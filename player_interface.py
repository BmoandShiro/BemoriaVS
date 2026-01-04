import re
from interactions import ButtonStyle, Embed, Button, Client, Extension, slash_command, SlashContext, component_callback, ComponentContext, ActionRow
from functools import partial
import logging
import math
import json
from inventory_systems import InventorySystem  # Import the InventorySystem
import random
#from Shop_Manager import ShopManager

class playerinterface(Extension):
    def __init__(self, bot):
        self.bot = bot
        

    async def send_player_ui(self, ctx, location_name, health, mana, stamina, current_location_id, gold_balance):
        db = self.bot.db
        player_id = await db.get_or_create_player(ctx.author.id)
        
        # Check if player is in combat - get the most recent active battle
        battle_instance = await db.fetchrow("""
            SELECT bi.instance_id 
            FROM battle_instances bi
            JOIN battle_participants bp ON bi.instance_id = bp.instance_id
            WHERE bp.player_id = $1 
            AND bi.is_active = true
            ORDER BY bi.created_at DESC
            LIMIT 1
        """, player_id)
        
        if battle_instance:
            # Player is in combat - show combat UI
            await self.send_combat_ui(ctx, player_id, battle_instance['instance_id'])
            return
    
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
        # Exclude party button from modification
        dynamic_buttons = [
            Button(style=button.style, label=button.label, custom_id=f"{button.custom_id}_{user_id}")
            for button in dynamic_buttons
            if not button.custom_id.startswith("party_menu_")
        ]

        # Add party button separately
        party_button = Button(
            style=ButtonStyle.PRIMARY,
            label="Party",
            custom_id=f"party_menu_{player_id}"
        )
        dynamic_buttons.insert(0, party_button)

        # Arrange static and dynamic buttons in rows of up to 5 each
        all_buttons = static_buttons + dynamic_buttons
        button_rows = [all_buttons[i:i + 5] for i in range(0, len(all_buttons), 5)]

        # Send the embed with the buttons arranged in rows
        await ctx.send(embeds=[embed], components=button_rows, ephemeral=False)
    
    async def send_combat_ui(self, ctx, player_id, instance_id):
        """Display combat UI when player is in battle."""
        battle_system = self.bot.get_ext("Battle_System")
        if not battle_system:
            await ctx.send("Error: Battle system not found.", ephemeral=True)
            return
        
        # Get battle state
        battle_state = await battle_system.get_instance_state(instance_id)
        if not battle_state:
            await ctx.send("Error: Could not retrieve battle state.", ephemeral=True)
            return
        
        # Get location information
        location_data = await self.bot.db.fetchrow("""
            SELECT l.name, l.locationid
            FROM player_data pd
            JOIN locations l ON l.locationid = pd.current_location
            WHERE pd.playerid = $1
        """, player_id)
        location_name = location_data['name'] if location_data else "Unknown Location"
        
        # Get current turn player - for solo battles, always allow actions
        current_turn_player = await battle_system.get_current_turn_player(instance_id)
        # For solo battles or if no turn system, allow player to act
        is_solo = battle_state.get('instance_type') == 'solo'
        is_my_turn = is_solo or (current_turn_player == player_id) or (current_turn_player is None)
        
        # Get player's participant data
        participant = next((p for p in battle_state['participants'] if p['player_id'] == player_id), None)
        if not participant:
            await ctx.send("Error: You are not a participant in this battle.", ephemeral=True)
            return
        
        # Create combat embed
        embed = Embed(
            title="⚔️ Battle in Progress",
            description=f"You are currently in combat at **{location_name}**!" + (" **It's your turn!**" if is_my_turn else " Waiting for your turn..."),
            color=0xFF0000
        )
        
        # Add all party members' status
        for p in battle_state['participants']:
            try:
                p_discord_id = await self.bot.db.fetchval("""
                    SELECT discord_id FROM players WHERE playerid = $1
                """, p['player_id'])
                if p_discord_id:
                    p_user = await self.bot.fetch_user(p_discord_id)
                    p_name = p_user.display_name if p_user else f"Player {p['player_id']}"
                else:
                    p_name = f"Player {p['player_id']}"
            except:
                p_name = f"Player {p['player_id']}"
            
            is_current_turn = " 👈" if p['player_id'] == current_turn_player else ""
            status_icon = "💀" if p['current_health'] <= 0 else "❤️"
            is_me = " (You)" if p['player_id'] == player_id else ""
            embed.add_field(
                name=f"{p_name}{is_me}{is_current_turn}",
                value=f"{status_icon} Health: {p['current_health']}\n✨ Mana: {p['current_mana']}",
                inline=True
            )
        
        # Add all enemies' status
        for battle_enemy in battle_state['enemies']:
            if battle_enemy['current_health'] > 0:
                enemy_data = await self.bot.db.fetchrow("""
                    SELECT * FROM enemies WHERE enemyid = $1
                """, battle_enemy['enemy_id'])
                if enemy_data:
                    status_icon = "💀" if battle_enemy['current_health'] <= 0 else "👹"
                    embed.add_field(
                        name=f"{enemy_data['name']}",
                        value=f"{status_icon} Health: {battle_enemy['current_health']}",
                        inline=True
                    )
        
        # Create action buttons - always show if player is alive, but indicate if it's not their turn
        buttons = None
        if participant['current_health'] > 0:
            buttons = ActionRow(
                Button(
                    style=ButtonStyle.PRIMARY,
                    label="Attack",
                    custom_id=f"attack_select_{player_id}",
                    disabled=not is_my_turn
                ),
                Button(
                    style=ButtonStyle.SECONDARY,
                    label="Use Ability",
                    custom_id=f"ability_select_{player_id}",
                    disabled=not is_my_turn
                ),
                Button(
                    style=ButtonStyle.SUCCESS,
                    label="Use Item",
                    custom_id=f"use_item_combat_{player_id}",
                    disabled=not is_my_turn
                ),
                Button(
                    style=ButtonStyle.DANGER,
                    label="Flee Battle",
                    custom_id=f"flee_{player_id}"
                )
            )
        
        # Send combat UI
        if buttons:
            await ctx.send(embeds=[embed], components=[buttons], ephemeral=False)
        else:
            await ctx.send(embeds=[embed], ephemeral=False)





    import logging

    async def get_location_based_buttons(self, location_id, player_id):
        db = self.bot.db
        logging.info(f"Fetching location-based buttons for location_id: {location_id}, player_id: {player_id}")

        # Get location-based commands
        commands = await db.fetch("""
            SELECT command_name, button_label, custom_id, button_color, condition, required_quest_id, required_quest_status, required_item_id
            FROM location_commands
            WHERE locationid = $1
        """, location_id)

        buttons = []
        logging.info(f"Fetched {len(commands)} commands for location_id {location_id}")

        # Process each command and create buttons
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

            # Adjust custom_id generation for dynamic NPC buttons
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

        # Get player data - send_player_ui will check for combat and show appropriate UI
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

            # Add button to view completed quests
            button = Button(
                style=ButtonStyle.SECONDARY,
                label="Completed Quests",
                custom_id=f"completed_quests_{original_user_id}"
            )
            await ctx.send(embeds=[embed], components=[button], ephemeral=True)
        else:
            # Still show the button even if no active quests
            button = Button(
                style=ButtonStyle.SECONDARY,
                label="Completed Quests",
                custom_id=f"completed_quests_{original_user_id}"
            )
            await ctx.send("You currently have no active quests.", components=[button], ephemeral=True)

    @component_callback(re.compile(r"^completed_quests_\d+$"))
    async def completed_quests_button_handler(self, ctx: ComponentContext):
        original_user_id = int(ctx.custom_id.split("_")[2])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)

        # Fetch the completed quests from player_quests table
        completed_quests = await self.bot.db.fetch("""
            SELECT q.name, q.description
            FROM player_quests pq
            JOIN quests q ON pq.quest_id = q.quest_id
            WHERE pq.player_id = $1 AND pq.status = 'completed'
            ORDER BY q.name
        """, player_id)

        # Create an embed to display the completed quests
        if completed_quests:
            embed = Embed(
                title="Completed Quests",
                description="Here are all your completed quests:",
                color=0xFFD700  # Gold color for completed quests
            )
            for quest in completed_quests:
                embed.add_field(
                    name=f"✅ {quest['name']}", 
                    value=quest['description'], 
                    inline=False
                )

            await ctx.send(embeds=[embed], ephemeral=True)
        else:
            await ctx.send("You have not completed any quests yet.", ephemeral=True)

    @component_callback(re.compile(r"^task_board_quest_[123]$"))
    async def task_board_quest_handler(self, ctx: ComponentContext):
        """Handle Task Board quest button clicks."""
        # Extract quest number from custom_id (e.g., "task_board_quest_1" -> "1")
        quest_num = ctx.custom_id.split("_")[-1]
        
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        
        # Verify player is at Task Board location
        player_location = await self.bot.db.fetchval("""
            SELECT current_location FROM player_data WHERE playerid = $1
        """, player_id)
        
        task_board_id = await self.bot.db.fetchval("""
            SELECT locationid FROM locations WHERE name = 'Task Board'
        """)
        
        if player_location != task_board_id:
            await ctx.send("You must be at the Task Board to accept quests.", ephemeral=True)
            return
        
        # Placeholder: Quest not implemented yet
            await ctx.send(
                f"Quest {quest_num} is not yet available. Check back soon!",
                ephemeral=True
            )

    @component_callback(re.compile(r"^open_player_locatinator_\d+$"))
    async def open_player_locatinator_handler(self, ctx: ComponentContext):
        """Handle opening the Player Locatinator from the location button."""
        # Extract user ID from custom_id
        original_user_id = int(ctx.custom_id.split("_")[-1])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return
        
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        
        # Verify player is at Ferns Grimoires
        player_location = await self.bot.db.fetchval("""
            SELECT current_location FROM player_data WHERE playerid = $1
        """, player_id)
        
        ferns_location_id = await self.bot.db.fetchval("""
            SELECT locationid FROM locations WHERE name ILIKE '%ferns grimoires%' OR name ILIKE '%fern%grimoire%'
        """)
        
        if player_location != ferns_location_id:
            await ctx.send("You must be at Fern's Grimoires to use the Player Locatinator.", ephemeral=True)
            return
        
        # Show player locator interface
        await self.show_player_locator(ctx, player_id)

    async def show_player_locator(self, ctx, player_id):
        """Display all players with their location, HP, mana, and stamina."""
        # Get all players with their current stats
        all_players = await self.bot.db.fetch("""
            SELECT 
                pd.playerid,
                pd.health,
                pd.mana,
                pd.stamina,
                l.name AS location_name,
                players.discord_id
            FROM player_data pd
            JOIN locations l ON l.locationid = pd.current_location
            JOIN players ON players.playerid = pd.playerid
            ORDER BY l.name, pd.playerid
        """)
        
        if not all_players:
            await ctx.send("No players found in the server.", ephemeral=True)
            return
        
        # Create embed with player information
        embed = Embed(
            title="Player Locatinator",
            description="Viewing all players in the server:",
            color=0x00FF00
        )
        
        # Group by location for better organization
        players_by_location = {}
        for player in all_players:
            location = player['location_name']
            if location not in players_by_location:
                players_by_location[location] = []
            players_by_location[location].append(player)
        
        # Add fields for each location
        for location, players in sorted(players_by_location.items()):
            player_list = []
            for p in players:
                try:
                    user = await self.bot.fetch_user(p['discord_id'])
                    player_name = user.display_name if user else f"Player {p['playerid']}"
                except:
                    player_name = f"Player {p['playerid']}"
                
                player_list.append(
                    f"**{player_name}** - HP: {p['health']}, Mana: {p['mana']}, Stamina: {p['stamina']}"
                )
            
            # Discord embed fields have a 1024 character limit, so split if needed
            field_value = "\n".join(player_list)
            if len(field_value) > 1024:
                # Split into multiple fields if too long
                chunks = [player_list[i:i+10] for i in range(0, len(player_list), 10)]
                for i, chunk in enumerate(chunks):
                    embed.add_field(
                        name=f"{location} (Part {i+1})" if i > 0 else location,
                        value="\n".join(chunk),
                        inline=False
                    )
            else:
                embed.add_field(
                    name=location,
                    value=field_value,
                    inline=False
                )
        
        await ctx.send(embeds=[embed], ephemeral=True)

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
        
            # Fetch accessible locations using self.bot.db (pass player_id to check requirements)
            accessible_locations = await self.bot.db.fetch_accessible_locations(current_location_id, player_id)

            if not accessible_locations:
                await ctx.send("No locations available to travel to from here.", ephemeral=True)
                return

            # Create buttons for each accessible location
            # Check requirements and style buttons accordingly
            location_buttons = []
            for location in accessible_locations:
                # Check if player meets requirements
                player_id = await self.bot.db.get_or_create_player(ctx.author.id)
                player_data = await self.bot.db.fetchrow("""
                    SELECT pd.xp, pd.playerid
                    FROM player_data pd
                    WHERE pd.playerid = $1
                """, player_id)
                
                has_required_item = True
                meets_xp = True
                meets_skills = True
                meets_quest = True
                
                if location.get('required_item_id'):
                    if location.get('required_item_equipped'):
                        # Check if item is equipped
                        has_item = await self.bot.db.fetchval("""
                            SELECT COUNT(*) > 0
                            FROM inventory
                            WHERE playerid = $1 AND itemid = $2 AND isequipped = TRUE
                        """, player_id, location['required_item_id'])
                        has_required_item = has_item if has_item else False
                    else:
                        # Check if item is in inventory (not equipped)
                        has_item = await self.bot.db.fetchval("""
                            SELECT COUNT(*) > 0
                            FROM inventory
                            WHERE playerid = $1 AND itemid = $2 AND (isequipped = FALSE OR isequipped IS NULL)
                        """, player_id, location['required_item_id'])
                        has_required_item = has_item if has_item else False
                
                if location.get('xp_requirement') and player_data:
                    meets_xp = player_data['xp'] >= location['xp_requirement']
                
                # Check quest requirement
                if location.get('required_quest_id'):
                    quest_completed = await self.bot.db.fetchval("""
                        SELECT EXISTS(
                            SELECT 1 FROM player_quests
                            WHERE player_id = $1 AND quest_id = $2 AND status = 'completed'
                        )
                    """, player_id, location['required_quest_id'])
                    meets_quest = quest_completed if quest_completed is not None else False
                
                # Check skill requirements if needed
                if player_data:
                    skill_check = await self.bot.db.fetchval("""
                        SELECT NOT EXISTS (
                            SELECT 1
                            FROM location_skill_requirements lsr
                            LEFT JOIN player_skills_xp ps ON ps.playerid = $1
                            WHERE lsr.locationid = $2
                            AND CASE 
                                WHEN lsr.skill_id = 1 THEN ps.fire_magic_xp >= lsr.required_level
                                WHEN lsr.skill_id = 2 THEN ps.water_magic_xp >= lsr.required_level
                                WHEN lsr.skill_id = 3 THEN ps.earth_magic_xp >= lsr.required_level
                                WHEN lsr.skill_id = 4 THEN ps.air_magic_xp >= lsr.required_level
                                ELSE FALSE
                            END = FALSE
                        )
                    """, player_id, location['locationid'])
                    meets_skills = skill_check if skill_check is not None else True
                
                # Determine button style based on requirements
                can_travel = has_required_item and meets_xp and meets_skills and meets_quest
                button_style = ButtonStyle.PRIMARY if can_travel else ButtonStyle.SECONDARY
                
                # Add indicator to label if requirements not met
                label = location['name']
                if not can_travel:
                    if not has_required_item:
                        label = f"{location['name']} 🔒"
                    elif not meets_quest:
                        label = f"{location['name']} 📜"
                    elif not meets_xp:
                        label = f"{location['name']} ⚠️"
                
                location_buttons.append(
                    Button(
                        style=button_style, 
                        label=label, 
                        custom_id=f"travel_location_{location['locationid']}_{original_user_id}",
                        disabled=not can_travel
                    )
                )

            # Arrange buttons in rows of up to 5
            button_rows = [location_buttons[i:i + 5] for i in range(0, len(location_buttons), 5)]

            # Send the location buttons
            await ctx.send("Please select a destination:", components=button_rows, ephemeral=True)
        else:
            await ctx.send("Your player data could not be found.", ephemeral=True)


    @component_callback(re.compile(r"^travel_location_\d+_\d+$"))
    async def travel_location_handler(self, ctx: ComponentContext):
        """Handle clicking a specific travel destination button."""
        parts = ctx.custom_id.split("_")
        location_id = int(parts[2])
        original_user_id = int(parts[3])
        
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return
        
        await ctx.defer(ephemeral=True)
        
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        player_data = await self.bot.db.fetchrow("""
            SELECT pd.current_location, pd.xp, pd.playerid
            FROM player_data pd
            WHERE pd.playerid = $1
        """, player_id)
        
        if not player_data:
            await ctx.send("Your player data could not be found.", ephemeral=True)
            return
        
        # Get location details
        location = await self.bot.db.fetchrow("""
            SELECT locationid, name, required_item_id, xp_requirement, required_quest_id, required_item_equipped
            FROM locations
            WHERE locationid = $1
        """, location_id)
        
        if not location:
            await ctx.send("Location not found.", ephemeral=True)
            return
        
        # Check if path exists
        path_exists = await self.bot.db.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM paths
                WHERE from_location_id = $1 AND to_location_id = $2
            )
        """, player_data['current_location'], location_id)
        
        if not path_exists:
            await ctx.send("There is no path to this location from your current location.", ephemeral=True)
            return
        
        # Check requirements
        has_required_item = True
        if location['required_item_id']:
            if location.get('required_item_equipped'):
                # Check if item is equipped (in any slot)
                has_item = await self.bot.db.fetchval("""
                    SELECT COUNT(*) > 0
                    FROM inventory
                    WHERE playerid = $1 AND itemid = $2 AND isequipped = TRUE
                """, player_id, location['required_item_id'])
                has_required_item = has_item if has_item else False
                
                if not has_required_item:
                    item_name = await self.bot.db.fetchval("""
                        SELECT name FROM items WHERE itemid = $1
                    """, location['required_item_id'])
                    await ctx.send(
                        f"You must have **{item_name or 'a required item'}** equipped to travel to {location['name']}.",
                        ephemeral=True
                    )
                    return
            else:
                # Check if item is in inventory (not equipped)
                has_item = await self.bot.db.fetchval("""
                    SELECT COUNT(*) > 0
                    FROM inventory
                    WHERE playerid = $1 AND itemid = $2 AND (isequipped = FALSE OR isequipped IS NULL)
                """, player_id, location['required_item_id'])
                has_required_item = has_item if has_item else False
                
                if not has_required_item:
                    item_name = await self.bot.db.fetchval("""
                        SELECT name FROM items WHERE itemid = $1
                    """, location['required_item_id'])
                    await ctx.send(
                        f"You need **{item_name or 'a required item'}** to travel to {location['name']}.",
                        ephemeral=True
                    )
                    return
        
        if location['xp_requirement'] and player_data['xp'] < location['xp_requirement']:
            await ctx.send(
                f"You need {location['xp_requirement']} XP to travel to {location['name']}. "
                f"You currently have {player_data['xp']} XP.",
                ephemeral=True
            )
            return
        
        # Check skill requirements
        skill_check = await self.bot.db.fetchval("""
            SELECT EXISTS (
                SELECT 1
                FROM location_skill_requirements lsr
                LEFT JOIN player_skills_xp ps ON ps.playerid = $1
                WHERE lsr.locationid = $2
                AND CASE 
                    WHEN lsr.skill_id = 1 THEN ps.fire_magic_xp >= lsr.required_level
                    WHEN lsr.skill_id = 2 THEN ps.water_magic_xp >= lsr.required_level
                    WHEN lsr.skill_id = 3 THEN ps.earth_magic_xp >= lsr.required_level
                    WHEN lsr.skill_id = 4 THEN ps.air_magic_xp >= lsr.required_level
                    ELSE FALSE
                END = FALSE
            )
        """, player_id, location_id)
        
        if skill_check:
            await ctx.send(
                f"You do not meet the skill requirements to travel to {location['name']}.",
                ephemeral=True
            )
            return
        
        # Check quest requirement
        if location['required_quest_id']:
            quest_completed = await self.bot.db.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM player_quests
                    WHERE player_id = $1 AND quest_id = $2 AND status = 'completed'
                )
            """, player_id, location['required_quest_id'])
            
            if not quest_completed:
                quest_name = await self.bot.db.fetchval("""
                    SELECT name FROM quests WHERE quest_id = $1
                """, location['required_quest_id'])
                await ctx.send(
                    f"You must complete the quest **{quest_name or 'a required quest'}** to travel to {location['name']}.",
                    ephemeral=True
                )
                return
        
        # Check if player is in a party
        party = await self.bot.db.fetchrow("""
            SELECT p.*, pm.role
            FROM parties p
            JOIN party_members pm ON p.party_id = pm.party_id
            WHERE pm.player_id = $1 AND p.is_active = true
        """, player_id)
        
        if party:
            if party['leader_id'] == player_id:
                # Leader can move party - travel_party will handle the UI refresh
                await self.bot.travel_system.travel_party(ctx, player_id, location['name'], party['party_id'])
                # After party travel, refresh UI for the leader
                player_data = await self.bot.db.fetchrow("""
                    SELECT pd.health, pd.mana, pd.stamina, l.name AS location_name, pd.current_location, pd.gold_balance
                    FROM player_data pd
                    JOIN locations l ON l.locationid = pd.current_location
                    WHERE pd.playerid = $1
                """, player_id)
                if player_data:
                    await self.send_player_ui(
                        ctx,
                        player_data['location_name'],
                        player_data['health'],
                        player_data['mana'],
                        player_data['stamina'],
                        player_data['current_location'],
                        player_data['gold_balance']
                    )
            else:
                await ctx.send(
                    "You are in a party! Only the party leader can initiate travel. "
                    "Ask your party leader to move the party, or leave the party to travel solo.",
                    ephemeral=True
                )
            return
        
        # Solo travel - update location
        await self.bot.db.update_player_location(player_id, location_id)
        
        # Fetch updated player details to refresh the UI
        player_data = await self.bot.db.fetchrow("""
            SELECT pd.health, pd.mana, pd.stamina, l.name AS location_name, pd.current_location, pd.gold_balance
            FROM player_data pd
            JOIN locations l ON l.locationid = pd.current_location
            WHERE pd.playerid = $1
        """, player_id)
        
        if player_data:
            # Refresh the player UI with updated location
            await self.send_player_ui(
                ctx,
                player_data['location_name'],
                player_data['health'],
                player_data['mana'],
                player_data['stamina'],
                player_data['current_location'],
                player_data['gold_balance']
            )
        else:
            await ctx.send(f"You have successfully traveled to **{location['name']}**.", ephemeral=True)

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
        
        # Check if player is in a party
        party = await self.bot.db.fetchrow("""
            SELECT p.*, pm.role
            FROM parties p
            JOIN party_members pm ON p.party_id = pm.party_id
            WHERE pm.player_id = $1 AND p.is_active = true
        """, player_id)

        if party:
            # If player is party leader, move entire party
            if party['leader_id'] == player_id:
                new_location_name = await self.bot.db.fetchval("SELECT name FROM locations WHERE locationid = $1", location_id)
                
                # Get location details to check requirements
                location_details = await self.bot.db.fetchrow("""
                    SELECT locationid, name, required_item_id, required_item_equipped
                    FROM locations
                    WHERE locationid = $1
                """, location_id)
                
                # Get all party members
                party_members = await self.bot.db.fetch("""
                    SELECT pm.player_id, players.discord_id
                    FROM party_members pm
                    JOIN players ON pm.player_id = players.playerid
                    WHERE pm.party_id = $1
                """, party['party_id'])

                # Check if location requires an equipped item - if so, verify all party members have it equipped
                if location_details and location_details['required_item_id'] and location_details.get('required_item_equipped'):
                    item_name = await self.bot.db.fetchval("""
                        SELECT name FROM items WHERE itemid = $1
                    """, location_details['required_item_id'])
                    
                    missing_members = []
                    for member in party_members:
                        has_item_equipped = await self.bot.db.fetchval("""
                            SELECT COUNT(*) > 0
                            FROM inventory
                            WHERE playerid = $1 AND itemid = $2 AND isequipped = TRUE
                        """, member['player_id'], location_details['required_item_id'])
                        
                        if not has_item_equipped:
                            try:
                                member_user = await self.bot.fetch_user(member['discord_id'])
                                member_name = member_user.display_name if member_user else f"Player {member['player_id']}"
                            except:
                                member_name = f"Player {member['player_id']}"
                            missing_members.append(member_name)
                    
                    if missing_members:
                        member_list = ", ".join(missing_members)
                        await ctx.send(
                            f"❌ Cannot travel to **{location_details['name']}**! All party members must have **{item_name}** equipped.\n\n"
                            f"Missing equipped item: {member_list}",
                            ephemeral=True
                        )
                        return

                # Update location for all party members
                moved_count = 0
                for member in party_members:
                    await self.bot.db.update_player_location(member['player_id'], location_id)
                    moved_count += 1
                    
                    # Notify each party member (except leader)
                    if member['player_id'] != player_id:
                        try:
                            member_user = await self.bot.fetch_user(member['discord_id'])
                            if member_user:
                                await member_user.send(f"🎯 Your party leader has moved the party to **{new_location_name}**!")
                        except:
                            pass  # Silently fail if can't DM member

                await ctx.send(
                    f"✅ Party successfully traveled to **{new_location_name}**! "
                    f"All {moved_count} party member(s) have been moved.",
                    ephemeral=True
                )
            else:
                # Non-leaders cannot travel solo
                await ctx.send(
                    "You are in a party! Only the party leader can initiate travel. "
                    "Ask your party leader to move the party, or leave the party to travel solo.",
                    ephemeral=True
                )
                return
        else:
            # Solo travel (no party)
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


    @component_callback(re.compile(r"^party_menu_\d+$"))
    async def party_menu_handler(self, ctx: ComponentContext):
        # Extract player ID from the custom_id
        player_id = int(ctx.custom_id.split("_")[2])
        
        # Get the Discord ID for this player_id
        discord_id = await self.bot.db.get_discord_id(player_id)
        
        # Check authorization
        if ctx.author.id != discord_id:
            await ctx.send("You are not authorized to use this button.", ephemeral=True)
            return

        # Get the party system
        party_system = self.bot.get_ext("Party_System")
        if not party_system:
            await ctx.send("Party system is not available right now.", ephemeral=True)
            return

        # Create buttons based on party status
        buttons = []
        
        # Check if player is in a party
        party_info = await party_system.get_player_party_info(player_id)
        
        if not party_info:
            # Player is not in a party
            buttons.append(
                Button(
                    style=ButtonStyle.SUCCESS,
                    label="Create Party",
                    custom_id=f"party_create_{player_id}"
                )
            )
        else:
            # Player is in a party
            buttons.append(
                Button(
                    style=ButtonStyle.PRIMARY,
                    label="Party Info",
                    custom_id=f"party_info_{player_id}"
                )
            )
            
            # All party members can invite
            buttons.append(
                Button(
                    style=ButtonStyle.SUCCESS,
                    label="Invite Player",
                    custom_id=f"party_invite_{player_id}"
                )
            )
            
            if party_info['leader_id'] == player_id:
                # Player is the party leader
                buttons.append(
                    Button(
                        style=ButtonStyle.DANGER,
                        label="Disband Party",
                        custom_id=f"party_disband_{player_id}"
                    )
                )
            else:
                # Player is a member
                buttons.append(
                    Button(
                        style=ButtonStyle.DANGER,
                        label="Leave Party",
                        custom_id=f"party_leave_{player_id}"
                    )
                )

        await ctx.send("Party Management:", components=buttons, ephemeral=True)

    

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


# Setup function to load this as an extension
def setup(bot):
    return playerinterface(bot)
