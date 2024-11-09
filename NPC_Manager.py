from npc_finn import Finn

class NPCManager:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.npcs = {
            "finn": Finn(bot, db),
            # Add other NPCs here
        }

    async def interact_with_npc(self, npc_name, ctx, player_id):
        npc = self.npcs.get(npc_name)
        if npc:
            await npc.interact(ctx, player_id)
        else:
            await ctx.send("NPC not found.")

