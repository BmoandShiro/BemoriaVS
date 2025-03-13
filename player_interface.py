import re
from interactions import ButtonStyle, Embed, Button, Client, Extension, slash_command, SlashContext, component_callback, ComponentContext
from functools import partial
import logging
import math
import json
from inventory_systems import InventorySystem  # Import the InventorySystem
from interactions import ButtonStyle, Embed, Button, Extension, slash_command, ComponentContext
import re
import random
#from Shop_Manager import ShopManager

class playerinterface(Extension):
    def __init__(self, bot):
        self.bot = bot
        

    async def send_player_ui(self, ctx, location_name, health, mana, stamina, current_location_id, gold_balance):
        db = self.bot.db
        player_id = await db.get_or_create_player(ctx.author.id)
    
        current_inventory_count = await db.get_current_inventory_count(player_id)
        max_inventory_capacity = await db.get_inventory_capacity(player_id)

        # Fetch max_health, max_mana, and max_stamina from the database
        max_stats = await db.fetchrow("""
            SELECT max_health, max_mana, max_stamina
            FROM player_data
            WHERE playerid = $1
        """, player_id)

        embed = Embed(
            title="Player Information",
            description=f"You are currently in {location_name}",
            color=0x00FF00
        )
        embed.add_field(name="Health", value=f"{health}/{max_stats['max_health']}", inline=True)
        embed.add_field(name="Mana", value=f"{mana}/{max_stats['max_mana']}", inline=True)
        embed.add_field(name="Stamina", value=f"{stamina}/{max_stats['max_stamina']}", inline=True)
        embed.add_field(name="Inventory Capacity", value=f"{current_inventory_count}/{max_inventory_capacity}", inline=True)
        embed.add_field(name="Gold", value=f"{gold_balance} gold", inline=True)  # Add gold information here
    
        user_id = ctx.author.id  # This is the Discord User ID

        # Static buttons with user ID in custom_id to link them to the player who requested the UI
        static_buttons = [
            Button(style=ButtonStyle.PRIMARY, label="Travel", custom_id=f"travel_{user_id}"),
            Button(style=ButtonStyle.PRIMARY, label="Skills", custom_id=f"skills_{user_id}"),
            Button(style=ButtonStyle.PRIMARY, label="View Stats", custom_id=f"view_stats_{user_id}"),
            Button(style=ButtonStyle.PRIMARY, label="Inventory", custom_id=f"inventory_{user_id}"),
            Button(style=ButtonStyle.PRIMARY, label="Quests", custom_id=f"quests_{user_id}"),
            Button(style=ButtonStyle.PRIMARY, label="Travel To", custom_id=f"travel_to_{user_id}")
        ]

        # Get dynamic buttons based on the current location
        dynamic_buttons = await self.get_location_based_buttons(current_location_id, player_id)

        # Update dynamic buttons to include user ID in their custom_id as well
        dynamic_buttons = [
            Button(style=button.style, label=button.label, custom_id=f"{button.custom_id}_{user_id}")
            for button in dynamic_buttons
        ]

        # Arrange static and dynamic buttons in rows of up to 5 each
        all_buttons = static_buttons + dynamic_buttons
        button_rows = [all_buttons[i:i + 5] for i in range(0, len(all_buttons), 5)]

        # Send the embed with the buttons arranged in rows
        await ctx.send(embeds=[embed], components=button_rows, ephemeral=False)





    import logging

    async def get_location_based_buttons(self, location_id, player_id):
        db = self.bot.db
        logging.info(f"Fetching location-based buttons for location_id: {location_id}, player_id: {player_id}")
        
        # First get the player's party status
        party_info = await db.fetchrow("""
            SELECT p.*, pm.role 
            FROM parties p
            JOIN party_members pm ON p.party_id = pm.party_id
            WHERE pm.player_id = $1 AND p.is_active = true
        """, player_id)

        # Create party management buttons
        party_buttons = []
        if not party_info:
            # Not in a party - show create button
            party_buttons.append(Button(
                style=ButtonStyle.SUCCESS,
                label="Create Party",
                custom_id=f"party_create_{player_id}"
            ))
        else:
            # In a party - show party management buttons
            if party_info['leader_id'] == player_id:
                # Leader buttons
                party_buttons.extend([
                    Button(style=ButtonStyle.PRIMARY, label="Party Info", custom_id=f"party_info_{player_id}"),
                    Button(style=ButtonStyle.SUCCESS, label="Invite Player", custom_id=f"party_invite_{player_id}"),
                    Button(style=ButtonStyle.DANGER, label="Kick Member", custom_id=f"party_kick_{player_id}"),
                    Button(style=ButtonStyle.SECONDARY, label="Transfer Leader", custom_id=f"party_transfer_{player_id}"),
                    Button(style=ButtonStyle.DANGER, label="Disband Party", custom_id=f"party_disband_{player_id}")
                ])
            else:
                # Member buttons
                party_buttons.extend([
                    Button(style=ButtonStyle.PRIMARY, label="Party Info", custom_id=f"party_info_{player_id}"),
                    Button(style=ButtonStyle.DANGER, label="Leave Party", custom_id=f"party_leave_{player_id}"),
                    Button(style=ButtonStyle.SECONDARY, label="Ready Status", custom_id=f"party_ready_{player_id}")
                ])

        # Get location-based commands
        commands = await db.fetch("""
            SELECT command_name, button_label, custom_id, button_color, condition, required_quest_id, required_quest_status, required_item_id
            FROM location_commands
            WHERE locationid = $1
        """, location_id)

        buttons = []
        logging.info(f"Fetched {len(commands)} commands for location_id {location_id}")
        
        # Add party buttons first
        buttons.extend(party_buttons)
        
        # Process location commands
        for command in commands:
            logging.info(f"Processing command: {command}")
            button_color = command.get('button_color') or 'PRIMARY'
            
            # Check if the command has quest requirements and evaluate them
            if command['required_quest_id'] is not None:
                quest_status = await db.fetchval("""
                    SELECT status FROM player_quests WHERE player_id = $1 AND quest_id = $2
                """, player_id, command['required_quest_id'])

                if quest_status != command['required_quest_status']:
                    # Skip this button if quest condition is not met
                    continue

            # Check if the command has item requirements and evaluate them
            if command['required_item_id'] is not None:
                has_required_item = await db.fetchval("""
                    SELECT COUNT(*) FROM inventory WHERE playerid = $1 AND itemid = $2
                """, player_id, command['required_item_id'])

                if has_required_item == 0:
                    # Skip this button if the required item is not in the player's inventory
                    continue

            # Determine button style based on button_color field
            button_style = ButtonStyle.PRIMARY
            if button_color == 'SUCCESS':
                button_style = ButtonStyle.SUCCESS
            elif button_color == 'DANGER':
                button_style = ButtonStyle.DANGER
            elif button_color == 'SECONDARY':
                button_style = ButtonStyle.SECONDARY

            # Adjust custom_id generation for dynamic NPC buttons to be consistent with what DynamicNPCModule expects
            if "talk_to_" in command['command_name']:
                npc_name = command['command_name'].split("talk_to_")[1]
                npc_id = await db.fetchval("SELECT dynamic_npc_id FROM dynamic_npcs WHERE LOWER(name) = LOWER($1)", npc_name)

                if npc_id:
                    # Update custom_id to match expected pattern for DynamicNPCModule
                    custom_id = f"npc_dialog_{npc_id}"  # Use npc_id to ensure the custom_id is uniquely linked to the NPC
                else:
                    custom_id = command['custom_id']
            else:
                custom_id = command['custom_id']

            logging.info(f"Final custom_id for button: {custom_id}")

            # Add the button if all conditions are met or if no conditions exist
            buttons.append(Button(style=button_style, label=command['button_label'], custom_id=custom_id))

        logging.info(f"Returning {len(buttons)} buttons for location_id {location_id}")
        return buttons



           





    async def send_player_stats(self, ctx, player_id):
        db = self.bot.db
        player_stats = await db.fetch_view_stats(player_id)

        if player_stats:
            embeds = []
            embed = Embed(
                title="Player Stats",
                description=f"Stats for Player ID: {player_id}",
                color=0x00FF00
            )

            for i, (stat, value) in enumerate(player_stats.items()):
                if stat != "playerid" and value is not None:
                    embed.add_field(name=stat.replace("_", " ").title(), value=f"{value}", inline=True)
                    if (i + 1) % 25 == 0:  # Add a new embed if there are 25 fields
                        embeds.append(embed)
                        embed = Embed(color=0x00FF00)

            embeds.append(embed)
            await ctx.send(embeds=embeds)
        else:
            await ctx.send("Your player stats could not be found.", ephemeral=True)
            

    async def send_player_skills(self, ctx, player_id):
        db = self.bot.db
        player_skills = await db.fetch_view_skills(player_id)
        
        if player_skills:
            embeds = []
            embed = Embed(
                title="Player Skills",
                description=f"Skills for Player ID: {player_id}",
                color=0x00FF00
            )

            skill_pairs = list(player_skills.items())[1:]  # Skip the playerid

            for i in range(0, len(skill_pairs), 2):
                if i < len(skill_pairs):
                    skill1, value1 = skill_pairs[i]
                    embed.add_field(name=skill1.replace("_", " ").title(), value=f"{value1}", inline=True)
                if i + 1 < len(skill_pairs):
                    skill2, value2 = skill_pairs[i + 1]
                    embed.add_field(name=skill2.replace("_", " ").title(), value=f"{value2}", inline=True)
                
                if (i + 2) % 2 == 0:  # Add a new embed after every 2 fields
                    embeds.append(embed)
                    embed = Embed(color=0x00FF00)
            
            if len(embed.fields) > 0:
                embeds.append(embed)

            # Send embeds in batches of 10
            for i in range(0, len(embeds), 10):
                await ctx.send(embeds=embeds[i:i+10])
        else:
            await ctx.send("Your player skills could not be found.", ephemeral=True)

    @slash_command(name="playerui", description="Reload the player UI menu")
    async def reload_ui_command(self, ctx):
        db = self.bot.db
        player_id = await db.get_or_create_player(ctx.author.id)

        # Check if player is in combat by accessing battle_system through extensions
        battle_system = self.bot.get_ext("Battle_System")
        if battle_system and player_id in battle_system.active_battles:
            await ctx.send("You cannot use this command while in combat! Use the flee button if you want to escape.", ephemeral=True)
            return

        player_data = await db.fetchrow("""
            SELECT pd.health, pd.mana, pd.stamina, l.name, pd.current_location, pd.gold_balance
            FROM player_data pd
            JOIN locations l ON l.locationid = pd.current_location
            WHERE pd.playerid = $1
        """, player_id)

        if player_data:
            await self.send_player_ui(
                ctx,
                player_data['name'],
                player_data['health'],
                player_data['mana'],
                player_data['stamina'],
                player_data['current_location'],
                player_data['gold_balance']  # Access gold_balance from player_data
            )
        else:
            await ctx.send("Your player data could not be found.", ephemeral=True)



    # Button Handlers

    @component_callback(re.compile(r"^view_stats_\d+$"))
    async def view_stats_button_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[2])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        await self.send_player_stats(ctx, player_id)

    @component_callback(re.compile(r"^skills_\d+$"))
    async def skills_button_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[1])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        await self.send_player_skills(ctx, player_id)

    @component_callback(re.compile(r"^travel_\d+$"))
    async def travel_button_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[1])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        # Use self.bot.db to access the database
        db = self.bot.db
        player_id = await db.get_or_create_player(ctx.author.id)
        player_data = await db.fetch_player_details(player_id)
    
        logging.info(f"Player Data: {player_data}")
        if player_data:
            current_location_id = player_data['current_location']
            travel_system = self.bot.travel_system  # Access the TravelSystem instance directly
            if travel_system:
                await travel_system.display_locations(ctx, current_location_id)
            else:
                await ctx.send("Travel system is not available.", ephemeral=True)
        else:
            await ctx.send("Your player data could not be found.", ephemeral=True)

    @component_callback(re.compile(r"^inventory_\d+$"))
    async def inventory_button_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[1])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        inventory_system = self.bot.inventory_system  # Access InventorySystem directly
        if inventory_system:
            player_id = await self.bot.db.get_or_create_player(ctx.author.id)
            await inventory_system.display_inventory(ctx, player_id)
        else:
            await ctx.send("Inventory system is not available.", ephemeral=True)
            

    @component_callback(re.compile(r"^bank_\d+$"))
    async def bank_button_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[1])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)

        # Fetch items currently in the bank
        bank_items = await self.bot.db.fetch("""
            SELECT inv.inventoryid, inv.quantity, inv.isequipped,
                   COALESCE(i.name, cf.fish_name) AS item_name, cf.length, cf.weight, cf.rarity
            FROM inventory inv
            LEFT JOIN items i ON inv.itemid = i.itemid
            LEFT JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1 AND inv.in_bank = TRUE
        """, player_id)

        if not bank_items:
            return await ctx.send("Bank is empty.", ephemeral=True)

        # Build detailed bank inventory display
        bank_view = ""
        for item in bank_items:
            if item['item_name']:
                if item['length'] and item['weight']:
                    bank_view += f"{item['item_name']} (Rarity: {item['rarity']}, Length: {item['length']} cm, Weight: {item['weight']} kg)\n"
                else:
                    bank_view += f"{item['item_name']} (x{item['quantity']})"
                if item['isequipped']:
                    bank_view += " - Equipped"
                bank_view += "\n"

        # Adding equip, unequip, drop, and transfer buttons
        '''equip_button = Button(style=ButtonStyle.SUCCESS, label="Equip Item", custom_id=f"equip_item_{player_id}")
        unequip_button = Button(style=ButtonStyle.DANGER, label="Unequip Item", custom_id=f"unequip_item_{player_id}")
        drop_button = Button(style=ButtonStyle.DANGER, label="Drop Item", custom_id=f"drop_item_{player_id}")
        transfer_to_inventory_buttons = Button(style=ButtonStyle.SECONDARY, label="Transfer to Inventory", custom_id=f"transfer_to_inventory_{player_id}")
        transfer_to_bank_buttons = Button(style=ButtonStyle.SECONDARY, label="Transfer to Bank", custom_id=f"transfer_to_bank_{ctx.author.id}")
        
        components = [[equip_button, unequip_button, drop_button, transfer_to_inventory_buttons, transfer_to_bank_buttons]]'''

        # Send the bank inventory content and appropriate buttons
        await ctx.send(content=bank_view, ephemeral=True)


    @component_callback(re.compile(r"^quests_\d+$"))
    async def quests_button_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[1])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)

        # Fetch the active quests from player_quests table
        active_quests = await self.bot.db.fetch("""
            SELECT q.name, q.description
            FROM player_quests pq
            JOIN quests q ON pq.quest_id = q.quest_id
            WHERE pq.player_id = $1 AND pq.status = 'in_progress'
        """, player_id)

        # Create an embed to display the quests
        if active_quests:
            embed = Embed(
                title="Active Quests",
                description="Here are your current active quests:",
                color=0x00FF00
            )
            for quest in active_quests:
                embed.add_field(name=quest['name'], value=quest['description'], inline=False)

            await ctx.send(embeds=[embed], ephemeral=True)
        else:
            await ctx.send("You currently have no active quests.", ephemeral=True)

    @component_callback(re.compile(r"^travel_to_\d+$"))
    async def travel_to_button_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[2])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        # Use self.bot.db to access the database
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        player_data = await self.bot.db.fetch_player_details(player_id)

        if player_data:
            current_location_id = player_data['current_location']
        
            # Fetch accessible locations using self.bot.db
            accessible_locations = await self.bot.db.fetch_accessible_locations(current_location_id)

            if not accessible_locations:
                await ctx.send("No locations available to travel to from here.", ephemeral=True)
                return

            # Create buttons for each accessible location
            location_buttons = [
                Button(style=ButtonStyle.PRIMARY, label=location['name'], custom_id=f"travel_{location['locationid']}_{original_user_id}")
                for location in accessible_locations
            ]

            # Arrange buttons in rows of up to 5
            button_rows = [location_buttons[i:i + 5] for i in range(0, len(location_buttons), 5)]

            # Send the location buttons
            await ctx.send("Please select a destination:", components=button_rows, ephemeral=True)
        else:
            await ctx.send("Your player data could not be found.", ephemeral=True)


    @component_callback(re.compile(r"^fish_\d+$"))
    async def fish_button_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[1])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)  # Acknowledge the interaction to prevent expiration

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        player_data = await self.bot.db.fetch_player_details(player_id)
        current_location_id = player_data['current_location']
        await self.bot.fishing_module.fish_button_action(current_location_id, ctx)



    @component_callback(re.compile(r"^shop_\d+$"))
    async def shop_button_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[1])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)  # Acknowledge the interaction to prevent expiration

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        player_data = await self.bot.db.fetch_player_details(player_id)

        current_location = player_data['current_location']

        # Access the shop_manager through the bot instance
        if hasattr(self.bot, "shop_manager") and self.bot.shop_manager:
            await self.bot.shop_manager.handle_shop(ctx, player_data)
        else:
            await ctx.send("Shop system is not available.", ephemeral=True)


    @component_callback(re.compile(r"^travel_\d+_\d+$"))
    async def travel_destination_handler(self, ctx: ComponentContext):
        parts = ctx.custom_id.split("_")
        location_id = int(parts[1])
        original_user_id = int(parts[2])

        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        # Use self.bot.db to access the database
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        await self.bot.db.update_player_location(player_id, location_id)
        new_location_name = await self.bot.db.fetchval("SELECT name FROM locations WHERE locationid = $1", location_id)

        await ctx.send(f"You have traveled to {new_location_name}.", ephemeral=True)

        # Fetch player details along with the gold balance in a single query
        player_data = await self.bot.db.fetchrow("""
            SELECT pd.health, pd.mana, pd.stamina, l.name AS location_name, pd.current_location, pd.gold_balance
            FROM player_data pd
            JOIN locations l ON l.locationid = pd.current_location
            WHERE pd.playerid = $1
        """, player_id)

        await self.send_player_ui(
            ctx,
            player_data['location_name'],
            player_data['health'],
            player_data['mana'],
            player_data['stamina'],
            player_data['current_location'],
            player_data['gold_balance']  # Pass the gold balance here
        )


    async def send_quest_details(self, ctx, quest_id):
        db = self.bot.db
        quest = await db.fetchrow("SELECT * FROM quests WHERE quest_id = $1", quest_id)

        if quest:
            embed = Embed(
                title=f"Quest: {quest['name']}",
                description=quest['description'],
                color=0x00FF00
            )

            # Add XP Reward details
            fishing_xp_reward = quest['fishing_xp_reward']
            if fishing_xp_reward > 0:
                embed.add_field(name="Fishing XP Reward", value=f"{fishing_xp_reward} XP", inline=False)

            # Add other rewards if applicable (e.g., items, general XP)
            await ctx.send(embeds=[embed])
        else:
            await ctx.send("Quest not found.", ephemeral=True)
            
    
    @component_callback(re.compile(r"^party_create_\d+$"))
    async def party_create_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[2])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        await self.bot.party_system.create_party(ctx, player_id)

    @component_callback(re.compile(r"^party_info_\d+$"))
    async def party_info_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[2])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        await self.bot.party_system.show_party_info(ctx, player_id)

    @component_callback(re.compile(r"^party_invite_\d+$"))
    async def party_invite_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[2])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        await self.bot.party_system.show_invite_menu(ctx, player_id)

    @component_callback(re.compile(r"^party_leave_\d+$"))
    async def party_leave_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[2])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        await self.bot.party_system.leave_party(ctx, player_id)

    @component_callback(re.compile(r"^party_ready_\d+$"))
    async def party_ready_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[2])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        await self.bot.party_system.toggle_ready_status(ctx, player_id)

    @component_callback(re.compile(r"^party_disband_\d+$"))
    async def party_disband_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[2])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        await self.bot.party_system.disband_party(ctx, player_id)


# Setup function to load this as an extension
def setup(bot):
    playerinterface(bot)
