import interactions
from interactions import Extension, slash_command, Button, ButtonStyle, ActionRow, ComponentContext, component_callback, SlashCommand
import re
from interactions.api.events import Component
from psycopg2 import OperationalError
from PostgreSQLlogic import Database
import logging
from player_interface import playerinterface
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

class CharacterCreation(Extension):
    def __init__(self, bot):
        self.bot = bot
        # Use bot.db if available, otherwise create a new connection from env vars
        if hasattr(bot, 'db') and bot.db:
            self.db = bot.db
        else:
            dsn = os.getenv('DATABASE_DSN')
            if not dsn:
                raise ValueError("DATABASE_DSN environment variable is not set")
            self.db = Database(dsn=dsn)

    @slash_command(name="create_character", description="Start creating a new character.")
    async def create_character(self, ctx):
        user_id = ctx.author.id  # Extract the user's Discord ID

        # Fetch races from your database
        races = await self.db.fetch_races()

        # Create a button for each race with the user_id in custom_id
        buttons = [
            Button(style=ButtonStyle.PRIMARY, label=race['name'], custom_id=f"select_race_{race['raceid']}_{user_id}")
            for race in races
        ]
        # Group buttons into action rows if needed
        components = [ActionRow(*buttons[i:i+5]) for i in range(0, len(buttons), 5)]
        await ctx.send("Please select your character's race:", components=components, ephemeral=False)

    @component_callback(re.compile(r"^select_race_\d+_\d+$"))
    async def race_button_handler(self, ctx: ComponentContext):
        # Extract race ID and original user ID from the custom_id of the button clicked
        parts = ctx.custom_id.split('_')
        race_id = int(parts[2])
        original_user_id = int(parts[3])

        # Verify that the user interacting is the original user
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        # Save the player's race choice in the database
        await self.db.save_player_choice(original_user_id, race_id)
    
        # Send confirmation to the player
        await ctx.send(f"You have chosen the race: {race_id}", ephemeral=True)

        # Fetch background titles from your database
        titles = await self.db.fetch_background_titles()

        # Create a button for each title with user_id in the custom_id
        title_buttons = [
            Button(style=ButtonStyle.PRIMARY, label=title['titlename'], custom_id=f"select_title_{title['titleid']}_{original_user_id}")
            for title in titles
        ]
        # Group buttons into action rows if needed
        title_components = [ActionRow(*title_buttons[i:i+5]) for i in range(0, len(title_buttons), 5)]
        await ctx.send("Please select your character's title:", components=title_components, ephemeral=True)

    @component_callback(re.compile(r"^select_title_\d+_\d+$"))
    async def title_button_handler(self, ctx: ComponentContext):
        # Extract title ID and original user ID from the custom_id of the button clicked
        parts = ctx.custom_id.split('_')
        title_id = int(parts[2])
        original_user_id = int(parts[3])

        # Verify that the user interacting is the original user
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        # Save the player's title choice in the database
        await self.db.save_player_title_choice(original_user_id, title_id)
        await ctx.send(f"You have chosen the title: {title_id}", ephemeral=True)

        # Set initial location after character creation is complete
        await self.db.set_initial_location(original_user_id)

        # Now fetch player details to get location_name, health, mana, and stamina
        player_id = await self.db.get_or_create_player(original_user_id)
        player_data = await self.db.fetch_player_details(player_id)

        if player_data:
            # Extract the details from player_data
            location_name = player_data['name']
            health = player_data['health']
            mana = player_data['mana']
            stamina = player_data['stamina']

            await self.db.add_player_skills_xp(player_id)

            await ctx.send(f"Character creation complete! Welcome to {location_name}. Health: {health}, Mana: {mana}, Stamina: {stamina}  /playerui for overview", ephemeral=True)
        else:
            await ctx.send("Could not load your player details.", ephemeral=True)

# Setup function for the bot to load this as an extension
def setup(bot):
    CharacterCreation(bot)
