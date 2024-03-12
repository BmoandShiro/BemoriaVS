
from interactions import SlashCommand, Client, Extension 
from charactercreation import setup as cc_setup
from charactercreation import CharacterCreation
from PostgreSQLlogic import Database  # Import the Database class
import logging

logging.basicConfig(level=logging.INFO)

TOKEN = 'MTE3Nzc3MjcyNDE1MjY5Njg1Mg.GmEncj.q1k72hSszveLmlOLde-I1XVvVPAFLBlQAJdKXY'

bot = Client(token=TOKEN)

DATABASE_DSN = "dbname='BMOSRPG' user='postgres' host='localhost' password='your_password' port='5432'"

db = Database(dsn=DATABASE_DSN)


logging.info("Loading extensions...")
# When setting up the bot, make sure the CharacterCreation class is defined to accept a bot and a db instance
cc_setup(bot)  # Pass both the bot and db instances to the setup function

# Event listener for when the bot has switched from offline to online.
@bot.event
async def on_ready():
    print(f'Logged in as {bot.me.name} (ID: {bot.me.id})')  # Note: bot.me is used instead of bot.user
    print('------')


# Start the bot with the specified token
bot.start()  # Note: Use start() instead of run()

