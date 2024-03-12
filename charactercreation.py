
import interactions
from interactions import Extension, slash_command, Button, ButtonStyle, ActionRow, ComponentContext, component_callback, SlashCommand  
import re
from interactions.api.events import Component
from psycopg2 import OperationalError
from PostgreSQLlogic import Database
import logging

logging.basicConfig(level=logging.INFO)

"""import interactions
print(dir(interactions))"""

class CharacterCreation(Extension):
    def __init__(self, bot):
        self.bot = bot
        # Assume db is an instance of your Database class that's already connected
        self.db = Database(dsn="postgresql://postgres:Oshirothegreat9@localhost:5432/BMOSRPG")

    @slash_command(name="create_character", description="Start creating a new character.")
    async def create_character(self, ctx):
        # Fetch races from your database
        races = await self.db.fetch_races()
        # Create a button for each race
        buttons = [
            Button(style=ButtonStyle.PRIMARY, label=race['name'], custom_id=f"select_race_{race['raceid']}")
            for race in races
        ]
        # Group buttons into action rows if needed
        components = [ActionRow(*buttons[i:i+5]) for i in range(0, len(buttons), 5)]
        await ctx.send("Please select your character's race:", components=components)

    # You will use a decorator from interactions to handle button clicks
    @component_callback(re.compile(r"select_race_\d+"))  # Regex pattern to match custom_id like 'select_race_1', 'select_race_2', etc.
    async def race_button_handler(self, ctx: ComponentContext):
        # Extract race ID from the custom_id of the button clicked
        race_id = int(ctx.custom_id.split('_')[-1])
        # Save the player's Discord ID and race ID to the database
        await self.db.save_player_choice(ctx.author.id, race_id)
        # Respond to the button click
        await ctx.send(f"You have chosen race ID: {race_id}", ephemeral=True)
# Don't forget to add the setup function
# charactercreation.py
def setup(bot):
    CharacterCreation(bot)