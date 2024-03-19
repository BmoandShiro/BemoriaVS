import interactions
from interactions import ButtonStyle, Embed, Button

class playerinterface:
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

    # Example of handling a button press
    @interactions.extension_component(custom_id="travel")
    async def travel_button_handler(self, ctx: interactions.CommandContext):
        # Handle travel logic here
        pass

    # ... other handlers for skills, stats, inventory, quests ...

# Setup function to be called to load this extension
def setup(bot):
    player_interface = PlayerInterface(bot)
    bot.add_component(player_interface.travel_button_handler)
    # ... add other components ...

# Later, you would load the extension in your main bot setup
# bot.load_extension("path.to.your.PlayerInterface")

