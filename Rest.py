import re
from interactions import Extension, ButtonStyle, ComponentContext, component_callback
import logging

class RestModule(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db  # Use the shared Database instance
        logging.info("RestModule initialized and callback registered.")

    @component_callback(re.compile(r"^rest"))

    async def rest_handler(self, ctx: ComponentContext):
        """
        Handle the 'Rest' button to fully restore health, mana, and stamina.
        """
        try:
            logging.info(f"Rest button clicked by {ctx.author.id} with custom_id: {ctx.custom_id}")

            # Get player ID
            player_id = await self.db.get_or_create_player(ctx.author.id)
            
            # Fetch the current location of the player
            player_location = await self.db.fetchval("""
                SELECT current_location FROM player_data WHERE playerid = $1
            """, player_id)
            
            # Verify that the player's current location has the rest command available
            # Check by custom_id since that's what the button uses
            has_rest_command = await self.db.fetchval("""
                SELECT COUNT(*) FROM location_commands 
                WHERE locationid = $1 AND custom_id = 'rest'
            """, player_location)
            
            if not has_rest_command:
                player_location_name = await self.db.fetchval("""
                    SELECT name FROM locations WHERE locationid = $1
                """, player_location) or "your current location"
                await ctx.send(
                    f"You cannot rest at **{player_location_name}**! Rest is only available at specific locations.",
                    ephemeral=True
                )
                return

            # Fetch and update player's stats
            max_stats = await self.db.fetchrow("""
                SELECT max_health, max_mana, max_stamina
                FROM player_data
                WHERE playerid = $1
            """, player_id)
            if not max_stats:
                await ctx.send("Unable to retrieve player data. Please try again.", ephemeral=True)
                return

            await self.db.execute("""
                UPDATE player_data
                SET health = $1, mana = $2, stamina = $3
                WHERE playerid = $4
            """, max_stats['max_health'], max_stats['max_mana'], max_stats['max_stamina'], player_id)
            logging.info(f"Player {player_id}'s stats updated successfully.")

            await ctx.send(
                content="You have rested and fully restored your health, mana, and stamina!",
                ephemeral=True
            )
        except Exception as e:
            logging.error(f"Error in rest_handler: {e}")
            await ctx.send("An error occurred while resting. Please try again.", ephemeral=True)


# Setup function to load this as an extension
def setup(bot):
    RestModule(bot)
