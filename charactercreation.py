# charactercreation.py
import interactions
from interactions import Extension, slash_command, Button, ButtonStyle, ActionRow, ComponentContext, component_callback
import re
from psycopg2 import OperationalError
from PostgreSQLlogic import Database
import logging
from config import GUILD_IDS  # Import GUILD_IDS from config.py
from player_interface import playerinterface

logging.basicConfig(level=logging.INFO)

class CharacterCreation(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database(dsn="postgresql://postgres:Oshirothegreat9!@localhost:5432/BMOSRPG")

    @slash_command(name="create_character", description="Start creating a new character.")
    async def create_character(self, ctx):
        races = await self.db.fetch_races()
        buttons = [
            Button(style=ButtonStyle.PRIMARY, label=race['name'], custom_id=f"select_race_{race['raceid']}")
            for race in races
        ]
        components = [ActionRow(*buttons[i:i+5]) for i in range(0, len(buttons), 5)]
        await ctx.send("Please select your character's race:", components=components)

    @component_callback(re.compile(r"select_race_\d+"))
    async def race_button_handler(self, ctx: ComponentContext):
        raceid = int(ctx.custom_id.split('_')[-1])
        discord_id = ctx.author.id
        await self.db.save_player_choice(discord_id, raceid)
        await ctx.send(f"You have chosen race ID: {raceid}", ephemeral=True)
        
        titles = await self.db.fetch_background_titles()
        title_buttons = [
            Button(style=ButtonStyle.PRIMARY, label=title['titlename'], custom_id=f"select_title_{title['titleid']}")
            for title in titles
        ]
        title_components = [ActionRow(*title_buttons[i:i+5]) for i in range(0, len(title_buttons), 5)]
        await ctx.send("Please select your character's title:", components=title_components)
    
    @component_callback(re.compile(r"select_title_\d+"))
    async def title_button_handler(self, ctx: ComponentContext):
        titleid = int(ctx.custom_id.split('_')[-1])
        discord_id = ctx.author.id
        await self.db.save_player_title_choice(discord_id, titleid)
        await ctx.send(f"You have chosen the title ID: {titleid}", ephemeral=True)
        await self.db.set_initial_location(discord_id)

        player_id = await self.db.get_or_create_player(discord_id)
        player_data = await self.db.fetch_player_details(player_id)

        if player_data:
            location_name = player_data['name']
            health = player_data['health']
            mana = player_data['mana']
            stamina = player_data['stamina']
            player_interface = playerinterface(self.bot)
            await player_interface.send_player_ui(ctx, location_name, health, mana, stamina)
        else:
            await ctx.send("Could not load your player details.", ephemeral=True)

def setup(bot):
    CharacterCreation(bot)
