
import random
import asyncio
from interactions import SlashContext, Extension, Button, ButtonStyle, ComponentContext, component_callback
import re

class WoodcuttingModule(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @component_callback(re.compile(r"^chop_\d+$"))
    async def chop_button_handler(self, ctx: ComponentContext):
        # Extract the original user's ID from the custom ID
        original_user_id = int(ctx.custom_id.split("_")[1])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)  # Acknowledge the interaction to prevent expiration

        # Get player data and proceed with chopping logic
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        player_data = await self.bot.db.fetch_player_details(player_id)
        current_location_id = player_data['current_location']
    
        # Pass control to the woodcutting logic, similar to fishing
        await self.start_chop_action(ctx, player_id, current_location_id)

    async def start_woodcutting(self, ctx: SlashContext, player_id: int, location_id: int, woodcutting_xp: int):
        # Fetch available trees from the current location
        trees = await self.db.fetch("""
            SELECT * FROM trees WHERE location_id = $1
        """, location_id)

        if not trees:
            await ctx.send("No trees to chop in this area.", ephemeral=True)
            return

        # Choose a random tree to chop
        tree = random.choice(trees)

        # Check if player meets woodcutting level requirement
        if woodcutting_xp < tree['woodcuttinglevelrequirement']:
            await ctx.send(f"You need at least {tree['woodcuttinglevelrequirement']} Woodcutting XP to chop a {tree['treetype']}.", ephemeral=True)
            return

        # Calculate the time required to chop the tree (simulate with async sleep)
        average_time = tree['averagetimetochop']
        await ctx.send(f"You start chopping the {tree['treetype']}... This will take approximately {average_time} seconds.", ephemeral=True)
        await asyncio.sleep(average_time)

        # Determine if the player successfully chops the tree (add a success rate based on player's level)
        success_chance = min(100, 50 + (woodcutting_xp - tree['woodcuttinglevelrequirement']) * 0.5)
        if random.randint(1, 100) <= success_chance:
            # Successfully chopped the tree
            log_name = f"{tree['treetype']} Log"
            await self.add_log_to_inventory(player_id, log_name)
            await ctx.send(f"You successfully chopped down a {tree['treetype']} and obtained {log_name}.", ephemeral=True)

            # Add XP to player's woodcutting skill
            await self.add_woodcutting_xp(player_id, 10)  # Example XP gained
        else:
            await ctx.send(f"You failed to chop the {tree['treetype']}. Better luck next time!", ephemeral=True)

    async def add_log_to_inventory(self, player_id: int, log_name: str):
        # Add the chopped log to player's inventory
        await self.db.execute("""
            INSERT INTO inventory (playerid, itemid, quantity, isequipped)
            VALUES ($1, (SELECT itemid FROM items WHERE name = $2), 1, FALSE)
            ON CONFLICT (playerid, itemid) DO UPDATE SET quantity = inventory.quantity + 1
        """, player_id, log_name)

    async def add_woodcutting_xp(self, player_id: int, xp_gained: int):
        # Add XP to player's woodcutting skill
        await self.db.execute("""
            UPDATE player_data
            SET woodcutting_xp = woodcutting_xp + $1
            WHERE playerid = $2
        """, xp_gained, player_id)
        
    async def start_chop_action(self, ctx: SlashContext, player_id: int, location_id: int):
        # Fetch a random tree from the current location to chop
        tree = await self.db.fetchrow("""
            SELECT * FROM trees
            WHERE locationid = $1
            ORDER BY RANDOM() LIMIT 1
        """, location_id)

    
        if not tree:
            await ctx.send("No trees to chop here.", ephemeral=True)
            return

        # Proceed with woodcutting logic, similar to how you handle fishing
        await ctx.send(f"You start chopping the {tree['treetype']}...", ephemeral=True)

        # Simulate chopping time, or fetch player skills and level to calculate
        # Chopping results and log gathering


# Setup function to load this as an extension
def setup(bot):
    WoodcuttingModule(bot)
