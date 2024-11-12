# npc_manager.py

from interactions import Extension, SlashContext
from NPC_Finn import Finn  # Import NPC classes
from NPC_Dave import Dave  # Import Dave

class NPCManager(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        # Register NPCs by name or identifier
        self.npcs = {
            "finn": Finn(self.bot),  # Instantiate Finn
            "dave": Dave(self.bot)  # Instantiate Dave
        }

    async def interact_with_npc(self, ctx: SlashContext, npc_name: str):
        """
        Interact with a specified NPC by name, after checking location.
        """
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        player_location = await self.db.fetchval(
            "SELECT current_location FROM player_data WHERE playerid = $1",
            player_id
        )

        # Check if the NPC is available in the player's location
        if npc_name in self.npcs:
            npc = self.npcs[npc_name]
            if player_location in npc.valid_locations:
                # Call the interact method defined in each NPC class
                await npc.interact(ctx, player_id)
            else:
                await ctx.send(f"{npc_name.capitalize()} is not in this location.", ephemeral=True)
        else:
            await ctx.send("This NPC does not exist.", ephemeral=True)

# Setup function for the bot to load NPCManager as an extension
def setup(bot):
    NPCManager(bot)  # This registers the NPCManager class as an extension
