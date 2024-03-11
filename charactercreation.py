
import interactions
from interactions import Extension, slash_command, Button, ButtonStyle, ActionRow, ComponentContext, component_callback  
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

    @slash_command(
        name="create_character",
        description="Start creating a new character."
    )
    async def create_character(self, ctx):
        # Assuming you have a method to fetch races from your database
        races = await self.fetch_races()
        select_race_button = Button(
            style=ButtonStyle.PRIMARY,
            label="Select Race",
            custom_id="select_race_button"  # Make sure this custom_id is unique and descriptive
        )
        await ctx.send(
            content="Please select your character's race:",
            components=[ActionRow(select_race_button)]  # Pass the button directly
        )

    async def fetch_races(self):
        # Placeholder function for fetching races
        return [
            {'id': '1', 'name': 'Elf', 'description': 'Wise and agile beings.'},
            {'id': '2', 'name': 'Dwarf', 'description': 'Stout and resilient.'}
            # Add more races as needed
        ]

    
    # you need to pass your custom_id to this decorator
    @component_callback("select_race_button")
    async def my_callback(ctx: ComponentContext):
        await ctx.send("You clicked it!")

def setup(bot):
    CharacterCreation(bot)