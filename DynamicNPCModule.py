import asyncio
from interactions import SlashContext, Extension, Button, ButtonStyle, ComponentContext, component_callback, Embed
import random
import re
import logging
import json

class DynamicNPCModule(Extension):
    def __init__(self, bot):
        
        self.bot = bot
        self.db = bot.db
        logging.info("DynamicNPCModule initialized successfully.")
        
        # Register the component callbacks manually to ensure they're active
        bot.listen(self.npc_dialog_handler)
        bot.listen(self.npc_response_handler)
        logging.info("DynamicNPCModule component callbacks registered manually.")

    @component_callback(re.compile(r"^npc_dialog_\d+_\d+$"))
    async def npc_dialog_handler(self, ctx: ComponentContext):
        try:
            # Extract NPC ID and original user ID
            npc_id, original_user_id = map(int, ctx.custom_id.split("_")[2:4])

            # Ensure only original player can interact
            if ctx.author.id != original_user_id:
                await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
                return

            player_id = await self.bot.db.get_or_create_player(ctx.author.id)
            await ctx.defer(ephemeral=True)

            # Fetch NPC details
            npc_data = await self.db.fetchrow("""
                SELECT * FROM dynamic_npcs WHERE dynamic_npc_id = $1
            """, npc_id)

            if not npc_data:
                await ctx.send("Unable to find NPC information.", ephemeral=True)
                return

            npc_name = npc_data['name']

            logging.info(f"Checking for quests that player_id: {player_id} can turn in at npc_id: {npc_id}")

            # Fetch quests that can be turned in at this NPC
            turn_in_quests = await self.db.fetch("""
                SELECT * FROM player_quests pq
                JOIN quests q ON pq.quest_id = q.quest_id
                WHERE pq.player_id = $1 AND pq.status = 'in_progress' 
                AND q.turn_in_npc_id = $2
            """, player_id, npc_id)

            if turn_in_quests:
                for quest in turn_in_quests:
                    try:
                        objective = json.loads(quest['objective'])
                        logging.info(f"Objective for quest {quest['quest_id']}: {objective}")

                        # If objective is 'collect', check player's inventory
                        if objective['type'] == 'collect':
                            item_id = objective['item_id']
                            required_quantity = objective['quantity']

                            # Fetch player's inventory count
                            player_item_count = await self.db.fetchval("""
                                SELECT quantity FROM inventory
                                WHERE playerid = $1 AND itemid = $2
                            """, player_id, item_id)

                            if player_item_count and player_item_count >= required_quantity:
                                # Remove items from inventory
                                await self.db.execute("""
                                    UPDATE inventory SET quantity = quantity - $1
                                    WHERE playerid = $2 AND itemid = $3
                                """, required_quantity, player_id, item_id)

                                # Mark quest as completed
                                await self.db.execute("""
                                    UPDATE player_quests
                                    SET status = 'completed'
                                    WHERE player_id = $1 AND quest_id = $2
                                """, player_id, quest['quest_id'])

                                await ctx.send(f"Congratulations! You have completed the quest: {quest['name']}!", ephemeral=True)
                                return

                    except Exception as e:
                        logging.error(f"Error parsing objective for quest {quest['quest_id']}: {e}")
                        await ctx.send("An error occurred while processing quest objectives. Please try again later.", ephemeral=True)
                        return

            # Check for new quests that can be accepted by the player from this NPC
            available_quests = await self.db.fetch("""
                SELECT * FROM quests 
                WHERE turn_in_npc_id = $1 
                AND quest_id NOT IN (
                    SELECT quest_id 
                    FROM player_quests 
                    WHERE player_id = $2
                )
            """, npc_id, player_id)

            if available_quests:
                components = []
                for quest in available_quests:
                    components.append(
                        Button(
                            style=ButtonStyle.PRIMARY,
                            label=f"Accept quest: {quest['name']}",
                            custom_id=f"accept_quest|{quest['quest_id']}|{player_id}"
                        )
                    )
                await ctx.send(f"{npc_name} has the following quests available for you:", components=components, ephemeral=True)
                return

            # If no quests are ready to be turned in or accepted
            await ctx.send(f"No quests are ready to be turned in or accepted at {npc_name}.", ephemeral=True)

        except Exception as e:
            logging.error(f"Error in npc_dialog_handler: {e}")
            await ctx.send("An error occurred while interacting with the NPC. Please try again later.", ephemeral=True)








    async def send_dialogue(self, ctx, dialog, player_id):
        # Verify the correct use of columns that actually exist in the database
        try:
            embed = Embed(
                title="NPC Interaction",
                description=dialog['dialog_text'],  # Correct column name
                color=0x00FF00
            )
        
            # Fetch available responses for the player
            responses = await self.db.fetch(
                """
                SELECT * FROM dynamic_dialogs
                WHERE follow_up_dialog_id = $1
                """, dialog['dialog_id']
            )

            components = []
            for response in responses:
                components.append(
                    Button(
                        style=ButtonStyle.SECONDARY,
                        label=response['dialog_text'],  # Adjusted if needed to display the right text
                        custom_id=f"npc_response_{response['dialog_id']}_{player_id}"
                    )
                )

            await ctx.send(embeds=[embed], components=components, ephemeral=True)
        except KeyError as e:
            logging.error(f"KeyError in send_dialogue: Missing key {e}")
            await ctx.send("An error occurred while generating the dialog. Please try again later.", ephemeral=True)


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
        


    @component_callback(re.compile(r"^accept_quest\|\d+\|\d+$"))
    async def accept_quest_handler(self, ctx: ComponentContext):
        try:
            # Extract quest ID and player ID from the custom ID
            _, quest_id_str, player_id_str = ctx.custom_id.split("|")
            quest_id = int(quest_id_str)
            player_id = int(player_id_str)

            # Log for debugging
            logging.info(f"Accept quest handler triggered for quest_id: {quest_id}, player_id: {player_id}")

            # Fetch quest details from the unified quests table
            quest = await self.db.fetchrow(
                """
                SELECT * FROM quests WHERE quest_id = $1
                """, quest_id
            )

            # Log the fetched quest for debugging
            logging.info(f"Fetched quest details: {quest}")

            # Check if the quest was found
            if not quest:
                logging.error(f"Quest with quest_id: {quest_id} could not be found in the quests table.")
                await ctx.send("The quest could not be found. Please try again later.", ephemeral=True)
                return

            # Check if the player already has this quest
            existing_quest = await self.db.fetchval(
                """
                SELECT quest_id FROM player_quests
                WHERE player_id = $1 AND quest_id = $2
                """, player_id, quest_id
            )

            if existing_quest:
                logging.info(f"Player {player_id} already has the quest with quest_id: {quest_id}")
                await ctx.send("You have already accepted this quest.", ephemeral=True)
                return

            # Parse the requirements field (assuming it's a JSON string)
            requirements = quest['requirements']
            if requirements:
                requirements = json.loads(requirements)

                # Check player's inventory for required items
                if "required_items" in requirements:
                    required_items = requirements['required_items']
                    for item in required_items:
                        item_id = item['item_id']
                        quantity = item['quantity']

                        # Fetch item count from the inventory for the player
                        player_item_count = await self.db.fetchval(
                            """
                            SELECT quantity FROM inventory
                            WHERE playerid = $1 AND itemid = $2
                            """, player_id, item_id
                        )

                        # Ensure the player has enough of the required item
                        if not player_item_count or player_item_count < quantity:
                            await ctx.send(
                                f"You need {quantity} of item ID {item_id} to accept this quest.",
                                ephemeral=True
                            )
                            return

            # Assign the quest to the player in the player_quests table
            # When a quest is accepted, initialize current_step
            await self.db.execute(
                """
                INSERT INTO player_quests (player_id, quest_id, status, current_step, progress, is_dynamic)
                VALUES ($1, $2, 'in_progress', 0, '{}', $3)
                """, player_id, quest_id, quest['is_dynamic']
            )


            # Send confirmation message to the player
            quest_name = quest['name']  # Corrected to use the 'name' column
            await ctx.send(f"You have accepted the quest: {quest_name}!", ephemeral=True)

        except ValueError as ve:
            logging.error(f"ValueError in accept_quest_handler: {ve}")
            await ctx.send("An error occurred while accepting the quest. Please try again later.", ephemeral=True)
        except Exception as e:
            logging.error(f"Error in accept_quest_handler: {e}")
            await ctx.send("An error occurred while accepting the quest. Please try again later.", ephemeral=True)








    async def assign_quest(self, player_id, quest_id):
        logging.info(f"Attempting to assign quest_id: {quest_id} to player_id: {player_id}")
        try:
            # Check if the player already has the quest
            existing_quest = await self.db.fetchval(
                """
                SELECT quest_id FROM dynamic_player_quests
                WHERE player_id = $1 AND quest_id = $2
                """, player_id, quest_id
            )

            if existing_quest:
                logging.info(f"Player {player_id} already has quest_id: {quest_id}")
                return "You already have this quest."

            # Insert the quest as 'in_progress' for the player
            await self.db.execute(
                """
                INSERT INTO dynamic_player_quests (player_id, quest_id, progress, status)
                VALUES ($1, $2, 0, 'in_progress')
                """, player_id, quest_id
            )

            logging.info(f"Quest_id: {quest_id} successfully assigned to player_id: {player_id}")
            return "You have been assigned a new quest!"
        except Exception as e:
            logging.error(f"Error while assigning quest_id: {quest_id} to player_id: {player_id}: {e}")
            return "An error occurred while assigning the quest. Please try again later."


    async def update_quest_progress(self, player_id, quest_id, item_id=None, quantity=1):
        # Fetch the player's current quest data
        quest_data = await self.db.fetchrow(
            """
            SELECT * FROM player_quests
            WHERE player_id = $1 AND quest_id = $2 AND status = 'in_progress'
            """, player_id, quest_id
        )
    
        if not quest_data:
            logging.error(f"Quest data not found for player_id: {player_id}, quest_id: {quest_id}")
            return
    
        #current_step = quest_data['current_step']
        quest_details = await self.db.fetchrow("SELECT * FROM quests WHERE quest_id = $1", quest_id)
    
        if not quest_details:
            logging.error(f"Quest details not found for quest_id: {quest_id}")
            return
    
        


    @component_callback(re.compile(r"^turn_in_quest\|\d+\|\d+$"))
    async def turn_in_quest_handler(self, ctx: ComponentContext):
        try:
            # Extract quest ID and player ID from the custom ID
            _, quest_id_str, player_id_str = ctx.custom_id.split("|")
            quest_id = int(quest_id_str)
            player_id = int(player_id_str)

            # Fetch the quest details from the quests table
            quest = await self.db.fetchrow(
                """
                SELECT * FROM quests WHERE quest_id = $1
                """, quest_id
            )

            if not quest:
                await ctx.send("The quest could not be found. Please try again later.", ephemeral=True)
                return

            # Fetch player's current quest data
            player_quest = await self.db.fetchrow(
                """
                SELECT * FROM player_quests
                WHERE player_id = $1 AND quest_id = $2 AND status = 'in_progress'
                """, player_id, quest_id
            )

            if not player_quest:
                await ctx.send("You do not have this quest in progress.", ephemeral=True)
                return

           

        except Exception as e:
            logging.error(f"Error in turn_in_quest_handler: {e}")
            await ctx.send("An error occurred while turning in the quest. Please try again later.", ephemeral=True)



    async def handle_npc_action(self, player_id, action_type, action_value):
        # Handle different types of NPC actions, e.g., assign quests or give items
        if action_type == 'assign_quest':
            return await self.assign_quest(player_id, action_value)
        # Additional actions can be implemented here

# Setup function to load this as an extension
def setup(bot):
    logging.info("Setting up DynamicNPCModule extension...")
    DynamicNPCModule(bot)
