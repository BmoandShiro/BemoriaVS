from interactions import Extension, SlashContext, component_callback, ComponentContext, Button, ButtonStyle
from NPC_Base import NPCBase  # Assuming you have a base NPC class for shared NPC functionality
import logging
import re

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
            # Check if the player already has or completed the quest
            player_quest = await self.db.fetch("""
                SELECT * FROM player_quests WHERE player_id = $1 AND quest_id = 1
            """, player_id)

            if not player_quest:
                # Offer the quest to the player
                await ctx.send(
                    "Finn says: 'Ah, you seem capable! I have a task for you. Gather 5 rare fish for me, and Ill make it worth your while. What do you say?'",
                    components=[Button(style=ButtonStyle.SUCCESS, label="Accept Quest", custom_id=f"accept_finn_quest_{ctx.author.id}")]
                )
            else:
                await ctx.send("Finn says: 'You already have your task. Go get those rare fish!'")
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

    # Add a component callback for the 'talk_to_finn' button
    @component_callback(re.compile(r"^talk_to_finn_\d+$"))
    async def talk_to_finn_button_handler(self, ctx: ComponentContext):
        logging.info(f"Received custom_id: {ctx.custom_id}")

        original_user_id = int(ctx.custom_id.split("_")[3])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        # Assuming you want to call the interact function if the user is authorized
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        await self.interact(ctx, player_id)

    # Component callback for accepting Finn's quest
    @component_callback(re.compile(r"^accept_finn_quest_\d+$"))
    async def accept_finn_quest_handler(self, ctx: ComponentContext):
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)

        # Add Finn's quest to player_quests table
        await self.db.execute("""
            INSERT INTO player_quests (player_id, quest_id, status, progress)
            VALUES ($1, 1, 'in_progress', '{"rare_fish_collected": 0}'::jsonb)
        """, player_id)

        await ctx.send("Finn says: 'Great! Bring me 5 rare fish, and youll earn my gratitude.'")

    async def give_finn_quest(self, ctx, player_id):
        # Check if the player has completed the objectives
        has_rare_fish = await self.check_rare_fish(player_id)  # Placeholder function to check if player has 5 rare fish
        if has_rare_fish:
            # Complete Finn's quest
            await self.complete_quest(player_id, 1)  # Assuming quest_id 1 is Finn's quest

            # Add XP for completing Finn's quest
            fishing_xp_reward = 100
            await self.db.execute("""
                UPDATE player_skills_xp
                SET fishing_xp = fishing_xp + $1
                WHERE playerid = $2
            """, fishing_xp_reward, player_id)

            await ctx.send("Finn says: 'Well done! Youve earned this reward. Good luck out there!'")
        else:
            await ctx.send("Finn says: 'You still need to gather more rare fish.'")

# Setup function for the bot to load this as an extension
def setup(bot):
    bot.add_extension(Finn(bot))
