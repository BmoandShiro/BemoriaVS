import random
import asyncio
from interactions import SlashContext, Extension, Button, ButtonStyle, ComponentContext, component_callback
import re
from Inventory import Inventory


class MiningModule(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @component_callback(re.compile(r"^mine_\d+$"))
    async def mine_button_handler(self, ctx: ComponentContext):
        # Extract the original user's ID from the custom ID
        original_user_id = int(ctx.custom_id.split("_")[1])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)  # Acknowledge the interaction to prevent expiration

        # Get player data and proceed with mining logic
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        player_data = await self.bot.db.fetch_player_details(player_id)
        current_location_id = player_data['current_location']

        # Pass control to the mining logic, similar to woodcutting
        await self.start_mining_action(ctx, player_id, current_location_id)

    async def start_mining_action(self, ctx: ComponentContext, player_id: int, location_id: int):
        # Fetch an ore deposit based on the current location
        ore = await self.db.fetchrow("""
            SELECT * FROM ores WHERE locationid = $1 ORDER BY RANDOM() LIMIT 1
        """, location_id)

        if not ore:
            await ctx.send("No ore deposits to mine here.", ephemeral=True)
            return

        # Check if the player has the correct pickaxe equipped
        pickaxe_type_required = ore['pickaxetype']

        equipped_pickaxe = await self.db.fetchrow("""
            SELECT i.itemid, i.name, i.type
            FROM inventory inv
            JOIN items i ON inv.itemid = i.itemid
            WHERE inv.playerid = $1 AND inv.isequipped = TRUE AND i.pickaxe = TRUE
        """, player_id)


        if not equipped_pickaxe:
            await ctx.send("You need to equip a pickaxe to mine ores.", ephemeral=True)
            return

        if equipped_pickaxe['type'].lower() != pickaxe_type_required.lower():
            await ctx.send(f"You need a {pickaxe_type_required} pickaxe to mine this type of ore.", ephemeral=True)
            return

        # Add ore item to inventory using itemid from ore table
        item_id = ore['itemid']
        number_of_ores = ore['number_of_ores']

        # Fetch item details from items table to get the name
        item_details = await self.db.fetchrow("""
            SELECT name FROM items WHERE itemid = $1
        """, item_id)

        if not item_details:
            await ctx.send("Error: Unable to retrieve item details.", ephemeral=True)
            return

        # Use the imported Inventory class to add items to inventory
        inventory = Inventory(self.db, player_id)
        result_message = await inventory.add_item(item_id, number_of_ores)

        # Update player experience points (assuming there's a column for mining XP)
        xp_gained = ore['xp_gained']
        await self.db.execute("""
            UPDATE player_skills_xp
            SET mining_xp = mining_xp + $1
            WHERE playerid = $2
        """, xp_gained, player_id)

        # Send a detailed message about what was added, including XP gained
        item_name = item_details['name']
        await ctx.send(f"Added {number_of_ores}x {item_name} to your inventory. You gained {xp_gained} XP in Mining.", ephemeral=True)


# Setup function to load this as an extension
def setup(bot):
    MiningModule(bot)

