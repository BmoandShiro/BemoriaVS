import re
from interactions import ButtonStyle, Embed, Button, Client, Extension, slash_command, SlashContext, component_callback, ComponentContext
from functools import partial
import logging
import math

class playerinterface(Extension):
    def __init__(self, bot):
        self.bot = bot

    async def send_player_ui(self, ctx, location_name, health, mana, stamina, current_location_id, gold_balance):
        db = self.bot.db
        player_id = await db.get_or_create_player(ctx.author.id)
        
        current_inventory_count = await db.get_current_inventory_count(player_id)
        max_inventory_capacity = await db.get_inventory_capacity(player_id)

        embed = Embed(
            title="Player Information",
            description=f"You are currently in {location_name}",
            color=0x00FF00
        )
        embed.add_field(name="Health", value=str(health), inline=True)
        embed.add_field(name="Mana", value=str(mana), inline=True)
        embed.add_field(name="Stamina", value=str(stamina), inline=True)
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
        dynamic_buttons = await self.get_location_based_buttons(current_location_id)

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

    async def get_location_based_buttons(self, location_id):
        """
        Fetch location-based commands from the database and create buttons for each command.
        """
        db = self.bot.db
        commands = await db.fetch("""
            SELECT command_name, button_label, custom_id
            FROM location_commands
            WHERE locationid = $1
        """, location_id)

        buttons = []
        for command in commands:
            buttons.append(Button(style=ButtonStyle.PRIMARY, label=command['button_label'], custom_id=command['custom_id']))
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

        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        player_data = await self.bot.db.fetch_player_details(player_id)
        current_location_id = player_data['current_location']
        await self.bot.fishing_module.fish_button_action(current_location_id, ctx)

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

# Setup function to load this as an extension
def setup(bot):
    playerinterface(bot)
