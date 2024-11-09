# command_helpers.py

def location_required(valid_locations):
    def decorator(func):
        async def wrapper(self, ctx, *args, **kwargs):
            # Fetch player location
            player_id = await self.bot.db.get_or_create_player(ctx.author.id)
            player_data = await self.bot.db.fetch_player_details(player_id)
            current_location = player_data['current_location']

            # Check if the player's location is in the list of valid locations
            if current_location not in valid_locations:
                location_names = ", ".join(valid_locations)
                await ctx.send(f"This action is only available at: {location_names}")
                return
            
            # Proceed with the command if location is valid
            await func(self, ctx, *args, **kwargs)
        return wrapper
    return decorator

