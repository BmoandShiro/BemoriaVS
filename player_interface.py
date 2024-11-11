import re  
from interactions import ButtonStyle, Embed, Button, Client, Extension, slash_command, SlashContext, component_callback, ComponentContext
from functools import partial
import logging
import math


class playerinterface(Extension):
    def __init__(self, bot):
        self.bot = bot

    async def send_player_ui(self, ctx, location_name, health, mana, stamina, current_location_id):
        embed = Embed(
            title="Player Information",
            description=f"You are currently in {location_name}",
            color=0x00FF00
        )
        embed.add_field(name="Health", value=str(health), inline=True)
        embed.add_field(name="Mana", value=str(mana), inline=True)
        embed.add_field(name="Stamina", value=str(stamina), inline=True)

        # Static buttons (including the new "Travel To" button)
        static_buttons = [
            Button(style=ButtonStyle.PRIMARY, label="Travel", custom_id="travel"),
            Button(style=ButtonStyle.PRIMARY, label="Skills", custom_id="skills"),
            Button(style=ButtonStyle.PRIMARY, label="View Stats", custom_id="view_stats"),
            Button(style=ButtonStyle.PRIMARY, label="Inventory", custom_id="inventory"),
            Button(style=ButtonStyle.PRIMARY, label="Quests", custom_id="quests"),
            Button(style=ButtonStyle.PRIMARY, label="Travel To", custom_id="travel_to")  # New button added here
        ]
    
        # Get dynamic buttons based on the current location
        dynamic_buttons = await self.get_location_based_buttons(current_location_id)

        # Arrange static and dynamic buttons in rows of up to 5 each
        all_buttons = static_buttons + dynamic_buttons
        button_rows = [all_buttons[i:i + 5] for i in range(0, len(all_buttons), 5)]

        # Send the embed with the buttons arranged in rows
        await ctx.send(embeds=[embed], components=button_rows)

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
        player_data = await db.fetch_player_details(player_id)

        if player_data:
            await self.send_player_ui(
                ctx,
                player_data['name'],
                player_data['health'],
                player_data['mana'],
                player_data['stamina'],
                player_data['current_location']
            )
        else:
            await ctx.send("Your player data could not be found.", ephemeral=True)

    @component_callback("view_stats")
    async def view_stats_button_handler(self, ctx: ComponentContext):
        db = self.bot.db
        player_id = await db.get_or_create_player(ctx.author.id)
        await self.send_player_stats(ctx, player_id)

    @component_callback("skills")
    async def skills_button_handler(self, ctx: ComponentContext):
        db = self.bot.db
        player_id = await db.get_or_create_player(ctx.author.id)
        await self.send_player_skills(ctx, player_id)

    @component_callback("travel")
    async def travel_button_handler(self, ctx: ComponentContext):
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

    @component_callback("inventory")
    async def inventory_button_handler(self, ctx: ComponentContext):
        inventory_system = self.bot.inventory_system  # Access InventorySystem directly
        if inventory_system:
            player_id = await self.bot.db.get_or_create_player(ctx.author.id)
            await inventory_system.display_inventory(ctx, player_id)
        else:
            await ctx.send("Inventory system is not available.", ephemeral=True)
            
    @component_callback("quests")
    async def quests_button_handler(self, ctx: ComponentContext):
        await ctx.send("Quest functionality coming soon!", ephemeral=True)

    @component_callback("travel_to")
    async def travel_to_button_handler(self, ctx: ComponentContext):
        # This will be the callback for the "Travel To" button
        await ctx.send("Please select a destination using the travel command.", ephemeral=True)
        
    @component_callback("travel_to")
    async def travel_to_button_handler(self, ctx: ComponentContext):
        db = self.bot.db
        player_id = await db.get_or_create_player(ctx.author.id)
        player_data = await db.fetch_player_details(player_id)

        if player_data:
            current_location_id = player_data['current_location']
        
            # Fetch accessible locations
            accessible_locations = await db.fetch_accessible_locations(current_location_id)
        
            if not accessible_locations:
                await ctx.send("No locations available to travel to from here.", ephemeral=True)
                return

            # Create buttons for each accessible location
            location_buttons = [
                Button(style=ButtonStyle.PRIMARY, label=location['name'], custom_id=f"travel_{location['locationid']}")
                for location in accessible_locations
            ]

            # Arrange buttons in rows of up to 5
            button_rows = [location_buttons[i:i + 5] for i in range(0, len(location_buttons), 5)]

            # Send the location buttons
            await ctx.send("Please select a destination:", components=button_rows, ephemeral=True)
        else:
            await ctx.send("Your player data could not be found.", ephemeral=True)
            
    @component_callback("fish")
    async def fish_button_handler(self, ctx: ComponentContext):
        # Get player ID and current location
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        player_data = await self.bot.db.fetch_player_details(player_id)
        current_location_id = player_data['current_location']
    
        # Call fish_button_action with location and ctx
        await self.bot.fishing_module.fish_button_action(current_location_id, ctx)
        # Add handlers for each travel destination button dynamically
        

    @component_callback(re.compile(r"^travel_\d+$"))
    async def travel_destination_handler(self, ctx: ComponentContext):
        location_id = int(ctx.custom_id.split("_")[1])
        db = self.bot.db
        player_id = await db.get_or_create_player(ctx.author.id)
    
        # Update the player's location
        await db.update_player_location(player_id, location_id)
        new_location_name = await db.fetchval("SELECT name FROM locations WHERE locationid = $1", location_id)
    
        await ctx.send(f"You have traveled to {new_location_name}.", ephemeral=True)
        # Optionally, you can reload the UI here to reflect the new location
        player_data = await db.fetch_player_details(player_id)
        await self.send_player_ui(ctx, player_data['name'], player_data['health'], player_data['mana'], player_data['stamina'], player_data['current_location'])
        
        
        

# Setup function to load this as an extension
def setup(bot):
    playerinterface(bot)
