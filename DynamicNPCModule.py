import asyncio
from interactions import SlashContext, Extension, Button, ButtonStyle, ComponentContext, component_callback, Embed
import random
import re

class DynamicNPCModule(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @component_callback(re.compile(r"^npc_dialog_\d+$"))
    async def npc_dialog_handler(self, ctx: ComponentContext):
        # Extract the NPC ID from the custom ID
        npc_id = int(ctx.custom_id.split("_")[2])
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)

        await ctx.defer(ephemeral=True)

        # Fetch initial dialogue for the NPC
        dialog = await self.db.fetchrow(
            """
            SELECT * FROM dynamic_dialogs
            WHERE npc_id = $1 AND initial = TRUE
            ORDER BY RANDOM() LIMIT 1
            """, npc_id
        )

        if not dialog:
            await ctx.send("This NPC has nothing to say at the moment.", ephemeral=True)
            return

        # Send dialogue and buttons for player responses
        await self.send_dialogue(ctx, dialog, player_id)

    async def send_dialogue(self, ctx, dialog, player_id):
        embed = Embed(title=dialog['dialogue_title'], description=dialog['dialogue_text'], color=0x00FF00)

        # Fetch available responses for the player
        responses = await self.db.fetch(
            """
            SELECT * FROM dynamic_dialogs
            WHERE previous_dialog_id = $1
            """, dialog['dialogue_id']
        )

        components = []
        for response in responses:
            components.append(
                Button(
                    style=ButtonStyle.SECONDARY,
                    label=response['response_text'],
                    custom_id=f"npc_response_{response['dialogue_id']}_{player_id}"
                )
            )

        await ctx.send(embeds=[embed], components=components, ephemeral=True)

    @component_callback(re.compile(r"^npc_response_\d+_\d+$"))
    async def npc_response_handler(self, ctx: ComponentContext):
        # Extract the dialogue ID and player ID from the custom ID
        _, dialog_id, player_id = ctx.custom_id.split("_")
        dialog_id, player_id = int(dialog_id), int(player_id)

        await ctx.defer(ephemeral=True)

        # Fetch the new dialogue based on player's response
        new_dialog = await self.db.fetchrow(
            """
            SELECT * FROM dynamic_dialogs
            WHERE dialogue_id = $1
            """, dialog_id
        )

        if not new_dialog:
            await ctx.send("The conversation ends here.", ephemeral=True)
            return

        # Send new dialogue
        await self.send_dialogue(ctx, new_dialog, player_id)

    async def assign_quest(self, player_id, quest_id):
        # Assign a quest to the player
        existing_quest = await self.db.fetchval(
            """
            SELECT quest_id FROM dynamic_player_quests
            WHERE player_id = $1 AND quest_id = $2
            """, player_id, quest_id
        )

        if existing_quest:
            return "You already have this quest."

        await self.db.execute(
            """
            INSERT INTO dynamic_player_quests (player_id, quest_id, progress, status)
            VALUES ($1, $2, 0, 'in_progress')
            """, player_id, quest_id
        )

        return "You have been assigned a new quest!"

    async def update_quest_progress(self, player_id, quest_id, progress):
        # Update quest progress for the player
        await self.db.execute(
            """
            UPDATE dynamic_player_quests
            SET progress = $1
            WHERE player_id = $2 AND quest_id = $3
            """, progress, player_id, quest_id
        )

    async def complete_quest(self, player_id, quest_id):
        # Complete the quest for the player
        await self.db.execute(
            """
            UPDATE dynamic_player_quests
            SET status = 'completed'
            WHERE player_id = $1 AND quest_id = $2
            """, player_id, quest_id
        )
        return "Quest completed!"

    async def handle_npc_action(self, player_id, action_type, action_value):
        # Handle different types of NPC actions, e.g., assign quests or give items
        if action_type == 'assign_quest':
            return await self.assign_quest(player_id, action_value)
        # Additional actions can be implemented here

# Setup function to load this as an extension
def setup(bot):
    DynamicNPCModule(bot)
