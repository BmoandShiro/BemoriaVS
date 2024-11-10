from interactions import Extension, SlashContext, component_callback, ComponentContext, Button, ButtonStyle
from NPC_Base import NPCBase  # Assuming you have a base NPC class for shared NPC functionality

class Finn(NPCBase, Extension):
    def __init__(self, bot):
        super().__init__(bot, bot.db)
        self.valid_locations = ["Docks"]  # List of locations where Finn can be found
        self.bot = bot
        self.db = bot.db

    async def interact(self, ctx: SlashContext, player_id):
        # Check if the player already has a fishing rod from Finn
        fishing_rod_id = await self.db.fetchval("SELECT itemid FROM items WHERE name = 'Beginner Fishing Rod'")

        bait_id = await self.db.fetchval("SELECT itemid FROM items WHERE name = 'Basic Bait'")

        has_fishing_gear = await self.db.fetchval("""
            SELECT COUNT(*) FROM inventory WHERE playerid = $1 AND itemid = $2
        """, player_id, fishing_rod_id)

        if has_fishing_gear > 0:
            await ctx.send("Finn says: 'You already have a fishing rod, young angler! Go catch some fish!'")
            return

        # Add Beginner's Fishing Rod
        await self.db.execute("""
            INSERT INTO inventory (playerid, itemid, quantity, isequipped, slot)
            VALUES ($1, $2, 1, false, NULL)
        """, player_id, fishing_rod_id)

        # Add Basic Bait and check for stacking
        existing_bait = await self.db.fetchrow("""
            SELECT inventoryid, quantity FROM inventory WHERE playerid = $1 AND itemid = $2
        """, player_id, bait_id)

        if existing_bait:
            # Update the quantity if bait already exists in inventory
            new_quantity = existing_bait['quantity'] + 10
            await self.db.execute("""
                UPDATE inventory SET quantity = $1 WHERE inventoryid = $2
            """, new_quantity, existing_bait['inventoryid'])
        else:
            # Add bait as a new item if it doesn't exist in inventory
            await self.db.execute("""
                INSERT INTO inventory (playerid, itemid, quantity, isequipped, slot)
                VALUES ($1, $2, 10, false, NULL)
            """, player_id, bait_id)

        # Send a message to the player
        await ctx.send(
            "Finn says: 'Here, take this fishing rod and some bait! You can use them at Tradewind Stream to catch fish.'"
        )
        
     #Add a component callback for the 'talk_to_finn' button
    @component_callback("talk_to_finn")
    async def talk_to_finn_button_handler(self, ctx: ComponentContext):
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        await self.interact(ctx, player_id)

# Setup function for the bot to load this as an extension
def setup(bot):
    bot.add_extension(Finn(bot))
