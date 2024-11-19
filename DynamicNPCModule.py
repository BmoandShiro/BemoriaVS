import asyncio
from interactions import SlashContext, Extension, Button, ButtonStyle, ComponentContext, component_callback, Embed
import random
import re
import logging


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
        logging.info(f"npc_dialog_handler triggered for NPC ID: {ctx.custom_id}")

        try:
            # Extract the NPC ID and the original user ID from the custom ID
            npc_id = int(ctx.custom_id.split("_")[2])
            original_user_id = int(ctx.custom_id.split("_")[3])

            # Ensure that only the original player can proceed
            if ctx.author.id != original_user_id:
                await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
                return

            player_id = await self.bot.db.get_or_create_player(ctx.author.id)
            await ctx.defer(ephemeral=True)

            # Fetch the NPC name from the database
            npc_data = await self.db.fetchrow(
                """
                SELECT name FROM dynamic_npcs
                WHERE dynamic_npc_id = $1
                """, npc_id
            )

            if not npc_data:
                await ctx.send("Unable to find NPC information.", ephemeral=True)
                return

            npc_name = npc_data['name']

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

            # Create an embed to show the NPC dialogue
            embed = Embed(title=npc_name, description=dialog['dialog_text'], color=0x00FF00)
            components = []

            # Fetch the available quest for the NPC from the `quests` table
            quest = await self.db.fetchrow(
                """
                SELECT quest_id, name AS quest_name
                FROM quests
                WHERE npc_id = $1
                LIMIT 1
                """, npc_id
            )

            # If a quest is available, add a button to accept it
            if quest:
                quest_name = quest['quest_name']
                quest_id = quest['quest_id']

                quest_button = Button(
                    style=ButtonStyle.PRIMARY,
                    label=f"Accept Quest: {quest_name}",
                    custom_id=f"accept_quest|{quest_id}|{player_id}"
                )
                components.append(quest_button)

            await ctx.send(embeds=[embed], components=components, ephemeral=True)

        except Exception as e:
            logging.error(f"Error in npc_dialog_handler: {e}")
            await ctx.send("An error occurred. Please try again later.", ephemeral=True)






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

            # Check for item requirements in the inventory if they exist
            if quest['required_item_ids'] and quest['required_quantities']:
                required_item_ids = eval(quest['required_item_ids'])
                required_quantities = eval(quest['required_quantities'])

                # Fetch player's inventory
                player_inventory = await self.db.fetch(
                    """
                    SELECT itemid, quantity FROM inventory WHERE player_id = $1
                    """, player_id
                )

                # Create a dictionary from the player's inventory for easier look-up
                inventory_dict = {item['itemid']: item['quantity'] for item in player_inventory}

                # Check if player has the required items and quantities
                for item_id, required_quantity in zip(required_item_ids, required_quantities):
                    if item_id not in inventory_dict or inventory_dict[item_id] < required_quantity:
                        await ctx.send("You do not have the required items to accept this quest.", ephemeral=True)
                        return

            # Assign the quest to the player in the player_quests table
            await self.db.execute(
                """
                INSERT INTO player_quests (player_id, quest_id, status, progress, is_dynamic)
                VALUES ($1, $2, 'in_progress', '{}', $3)
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


    async def update_quest_progress(self, player_id, quest_id, progress):
        # Update quest progress for the player
        await self.db.execute(
            """
            UPDATE dynamic_player_quests
            SET progress = $1
            WHERE player_id = $2 AND quest_id = $3
            """, progress, player_id, quest_id
        )

    @component_callback(re.compile(r"^turn_in_quest\|\d+\|\d+$"))
    async def turn_in_quest_handler(self, ctx: ComponentContext):
        try:
            # Extract quest ID and player ID from the custom ID
            _, quest_id_str, player_id_str = ctx.custom_id.split("|")
            quest_id = int(quest_id_str)
            player_id = int(player_id_str)

            # Fetch the quest details
            quest = await self.db.fetchrow(
                """
                SELECT * FROM quests WHERE quest_id = $1
                """, quest_id
            )

            if not quest:
                await ctx.send("The quest could not be found. Please try again later.", ephemeral=True)
                return

            # Fetch player inventory
            inventory_items = await self.db.fetch(
                """
                SELECT item_id, quantity FROM inventory
                WHERE player_id = $1
                """, player_id
            )
            inventory_dict = {item['item_id']: item['quantity'] for item in inventory_items}

            # Check if the player has the required items
            required_item_ids = list(map(int, quest['required_item_ids'].split(',')))
            required_quantities = list(map(int, quest['required_quantities'].split(',')))

            has_all_required_items = True
            for item_id, quantity in zip(required_item_ids, required_quantities):
                if inventory_dict.get(item_id, 0) < quantity:
                    has_all_required_items = False
                    break

            if not has_all_required_items:
                await ctx.send("You do not have all the required items to turn in the quest.", ephemeral=True)
                return

            # Remove the required items from the player's inventory
            for item_id, quantity in zip(required_item_ids, required_quantities):
                await self.db.execute(
                    """
                    UPDATE inventory
                    SET quantity = quantity - $1
                    WHERE player_id = $2 AND item_id = $3
                    """, quantity, player_id, item_id
                )

            # Mark the quest as complete
            await self.db.execute(
                """
                UPDATE player_quests
                SET status = 'completed'
                WHERE player_id = $1 AND quest_id = $2
                """, player_id, quest_id
            )

            # Send a success message
            await ctx.send(f"Congratulations! You have completed the quest: {quest['name']}!", ephemeral=True)

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
