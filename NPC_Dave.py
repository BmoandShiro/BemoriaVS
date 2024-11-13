from interactions import Extension, SlashContext, component_callback, ComponentContext, Button, ButtonStyle, Embed
from NPC_Base import NPCBase  # Assuming you have a base NPC class for shared NPC functionality
import logging
import re
from Utility import send_quest_indicator
from inventory_systems import InventorySystem

class Dave(NPCBase, Extension):
    def __init__(self, bot):
        super().__init__(bot, bot.db)
        self.valid_locations = ["Dave's Fishery"]
        self.bot = bot
        self.db = bot.db

        logging.info("Dave extension initialized successfully.")

    async def interact(self, ctx: SlashContext, player_id):
        logging.info(f"Interacting with Dave for player_id: {player_id}")

        # Check if player has the legendary fish in inventory
        legendary_fish_count = await self.db.fetchval("""
            SELECT COUNT(*)
            FROM inventory inv
            JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1 AND cf.rarity = 'legendary'
        """, player_id)

        # Check if Dave's quest is in progress
        dave_quest_status = await self.db.fetchval("""
            SELECT status FROM player_quests
            WHERE player_id = $1 AND quest_id = 2
        """, player_id)

        if dave_quest_status != 'in_progress':
            await ctx.send("Dave says: 'Scram kid, I don't have time for you.'")
            return

        if legendary_fish_count > 0:
            await self.complete_quest(ctx, player_id)
        else:
            await ctx.send("Dave says: 'I need to see a legendary fish to inspire me again.'")

    async def complete_quest(self, ctx, player_id):
        logging.info(f"Completing Dave's quest for player_id: {player_id}")

        # Fetch the inventory item ID for the legendary fish
        legendary_fish = await self.db.fetchrow("""
            SELECT inventoryid, caught_fish_id 
            FROM inventory inv
            JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1 AND cf.rarity = 'legendary'
            LIMIT 1
        """, player_id)

        # If legendary fish is found, use the drop logic to remove it
        if legendary_fish:
            await self._drop_item(player_id, legendary_fish['inventoryid'], legendary_fish['caught_fish_id'])
        else:
            await ctx.send("Error: Legendary fish not found in inventory.")
            return

        # Update player quest status to 'completed'
        await self.db.execute("""
            UPDATE player_quests SET status = 'completed'
            WHERE player_id = $1 AND quest_id = 2
        """, player_id)

        # Inform the player of quest completion
        await ctx.send(f"Dave says: 'You've inspired me with that legendary fish! I'll reopen my shop as a thank you.'")

        # Send quest indicator to the player
        quest_details = await self.db.fetchrow("""
            SELECT name, description FROM quests WHERE quest_id = $1
        """, 2)
        await send_quest_indicator(ctx, quest_details['name'], quest_details['description'])


    async def _drop_item(self, player_id, inventory_id, caught_fish_id=None):
        # Logic for dropping an item, similar to select_drop_item_handler
        if caught_fish_id:
            # If it's a fish, remove it from the inventory first
            await self.db.execute("DELETE FROM inventory WHERE inventoryid = $1 AND playerid = $2", inventory_id, player_id)
            # Then remove it from the caught_fish table
            await self.db.execute("DELETE FROM caught_fish WHERE id = $1", caught_fish_id)
        else:
            # If it's not a fish, simply remove it from the inventory table
            await self.db.execute("DELETE FROM inventory WHERE inventoryid = $1 AND playerid = $2", inventory_id, player_id)





    @component_callback(re.compile(r"^talk_to_dave_\d+$"))
    async def talk_to_dave_button_handler(self, ctx: ComponentContext):
        logging.info(f"Received interaction for talk_to_dave with custom_id: {ctx.custom_id}")

        try:
            # Extract player ID
            original_user_id = int(ctx.custom_id.split("_")[3])


            # Check if the correct user clicked the button
            if ctx.author.id != original_user_id:
                await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
                return

            # Proceed with interaction logic
            player_id = await self.bot.db.get_or_create_player(ctx.author.id)
            await self.interact(ctx, player_id)
        except Exception as e:
            logging.error(f"Error handling talk_to_dave button interaction: {e}")
            await ctx.send("An error occurred. Please try again later.", ephemeral=True)

    @component_callback(re.compile(r"^shop_player_\d+$"))
    async def shop_button_handler(self, ctx: ComponentContext):
        logging.info(f"Received interaction for shop with custom_id: {ctx.custom_id}")

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        gold_balance = await self.db.fetchval("""
            SELECT gold_balance FROM player_data WHERE playerid = $1
        """, player_id)

        shop_items = [
            {"name": "Ocean Rod", "price": 7500, "description": "A powerful rod capable of catching deep-sea fish."}
        ]

        shop_embed = Embed(
            title="Dave's Fishery - Shop",
            description="Select an item to buy or sell your fish.",
            color=0x00FF00
        )

        for item in shop_items:
            shop_embed.add_field(name=item['name'], value=f"Price: {item['price']} gold\n{item['description']}", inline=False)

        buy_button = Button(style=ButtonStyle.PRIMARY, label="Buy", custom_id=f"buy_item_{player_id}")
        sell_button = Button(style=ButtonStyle.PRIMARY, label="Sell Fish", custom_id=f"sell_fish_{player_id}")

        await ctx.send(embeds=[shop_embed], components=[[buy_button, sell_button]], ephemeral=True)

# Setup function to load this as an extension
def setup(bot):
    logging.info("Setting up Dave extension...")
    bot.add_extension(Dave(bot))
    logging.info("Dave extension setup completed.")
