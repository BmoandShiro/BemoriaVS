import re
from interactions import Extension, ButtonStyle, ComponentContext, component_callback
import logging

class RestModule(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db  # Use the shared Database instance

    @component_callback(re.compile(r"^rest_\d+$"))
    async def rest_handler(self, ctx: ComponentContext):
        """
        Handle the 'Rest' button to fully restore health, mana, and stamina.
        """
        try:
            # Extract the location ID from the custom ID
            location_id = int(ctx.custom_id.split("_")[-1])
            player_id = await self.db.get_or_create_player(ctx.author.id)  # Use Database utility function

            # Fetch the player's max stats using a utility function
            max_stats = await self.db.fetchrow("""
                SELECT max_health, max_mana, max_stamina
                FROM player_data
                WHERE playerid = $1
            """, player_id)

            if not max_stats:
                await ctx.send("Unable to retrieve player data. Please try again.", ephemeral=True)
                return

            # Update the player's stats to their maximum values using a utility function
            await self.db.execute("""
                UPDATE player_data
                SET health = $1, mana = $2, stamina = $3
                WHERE playerid = $4
            """, max_stats['max_health'], max_stats['max_mana'], max_stats['max_stamina'], player_id)

            # Notify the player
            await ctx.send(
                content="You have rested and fully restored your health, mana, and stamina!",
                ephemeral=True
            )

            logging.info(f"Player {player_id} has rested at location {location_id}.")
        except Exception as e:
            logging.error(f"Error in rest_handler: {e}")
            await ctx.send("An error occurred while resting. Please try again.", ephemeral=True)

# Setup function to load this as an extension
def setup(bot):
    RestModule(bot)
