import interactions
from interactions import ButtonStyle, Embed, Button, Client, Extension, slash_command
from functools import partial
from config import GUILD_IDS
import logging
from PostgreSQLlogic import Database

class playerinterface(Extension):  # Inherit from Extension
    def __init__(self, bot):
        self.bot = bot
        self.db = Database(dsn="postgresql://postgres:Oshirothegreat9!@localhost:5432/BMOSRPG")
        
        
    async def send_player_ui(self, ctx, location_name, health, mana, stamina):
        embed = Embed(
            title="Player Information",
            description=f"You are currently in {location_name}",
            color=0x00FF00
        )
        embed.add_field(name="Health", value=str(health), inline=True)
        embed.add_field(name="Mana", value=str(mana), inline=True)
        embed.add_field(name="Stamina", value=str(stamina), inline=True)
        
        travel_button = Button(style=ButtonStyle.PRIMARY, label="Travel", custom_id="travel")
        skills_button = Button(style=ButtonStyle.PRIMARY, label="Skills", custom_id="skills")
        stats_button = Button(style=ButtonStyle.PRIMARY, label="View Stats", custom_id="view_stats")
        inventory_button = Button(style=ButtonStyle.PRIMARY, label="Inventory", custom_id="inventory")
        quests_button = Button(style=ButtonStyle.PRIMARY, label="Quests", custom_id="quests")

        await ctx.send(embeds=[embed], components=[travel_button, skills_button, stats_button, inventory_button, quests_button])

    @slash_command(name="ui", description="Show the main UI", scopes=GUILD_IDS)  # Use scopes to limit to specific guilds
    async def ui_command(self, ctx):
        logging.info("ui_command called")
        db = self.bot.db
        if db.pool is None:
            logging.error("Database pool is not initialized")
            await ctx.send("Database connection issue. Please try again later.", ephemeral=True)
            return

        try:
            logging.info(f"Fetching player data for user {ctx.author.id}")
            player_id = await db.get_or_create_player(ctx.author.id)
            logging.info(f"Player ID: {player_id}")
            player_data = await db.fetch_player_details(player_id)
            logging.info(f"Player Data: {player_data}")

            if player_data:
                await self.send_player_ui(ctx, player_data['location_name'], player_data['health'], player_data['mana'], player_data['stamina'])
            else:
                await ctx.send("Your player data could not be found.", ephemeral=True)
        except Exception as e:
            logging.error(f"An error occurred while fetching player data: {e}")
            await ctx.send("An error occurred while fetching your player data. Please try again later.", ephemeral=True)
                    
def setup(bot):
    playerinterface(bot)  # Register the extension properly
