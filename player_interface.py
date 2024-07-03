import interactions
from interactions import ButtonStyle, Embed, Button, Client, Extension, slash_command, SlashContext
from functools import partial

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

    # Setup function to load this as an extension
def setup(bot):
    playerinterface(bot)


       