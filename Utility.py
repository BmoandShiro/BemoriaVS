
from interactions import Embed

async def send_quest_indicator(ctx, quest_name, quest_description):
    await ctx.send(embeds=[Embed(
        title="New Quest Acquired!",
        description=f"**{quest_name}**\n{quest_description}",
        color=0xFFD700  # Gold color to indicate a quest
    )])






async def offer_quest(ctx, db, player_id, quest_id):
    # Check if the player already has the quest
    existing_quest = await db.fetchval("""
        SELECT 1 FROM player_quests WHERE player_id = $1 AND quest_id = $2
    """, player_id, quest_id)
    
    if existing_quest:
        await ctx.send("You already have this quest active.")
        return

    # Insert the new quest as 'in_progress'
    await db.execute("""
        INSERT INTO player_quests (player_id, quest_id, status, progress)
        VALUES ($1, $2, 'in_progress', '{}')
    """, player_id, quest_id)

    # Fetch quest details to display
    quest_details = await db.fetchrow("""
        SELECT name, description FROM quests WHERE quest_id = $1
    """, quest_id)

    # Trigger the quest indicator
    await send_quest_indicator(ctx, quest_details['name'], quest_details['description'])
