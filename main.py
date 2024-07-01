from interactions import SlashCommand, Client, Extension, slash_command 
from charactercreation import setup as cc_setup
from charactercreation import CharacterCreation
from PostgreSQLlogic import Database  # Import the Database class
from player_interface import setup as player_interface_setup
from functools import partial
import logging
from config import GUILD_IDS  # Import GUILD_IDS from config.py

logging.basicConfig(level=logging.INFO)

TOKEN = 'MTE3Nzc3MjcyNDE1MjY5Njg1Mg.GmEncj.q1k72hSszveLmlOLde-I1XVvVPAFLBlQAJdKXY'


bot = Client(token=TOKEN)

DATABASE_DSN = "dbname='BMOSRPG' user='postgres' host='localhost' password='Oshirothegreat9!' port='5432'"

db = Database(dsn=DATABASE_DSN)
bot.db = db  # Attach the database instance to the bot object

async def initialize_db():
    logging.info("Connecting to the database...")
    await bot.db.connect()
    logging.info("Database connected.")



# Event listener for when the bot has switched from offline to online.
@bot.event
async def on_ready():
    print(f"Logged in as {bot.me.name}")
    await bot.db.connect()
    
    # Synchronize commands with the guilds specified in GUILD_IDS
    for guild_id in GUILD_IDS:
        await bot.sync_commands(guild_id)


logging.info("Loading extensions...")
# When setting up the bot, make sure the CharacterCreation class is defined to accept a bot and a db instance
cc_setup(bot)  # Pass both the bot and db instances to the setup function
player_interface_setup(bot)

# Start the bot with the specified token
bot.start()  # Note: Use start() instead of run()