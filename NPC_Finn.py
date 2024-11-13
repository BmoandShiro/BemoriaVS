from interactions import Extension, SlashContext, component_callback, ComponentContext, Button, ButtonStyle
from NPC_Base import NPCBase  # Assuming you have a base NPC class for shared NPC functionality
import logging
import re
from Utility import send_quest_indicator


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
                    "Finn says: 'Ah, you seem capable! I have a task for you. Gather 5 rare fish for me, and I'll make it worth your while. What do you say?'",
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

        # Send a message to the player about the new gear
        await ctx.send(
            "Finn says: 'Here, take this fishing rod and some bait! You can use them at Tradewind Stream to catch fish.'"
        )

        # Offer the quest to the player if they have the new fishing gear but do not have the quest yet
        player_quest = await self.db.fetch("""
            SELECT * FROM player_quests WHERE player_id = $1 AND quest_id = 1
        """, player_id)

        if not player_quest:
            # Insert quest into player_quests table and send indicator
            await self.db.execute("""
                INSERT INTO player_quests (player_id, quest_id, status, progress)
                VALUES ($1, 1, 'in_progress', '{"rare_fish_collected": 0}'::jsonb)
            """, player_id)

            # Fetch quest details for the indicator
            quest_details = await self.db.fetchrow("""
                SELECT name, description FROM quests WHERE quest_id = $1
            """, 1)

            # Send the quest indicator
            await send_quest_indicator(ctx, quest_details['name'], quest_details['description'])

    # Add a component callback for the 'talk_to_finn' button
    @component_callback(re.compile(r"^talk_to_finn_\d+$"))
    async def talk_to_finn_button_handler(self, ctx: ComponentContext):
        # Log the received custom_id to verify its structure
        logging.info(f"[INFO] Received custom_id: {ctx.custom_id}")

        # Extract and log the split custom_id parts
        custom_id_parts = ctx.custom_id.split("_")
        logging.info(f"[INFO] Custom ID parts: {custom_id_parts}")

        # Ensure we have the expected number of parts
        if len(custom_id_parts) != 4:
            await ctx.send("Error: Unexpected custom ID format.", ephemeral=True)
            logging.error(f"[ERROR] Unexpected custom ID format: {ctx.custom_id}")
            return

        # Attempt to parse the user ID part (use the correct index, which is 3)
        try:
            original_user_id = int(custom_id_parts[3])
        except ValueError as e:
            await ctx.send("Error: Unable to extract user ID from custom ID.", ephemeral=True)
            logging.error(f"[ERROR] Failed to parse user ID from custom_id: {ctx.custom_id}. Error: {e}")
            return

        # Log the user IDs for verification
        logging.info(f"[INFO] Original user ID: {original_user_id}, Interaction by user ID: {ctx.author.id}")

        # Verify if the user interacting is the same as the original user
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            logging.info(f"[INFO] Authorization failed for user {ctx.author.id}.")
            return

        # Proceed with player interaction
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        logging.info(f"[INFO] Player ID {player_id} fetched or created.")

        # Remaining logic (quest status check, etc.)
        finn_quest_status = await self.db.fetchval("""
            SELECT status FROM player_quests
            WHERE player_id = $1 AND quest_id = 1
        """, player_id)
        logging.info(f"[INFO] Finn quest status for player {player_id}: {finn_quest_status}")

        if finn_quest_status == 'completed':
            # Handling for Dave's quest offering
            dave_quest_status = await self.db.fetchval("""
                SELECT status FROM player_quests
                WHERE player_id = $1 AND quest_id = 2
            """, player_id)
            logging.info(f"[INFO] Dave quest status for player {player_id}: {dave_quest_status}")

            if not dave_quest_status:
                await self.offer_dave_quest(ctx, player_id)
            else:
                await ctx.send("Finn says: 'Sorry, I don't have anything else for you right now.'")
            return

        elif finn_quest_status == 'in_progress':
            # Handle the quest in progress state
            has_rare_fish = await self.check_rare_fish(player_id)
            logging.info(f"[INFO] Player {player_id} has enough rare fish: {has_rare_fish}")

            if has_rare_fish:
                # Complete the quest and remove fish
                await self.db.execute("""
                    UPDATE player_quests
                    SET status = 'completed'
                    WHERE player_id = $1 AND quest_id = 1
                """, player_id)
                logging.info(f"[INFO] Player {player_id}'s quest has been marked as complete.")

                rare_fish_items = await self.db.fetch("""
                    SELECT inventoryid, caught_fish_id
                    FROM inventory inv
                    JOIN caught_fish cf ON inv.caught_fish_id = cf.id
                    WHERE inv.playerid = $1 AND cf.rarity = 'rare'
                    LIMIT 5
                """, player_id)
                logging.info(f"[INFO] Rare fish items found for player {player_id}: {rare_fish_items}")

                if not rare_fish_items:
                    await ctx.send("Error: No rare fish found in your inventory.")
                    logging.warning(f"[WARNING] No rare fish found in inventory for player {player_id} after quest completion.")
                    return

                for item in rare_fish_items:
                    await self.db.execute("DELETE FROM inventory WHERE inventoryid = $1 AND playerid = $2", item['inventoryid'], player_id)
                    await self.db.execute("DELETE FROM caught_fish WHERE id = $1", item['caught_fish_id'])
                    logging.info(f"[INFO] Removed fish with inventoryid {item['inventoryid']} and caught_fish_id {item['caught_fish_id']} for player {player_id}")

                fishing_xp_reward = 50
                await self.db.execute("""
                    UPDATE player_skills_xp
                    SET fishing_xp = fishing_xp + $1
                    WHERE playerid = $2
                """, fishing_xp_reward, player_id)
                logging.info(f"[INFO] Awarded {fishing_xp_reward} fishing XP to player {player_id}")

                await ctx.send("Finn says: 'Thank you for gathering the rare fish! Here is your reward.'")
                await self.offer_dave_quest(ctx, player_id)
            else:
                await ctx.send("Finn says: 'You already have your task. Go get those rare fish!'")
            return

        await self.interact(ctx, player_id)
        logging.info(f"[INFO] Interact function called for player {player_id}.")




    async def offer_dave_quest(self, ctx, player_id):
        # Insert the new quest for Dave into the player_quests table
        await self.db.execute("""
            INSERT INTO player_quests (player_id, quest_id, status, progress)
            VALUES ($1, 2, 'in_progress', '{"legendary_fish_collected": 0}')
        """, player_id)

        # Fetch quest details for the indicator
        quest_details = await self.db.fetchrow("""
            SELECT name, description FROM quests WHERE quest_id = $1
        """, 2)

        # Trigger the quest indicator
        await send_quest_indicator(ctx, quest_details['name'], quest_details['description'])

        # Send the player the dialogue offering Dave's quest
        await ctx.send("Finn says: 'I've heard of an old man in town named Dave. He used to be a great angler like you but has recently stopped fishing. He devoted his life to the catching legendary fish. Maybe you will see him around town.'")


   
    




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
        logging.info(f"[INFO] Entered give_finn_quest for player_id {player_id}")

        # Step 1: Check if the player has completed the objectives (i.e., has enough rare fish)
        has_rare_fish = await self.check_rare_fish(player_id)
        logging.info(f"[DEBUG] Player {player_id} has enough rare fish: {has_rare_fish}")

        if not has_rare_fish:
            await ctx.send("Finn says: 'You still need to gather more rare fish.'")
            logging.info(f"[DEBUG] Player {player_id} does not have enough rare fish, stopping quest.")
            return

        # Step 2: Update the player's quest status to complete
        try:
            await self.db.execute("""
                UPDATE player_quests
                SET status = 'completed'
                WHERE player_id = $1 AND quest_id = 1
            """, player_id)
            logging.info(f"[INFO] Player {player_id}'s quest has been marked as complete.")
        except Exception as e:
            logging.error(f"[ERROR] Could not update quest status for player {player_id}: {e}")
            await ctx.send("Error: Could not complete the quest. Please try again later.")
            return

        # Step 3: Fetch up to 5 rare fish items for removal
        try:
            rare_fish_items = await self.db.fetch("""
                SELECT inventoryid, caught_fish_id
                FROM inventory inv
                JOIN caught_fish cf ON inv.caught_fish_id = cf.id
                WHERE inv.playerid = $1 AND cf.rarity = 'rare'
                LIMIT 5
            """, player_id)
            logging.info(f"[DEBUG] Rare fish items found for player {player_id}: {rare_fish_items}")
        except Exception as e:
            logging.error(f"[ERROR] Could not fetch rare fish for player {player_id}: {e}")
            await ctx.send("Error: Could not verify rare fish in your inventory. Please try again later.")
            return

        if not rare_fish_items:
            await ctx.send("Error: No rare fish found in your inventory.")
            logging.warning(f"[WARNING] No rare fish found in inventory for player {player_id} after quest completion.")
            return

        # Step 4: Remove the rare fish from inventory
        for item in rare_fish_items:
            logging.info(f"[DEBUG] Attempting to remove fish with inventoryid {item['inventoryid']} and caught_fish_id {item['caught_fish_id']} for player {player_id}")
            await self._drop_item(player_id, item['inventoryid'], item['caught_fish_id'])

        # Step 5: Award fishing XP for completing Finn's quest
        fishing_xp_reward = 50  # Assuming 50 XP as the reward for Finn's quest
        try:
            await self.db.execute("""
                UPDATE player_skills_xp
                SET fishing_xp = fishing_xp + $1
                WHERE playerid = $2
            """, fishing_xp_reward, player_id)
            logging.info(f"[INFO] Awarded {fishing_xp_reward} fishing XP to player {player_id}")
        except Exception as e:
            logging.error(f"[ERROR] Could not award XP to player {player_id}: {e}")
            await ctx.send("Error: Could not award XP for quest completion. Please try again later.")

        # Step 6: Send a message to the player indicating quest completion and reward
        await ctx.send("Finn says: 'Well done! You've brought me enough rare fish. Here's some XP for your trouble.'")




        async def _drop_item(self, player_id, inventory_id, caught_fish_id=None):
            # Logging entry into the function
            logging.info(f"[INFO] Entered _drop_item for player_id {player_id}, inventory_id {inventory_id}, caught_fish_id {caught_fish_id}")

            try:
                if caught_fish_id:
                    # If it's a fish, remove it from the inventory first
                    await self.db.execute("DELETE FROM inventory WHERE inventoryid = $1 AND playerid = $2", inventory_id, player_id)
                    logging.info(f"[INFO] Dropped fish item from inventory with inventoryid {inventory_id} for player {player_id}")
            
                    # Then remove it from the caught_fish table
                    await self.db.execute("DELETE FROM caught_fish WHERE id = $1", caught_fish_id)
                    logging.info(f"[INFO] Dropped fish item from caught_fish with caught_fish_id {caught_fish_id} for player {player_id}")
                else:
                    # If it's not a fish, simply remove it from the inventory table
                    await self.db.execute("DELETE FROM inventory WHERE inventoryid = $1 AND playerid = $2", inventory_id, player_id)
                    logging.info(f"[INFO] Dropped item with inventoryid {inventory_id} for player {player_id}")
            except Exception as e:
                logging.error(f"[ERROR] Failed to drop item with inventoryid {inventory_id} for player {player_id}: {e}")
                await ctx.send("Error: Could not drop the item. Please try again later.")






            
    async def check_rare_fish(self, player_id):
        # Count the number of rare fish linked to the player's inventory
        rare_fish_count = await self.db.fetchval("""
            SELECT COUNT(*)
            FROM inventory inv
            JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1 AND cf.rarity = 'rare'
        """, player_id)
    
        # Return True if the player has collected at least 5 rare fish
        return rare_fish_count >= 5




# Setup function for the bot to load this as an extension
def setup(bot):
    bot.add_extension(Finn(bot))
