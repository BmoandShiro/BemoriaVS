import interactions
from interactions import Extension, slash_command, SlashContext
from command_helpers import location_required
from npc_base import NPCBase  # Assuming you have a base NPC class as previously discussed

class Finn(NPCBase, Extension):
    def __init__(self, bot):
        super().__init__(bot, bot.db)  # Initialize NPCBase with bot and db
        self.bot = bot
        self.db = bot.db

    @slash_command(name="talk_to_finn", description="Talk to Finn, the fishing instructor.")
    @location_required(valid_locations=["Docks"])
    async def talk_to_finn_command(self, ctx: SlashContext):
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        await self.interact(ctx, player_id)

    async def interact(self, ctx: SlashContext, player_id):
        # Finn's specific interaction logic
        has_fishing_gear = await self.db.fetchval("""
            SELECT COUNT(*) FROM inventory WHERE playerid = $1 AND itemid = (
                SELECT itemid FROM items WHERE name = 'Beginner’s Fishing Rod'
            )
        """, player_id)

        if has_fishing_gear > 0:
            await ctx.send("Finn says: 'You already have a fishing rod, young angler! Go catch some fish!'")
            return

        # Add Beginner’s Fishing Rod and Basic Bait to inventory
        fishing_rod_id = await self.db.fetchval("SELECT itemid FROM items WHERE name = 'Beginner’s Fishing Rod'")
        bait_id = await self.db.fetchval("SELECT itemid FROM items WHERE name = 'Basic Bait'")

        await self.db.execute("""
            INSERT INTO inventory (playerid, itemid, quantity, isequipped, slot) VALUES 
            ($1, $2, 1, false, NULL),
            ($1, $3, 10, false, NULL)
        """, player_id, fishing_rod_id, bait_id)

        # Send a message to the player
        await ctx.send(
            "Finn says: 'Here, take this fishing rod and some bait! You can use them at Tradewind Stream to catch fish.'"
        )

# Setup function to load this as an extension
def setup(bot):
    Finn(bot)
