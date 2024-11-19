# npc_manager.py

from interactions import Extension, SlashContext
from NPC_Finn import Finn  # Import NPC classes
from NPC_Dave import Dave  # Import Dave
import logging

class NPCManager(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.npcs = {}
        self.hardcoded_npcs = {
            "finn": Finn(bot),
            "dave": Dave(bot)
        }

    async def load_npcs(self):
        # Fetch all dynamic NPCs from the database
        dynamic_npcs = await self.db.fetch("SELECT * FROM dynamic_npcs")
        for npc in dynamic_npcs:
            npc_name = npc['name'].lower()
            npc_id = npc['dynamic_npc_id']
            # Store the NPC information in the manager for easy lookup
            self.npcs[npc_name] = {
                "npc_id": npc_id,
                "locationid": npc['locationid'],  # Updated to match the renamed column
                "description": npc['description']
            }
    
    async def interact_with_npc(self, ctx: SlashContext, npc_name: str):
        """
        Interact with a specified NPC by name, after checking location.
        """
        npc_name = npc_name.lower()
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        player_location = await self.db.fetchval(
            "SELECT current_location FROM player_data WHERE playerid = $1",
            player_id
        )

        # Check if it's a hardcoded NPC (Finn or Dave)
        if npc_name in self.hardcoded_npcs:
            npc = self.hardcoded_npcs[npc_name]
            if player_location in npc.valid_locations:
                await npc.interact(ctx, player_id)
            else:
                await ctx.send(f"{npc_name.capitalize()} is not in this location.", ephemeral=True)
            return

        # Check if it's a dynamic NPC
        if npc_name in self.npcs:
            npc = self.npcs[npc_name]
            if player_location == npc["locationid"]:
                dynamic_npc_id = npc["npc_id"]
                
                # Trigger interaction via DynamicNPCModule
                dynamic_npc_module = getattr(self.bot, 'dynamic_npc_module', None)

                if dynamic_npc_module:
                    await dynamic_npc_module.npc_dialog_handler(ctx, dynamic_npc_id)
                else:
                    await ctx.send("Dynamic NPC Module is not available.", ephemeral=True)
            else:
                await ctx.send(f"{npc_name.capitalize()} is not in this location.", ephemeral=True)
        else:
            await ctx.send("This NPC does not exist.", ephemeral=True)

# Setup function for the bot to load NPCManager as an extension
def setup(bot):
    
    NPCManager(bot)  # This registers the NPCManager class as an extension
    logging.info("NPC_Manager extension setup completed.")