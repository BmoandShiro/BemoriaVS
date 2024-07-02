from interactions import SlashCommand, Client, Extension 
from charactercreation import setup as cc_setup
from charactercreation import CharacterCreation
from PostgreSQLlogic import Database  # Import the Database class
from player_interface import setup as player_interface_setup
from functools import partial
import logging
from GuildConfig import GUILD_IDS

logging.basicConfig(level=logging.INFO)

TOKEN = 'MTE3Nzc3MjcyNDE1MjY5Njg1Mg.GmEncj.q1k72hSszveLmlOLde-I1XVvVPAFLBlQAJdKXY'

# Since GUILD_IDS is now a list with one element, we extract the single ID for debug_scope
debug_scope = GUILD_IDS[0]

bot = Client(token=TOKEN, debug_scope=debug_scope)


DATABASE_DSN = "dbname='BMOSRPG' user='postgres' host='localhost' password='Oshirothegreat9!' port='5432'"

db = Database(dsn=DATABASE_DSN)
bot.db = db  # Attach the database instance to the bot object

logging.info("Loading extensions...")
# When setting up the bot, make sure the CharacterCreation class is defined to accept a bot and a db instance
cc_setup(bot)  # Pass both the bot and db instances to the setup function

# Event listener for when the bot has switched from offline to online.
@bot.event
async def on_ready():
    print(f"Logged in as {bot.me.name}")
    await bot.db.connect()
    
# Load your extensions here
player_interface_setup(bot)  # Pass the database instance to the setup function of the player_interface    
bot.load_extension("player_interface")  # Assuming player_interface.py is in the same directory

# Start the bot with the specified token
bot.start()  # Note: Use start() instead of run()