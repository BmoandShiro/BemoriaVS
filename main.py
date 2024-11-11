from interactions import SlashCommand, Client, Extension, Client, SlashContext, slash_command 
from charactercreation import setup as cc_setup
from charactercreation import CharacterCreation
from PostgreSQLlogic import Database  # Import the Database class
from player_interface import setup as player_interface_setup
from functools import partial
import logging
from travelsystem import TravelSystem, setup as ts_setup 
from GuildConfig import GUILD_IDS
from Inventory import Inventory
from inventory_systems import InventorySystem  # Import the InventorySystem wrapper
from travelsystem import TravelSystem
#from NPC_Finn import setup as setup_finn
from NPC_Manager import NPCManager
from inventory_systems import setup as inventory_setup
#from Fishing import setup as fishing_setup
from Fishing import FishingModule

logging.basicConfig(level=logging.INFO)

TOKEN = 'MTE3Nzc3MjcyNDE1MjY5Njg1Mg.GmEncj.q1k72hSszveLmlOLde-I1XVvVPAFLBlQAJdKXY'

# Since GUILD_IDS is now a list with one element, we extract the single ID for debug_scope
debug_scope = GUILD_IDS[0]

bot = Client(token=TOKEN, debug_scope=debug_scope)


DATABASE_DSN = "postgresql://postgres:Oshirothegreat9!@localhost:5432/BMOSRPG"

db = Database(dsn=DATABASE_DSN)
bot.db = db  # Attach the database instance to the bot object

logging.info("Loading extensions...")
# When setting up the bot, make sure the CharacterCreation class is defined to accept a bot and a db instance
# Load your extensions here
player_interface_setup(bot)  # Pass the database instance to the setup function of the player_interface 
cc_setup(bot)  # Pass both the bot and db instances to the setup function
#ts_setup(bot) #had to take this out for now to make it work idk why i need to learn this part better still

# Create and attach InventorySystem to the bot
inventory_system = InventorySystem(bot)
bot.inventory_system = inventory_system

# Create and attach the TravelSystem instance to the bot idk why this worked but it did so read into this more
travel_system = TravelSystem(bot)
bot.travel_system = travel_system

#inventory_setup(bot)

bot.fishing_module = FishingModule(bot)
#fishing_setup(bot)


@slash_command(name="talk_to_npc", description="Talk to an NPC.")
async def talk_to_npc_command(ctx: SlashContext, npc_name: str):
    """
    Command to talk to an NPC by name.
    """
    NPC_Manager = bot.get_extension("NPCManager")
    if NPC_Manager:
        await NPC_Manager.interact_with_npc(ctx, npc_name)
    else:
        await ctx.send("NPC Manager is not available.", ephemeral=True)

# Load extensions (including NPCManager)
bot.load_extension("NPC_Manager")  # This will load the NPC_Manager extension correctly




# Event listener for when the bot has switched from offline to online.
@bot.event
async def on_ready():
    print(f"Logged in as {bot.me.name}")
    await bot.db.connect()
    await bot.sync_interactions()

# Start the bot with the specified token
bot.start()  # Note: Use start() instead of run()