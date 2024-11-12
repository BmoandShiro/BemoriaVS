class NPCBase:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def give_item(self, ctx, player_id, item_name, quantity=1):
        item_id = await self.db.fetchval("SELECT itemid FROM items WHERE name = $1", item_name)
        if item_id:
            await self.db.execute(
                "INSERT INTO inventory (playerid, itemid, quantity) VALUES ($1, $2, $3) "
                "ON CONFLICT (playerid, itemid) DO UPDATE SET quantity = inventory.quantity + $3",
                player_id, item_id, quantity
            )
            await ctx.send(f"You received {quantity} x {item_name}.")
        else:
            await ctx.send("Item not found.")


    async def complete_quest(self, player_id, quest_id):
        # Fetch quest details
        quest = await self.db.fetchrow("SELECT * FROM quests WHERE quest_id = $1", quest_id)

        if not quest:
            return "Quest not found."

        # Update player_quests table to mark quest as completed
        await self.db.execute("""
            UPDATE player_quests
            SET status = 'completed', progress = jsonb_set(progress, '{is_completed}', 'true')
            WHERE player_id = $1 AND quest_id = $2
        """, player_id, quest_id)

        # Grant Fishing XP if applicable
        fishing_xp_reward = quest['fishing_xp_reward']
        if fishing_xp_reward > 0:
            await self.add_fishing_xp(player_id, fishing_xp_reward)
            reward_message = f"You have earned {fishing_xp_reward} fishing XP!"

        # Other potential rewards (e.g., items, general XP) would also be granted here
        return f"Quest '{quest['name']}' completed! {reward_message}"

    async def add_fishing_xp(self, player_id, xp_gained):
        """Update fishing XP for the player"""
        await self.db.execute("""
            UPDATE player_skills_xp
            SET fishing_xp = fishing_xp + $1
            WHERE playerid = $2
        """, xp_gained, player_id)