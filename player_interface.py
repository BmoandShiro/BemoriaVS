import interactions
from interactions import ButtonStyle, Embed, Button, Client, Extension, slash_command, SlashContext, component_callback, ComponentContext
from functools import partial
import logging
import math 

class playerinterface(Extension):
    def __init__(self, bot):
        self.bot = bot

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
        
    async def send_player_stats(self, ctx, player_id):
        db = self.bot.db
        player_stats = await db.fetch_view_stats(player_id)
        
        if player_stats:
            embeds = []
            embed = Embed(
                title="Player Stats",
                description=f"Stats for Player ID: {player_id}",
                color=0x00FF00
            )

            for i, (stat, value) in enumerate(player_stats.items()):
                if stat != "playerid" and value is not None:
                    color = 0xFF0000 if value < 0 else 0x00FF00
                    embed.add_field(name=stat.replace("_", " ").title(), value=f"{value}", inline=True)
                    if (i + 1) % 25 == 0:  # Add a new embed if there are 25 fields
                        embeds.append(embed)
                        embed = Embed(color=0x00FF00)
            
            embeds.append(embed)
            await ctx.send(embeds=embeds)
        else:
            await ctx.send("Your player stats could not be found.", ephemeral=True)


    async def send_player_skills(self, ctx, player_id):
        db = self.bot.db
        player_skills = await db.fetch_view_skills(player_id)
        
        if player_skills:
            embeds = []
            embed = Embed(
                title="Player Skills",
                description=f"Skills for Player ID: {player_id}",
                color=0x00FF00
            )

            for i, (skill, value) in enumerate(player_skills.items()):
                if skill != "playerid" and value is not None:
                    color = 0xFF0000 if value < 0 else 0x00FF00
                    embed.add_field(name=skill.replace("_", " ").title(), value=f"{value}", inline=True)
                    if (i + 1) % 25 == 0:  # Add a new embed if there are 25 fields
                        embeds.append(embed)
                        embed = Embed(color=0x00FF00)
            
            embeds.append(embed)
            await ctx.send(embeds=embeds)
        else:
            await ctx.send("Your player skills could not be found.", ephemeral=True)
            

    @slash_command(name="playerui", description="Reload the player UI menu")
    async def reload_ui_command(self, ctx):
        db = self.bot.db
        player_id = await db.get_or_create_player(ctx.author.id)
        player_data = await db.fetch_player_details(player_id)

        if player_data:
            await self.send_player_ui(ctx, 
                                      player_data['name'], 
                                      player_data['health'], 
                                      player_data['mana'], 
                                      player_data['stamina'])
        else:
            await ctx.send("Your player data could not be found.", ephemeral=True)
            
    @component_callback("view_stats")
    async def view_stats_button_handler(self, ctx: ComponentContext):
        db = self.bot.db
        player_id = await db.get_or_create_player(ctx.author.id)
        await self.send_player_stats(ctx, player_id)
        
    @component_callback("skills")
    async def skills_button_handler(self, ctx: ComponentContext):
        db = self.bot.db
        player_id = await db.get_or_create_player(ctx.author.id)
        await self.send_player_skills(ctx, player_id)
        
    @component_callback("travel")
    async def travel_button_handler(self, ctx: ComponentContext):
        db = self.bot.db
        player_id = await db.get_or_create_player(ctx.author.id)
        player_data = await db.fetch_player_details(player_id)
        logging.info(f"Player Data: {player_data}")
        if player_data:
            current_location_id = player_data['current_location']
            travel_system = self.bot.travel_system  # Access the TravelSystem instance directly
            if travel_system:
                await travel_system.display_locations(ctx, current_location_id)
            else:
                await ctx.send("Travel system is not available.", ephemeral=True)
        else:
            await ctx.send("Your player data could not be found.", ephemeral=True)

    # Setup function to load this as an extension
def setup(bot):
    playerinterface(bot)


       