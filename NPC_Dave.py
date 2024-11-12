# NPC_Dave.py
from interactions import Extension, SlashContext, component_callback, ComponentContext, Button, ButtonStyle, Embed, StringSelectMenu, StringSelectOption
from NPC_Base import NPCBase  # Assuming you have a base NPC class for shared NPC functionality
import logging
import re
from Utility import send_quest_indicator

class Dave(NPCBase, Extension):
    def __init__(self, bot):
        super().__init__(bot, bot.db)
        self.valid_locations = ["Dave's Fishery"]
        self.bot = bot
        self.db = bot.db

    async def interact(self, ctx: SlashContext, player_id):
        # Check if player has the legendary fish in inventory
        legendary_fish = await self.db.fetchrow("""
            SELECT inv.inventoryid, cf.name FROM inventory inv
            JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1 AND cf.rarity = 'legendary'
        """, player_id)

        # Check if Dave's quest is in progress
        dave_quest_status = await self.db.fetchval("""
            SELECT status FROM player_quests
            WHERE player_id = $1 AND quest_id = 2
        """, player_id)

        # If the quest is not in progress, Dave is not interested
        if dave_quest_status != 'in_progress':
            await ctx.send("Dave says: 'Scram kid, I don't have time for you.'")
            return

        # If the player has a legendary fish and Dave's quest is in progress
        if legendary_fish:
            await self.complete_quest(ctx, player_id, legendary_fish)
        else:
            await ctx.send("Dave says: 'I need to see a legendary fish to inspire me again.'")
    
    async def complete_quest(self, ctx, player_id, legendary_fish):
        # Remove the legendary fish from the inventory
        await self.db.execute("""
            DELETE FROM inventory WHERE inventoryid = $1
        """, legendary_fish['inventoryid'])

        # Mark Dave's quest as complete
        await self.db.execute("""
            UPDATE player_quests SET status = 'completed'
            WHERE player_id = $1 AND quest_id = 2
        """, player_id)

        # Notify player with the quest completion message
        await ctx.send(f"Dave says: 'You've inspired me with that legendary {legendary_fish['name']}! I'll reopen my shop as a thank you.'")

        # Send a quest completion indicator
        quest_details = await self.db.fetchrow("""
            SELECT name, description FROM quests WHERE quest_id = $1
        """, 2)
        await send_quest_indicator(ctx, quest_details['name'], quest_details['description'])

    @component_callback(re.compile(r"^talk_to_dave_\d+$"))
    async def talk_to_dave_button_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[3])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        await self.interact(ctx, player_id)

    @component_callback(re.compile(r"^shop_\d+$"))
    async def shop_button_handler(self, ctx: ComponentContext):
        # Get player's gold balance
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        gold_balance = await self.db.fetchval("""
            SELECT gold_balance FROM player_data WHERE playerid = $1
        """, player_id)

        # Shop Items (could also be fetched from a table)
        shop_items = [
            {"name": "Ocean Rod", "price": 7500, "description": "A powerful rod capable of catching deep-sea fish."}
        ]

        # Show shop items
        shop_embed = Embed(
            title="Dave's Fishery - Shop",
            description="Select an item to buy or sell your fish.",
            color=0x00FF00
        )

        # Adding items to the embed
        for item in shop_items:
            shop_embed.add_field(name=item['name'], value=f"Price: {item['price']} gold\n{item['description']}", inline=False)

        # Shop Buttons
        buy_button = Button(style=ButtonStyle.PRIMARY, label="Buy", custom_id=f"buy_item_{player_id}")
        sell_button = Button(style=ButtonStyle.PRIMARY, label="Sell Fish", custom_id=f"sell_fish_{player_id}")

        await ctx.send(embeds=[shop_embed], components=[[buy_button, sell_button]], ephemeral=True)

    @component_callback(re.compile(r"^buy_item_\d+$"))
    async def buy_item_handler(self, ctx: ComponentContext):
        player_id = int(ctx.custom_id.split("_")[2])
        gold_balance = await self.db.fetchval("SELECT gold_balance FROM player_data WHERE playerid = $1", player_id)

        if gold_balance >= 7500:
            await self.db.execute("UPDATE player_data SET gold_balance = gold_balance - 7500 WHERE playerid = $1", player_id)
            # Add Ocean Rod to Inventory
            ocean_rod_id = await self.db.fetchval("SELECT itemid FROM items WHERE name = 'Ocean Rod'")
            await self.db.execute("""
                INSERT INTO inventory (playerid, itemid, quantity, isequipped, slot)
                VALUES ($1, $2, 1, false, NULL)
            """, player_id, ocean_rod_id)

            await ctx.send("Dave says: 'Here is your Ocean Rod! Good luck out there, angler!'")
        else:
            await ctx.send("Dave says: 'You don't have enough gold to buy that!'")

    @component_callback(re.compile(r"^sell_fish_\d+$"))
    async def sell_fish_handler(self, ctx: ComponentContext):
        player_id = int(ctx.custom_id.split("_")[2])

        # Fetch all fish from player's inventory
        fish_items = await self.db.fetch("""
            SELECT inv.inventoryid, cf.name, cf.length, cf.weight, cf.rarity FROM inventory inv
            JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1
        """, player_id)

        if not fish_items:
            await ctx.send("Dave says: 'You don't have any fish to sell!'", ephemeral=True)
            return

        # Calculate fish values and show them
        fish_embed = Embed(
            title="Sell Your Fish",
            description="Select the fish you want to sell.",
            color=0x00FF00
        )

        options = []
        for fish in fish_items:
            base_value = 100  # Base value can be assigned based on fish rarity/type
            value = base_value + (fish['length'] * 10) + (fish['weight'] * 5)
            options.append({
                "name": fish['name'],
                "value": str(fish['inventoryid']),
                "description": f"Length: {fish['length']} cm, Weight: {fish['weight']} kg, Value: {value} gold"
            })

        sell_select_menu = StringSelectMenu(
            custom_id="select_fish_to_sell",
            placeholder="Select a fish to sell",
            options=[StringSelectOption(label=opt['name'], value=opt['value']) for opt in options]
        )

        await ctx.send(embeds=[fish_embed], components=[sell_select_menu], ephemeral=True)

    @component_callback("select_fish_to_sell")
    async def select_fish_to_sell_handler(self, ctx: ComponentContext):
        fish_inventory_id = int(ctx.values[0])
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)

        # Fetch fish details
        fish_details = await self.db.fetchrow("""
            SELECT cf.length, cf.weight FROM inventory inv
            JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.inventoryid = $1
        """, fish_inventory_id)

        base_value = 100
        fish_value = base_value + (fish_details['length'] * 10) + (fish_details['weight'] * 5)

        # Remove the fish and update player's gold balance
        await self.db.execute("DELETE FROM inventory WHERE inventoryid = $1", fish_inventory_id)
        await self.db.execute("UPDATE player_data SET gold_balance = gold_balance + $1 WHERE playerid = $2", fish_value, player_id)

        await ctx.send(f"Dave says: 'Thanks for the fish! Here's {fish_value} gold for your efforts.'", ephemeral=True)

# Setup function to load this as an extension
def setup(bot):
    bot.add_extension(Dave(bot))
