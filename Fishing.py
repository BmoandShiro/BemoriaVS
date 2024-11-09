import interactions
from interactions import SlashContext

class FishingSystem:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def fish(self, ctx: SlashContext, player_id):
        # Check if player has fishing gear and bait
        fishing_rod = await self.db.fetchrow("""
            SELECT * FROM inventory WHERE playerid = $1 AND itemid = (
                SELECT itemid FROM items WHERE name = 'Beginner’s Fishing Rod'
            )
        """, player_id)

        bait = await self.db.fetchrow("""
            SELECT * FROM inventory WHERE playerid = $1 AND itemid = (
                SELECT itemid FROM items WHERE name = 'Basic Bait'
            ) AND quantity > 0
        """, player_id)

        if not fishing_rod or not bait:
            await ctx.send("You need a fishing rod and some bait to fish here.")
            return

        # Use 1 bait
        new_bait_quantity = bait['quantity'] - 1
        await self.db.execute(
            "UPDATE inventory SET quantity = $1 WHERE inventoryid = $2",
            new_bait_quantity, bait['inventoryid']
        )

        # Simulate catching a fish from the `fish` table
        fish = await self.db.fetchrow("SELECT * FROM fish ORDER BY random() LIMIT 1")
        await ctx.send(f"You caught a {fish['name']}!")

