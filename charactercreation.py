
import interactions
from interactions import Extension, slash_command, Button, ButtonStyle, ActionRow, ComponentContext, component_callback, SlashCommand  
import re
from interactions.api.events import Component
from psycopg2 import OperationalError
from PostgreSQLlogic import Database
import logging
from player_interface import playerinterface

logging.basicConfig(level=logging.INFO)

"""import interactions
print(dir(interactions))"""

class CharacterCreation(Extension):
    def __init__(self, bot):
        self.bot = bot
        # Assume db is an instance of your Database class that's already connected
        self.db = Database(dsn="postgresql://postgres:Oshirothegreat9!@localhost:5432/BMOSRPG")

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
    @component_callback(re.compile(r"select_race_\d+"))
    async def race_button_handler(self, ctx: ComponentContext):
        # Extract race ID from the custom_id of the button clicked
        raceid = int(ctx.custom_id.split('_')[-1])
        # Extract the player's Discord ID from the context
        discord_id = ctx.author.id
    
        # Save the player's race choice in the database
        await self.db.save_player_choice(discord_id, raceid)
    
        # Send confirmation to the player
        await ctx.send(f"You have chosen race ID: {raceid}", ephemeral=True)
        
        # Fetch background titles from your database
        titles = await self.db.fetch_background_titles()
        # Create a button for each title
        title_buttons = [
            Button(style=ButtonStyle.PRIMARY, label=title['titlename'], custom_id=f"select_title_{title['titleid']}")
            for title in titles
        ]
        # Group buttons into action rows if needed
        title_components = [ActionRow(*title_buttons[i:i+5]) for i in range(0, len(title_buttons), 5)]
        await ctx.send("Please select your character's title:", components=title_components)
    
    # New handler for title button clicks
    @component_callback(re.compile(r"select_title_\d+"))
    async def title_button_handler(self, ctx: ComponentContext):
        # Extract title ID from the custom_id of the button clicked
        titleid = int(ctx.custom_id.split('_')[-1])
        # Extract the player's Discord ID from the context
        discord_id = ctx.author.id
    
        # Save the player's title choice in the database
        await self.db.save_player_title_choice(discord_id, titleid)
        await ctx.send(f"You have chosen the title ID: {titleid}", ephemeral=True)
    
        # Use this method after the player has finished character creation
        await self.db.set_initial_location(discord_id)

        # Now fetch player details to get location_name, health, mana, and stamina
        # This assumes you have a method to get player_id from discord_id
        player_id = await self.db.get_or_create_player(discord_id)
        player_data = await self.db.fetch_player_details(player_id)

        if player_data:
            # Extract the details from player_data
            location_name = player_data['name']
            health = player_data['health']
            mana = player_data['mana']
            stamina = player_data['stamina']

            await self.db.add_player_skills_xp(player_id)

            await ctx.send(f"Character creation complete! Welcome to {location_name}. Health: {health}, Mana: {mana}, Stamina: {stamina}  /playerui for overview")
        else:
            await ctx.send("Could not load your player details.", ephemeral=True)
            

            '''# Instantiate player_interface with bot and send the UI
            player_interface = playerinterface(self.bot)
            await player_interface.send_player_ui(ctx, location_name, health, mana, stamina)
        else:
            await ctx.send("Could not load your player details.", ephemeral=True)'''
    

        
        
        

    
# Don't forget to add the setup function
# charactercreation.py
def setup(bot):
    CharacterCreation(bot)