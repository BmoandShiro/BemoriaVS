import interactions
from interactions import SlashContext, Extension, component_callback, ComponentContext

import random
import time

class FishingModule:
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db  # Access the database instance directly from the bot

    async def get_player_xp_level(self, player_id):
        xp_level = await self.db.fetchval("SELECT fishing_xp FROM player_data WHERE playerid = $1", player_id)
        return xp_level or 1  # Default to level 1 if no XP found

    async def fetch_fish_for_location(self, location, tool_type):
        # Convert location to string if needed
        location = str(location)
        
        query = """
            SELECT * FROM fish
            WHERE location = $1 AND rodtype = $2
        """
        fish_list = await self.db.fetch(query, location, tool_type)
        return fish_list

    async def calculate_catch_probability(self, fish_list):
        probabilities = {
            fish['Catfish']: fish.get('catch_probability', 1.0) for fish in fish_list
        }
        total_prob = sum(probabilities.values())
        normalized_probabilities = {name: prob / total_prob for name, prob in probabilities.items()}
        return normalized_probabilities

    async def attempt_catch_fish(self, player_id, location, tool_type):
        fish_list = await self.fetch_fish_for_location(location, tool_type)
        if not fish_list:
            return "No fish available for this location and tool type."

        xp_level = await self.get_player_xp_level(player_id)
        catch_time = max(1, 10 - xp_level)
        time.sleep(catch_time)

        probabilities = await self.calculate_catch_probability(fish_list)
        fish_names = list(probabilities.keys())
        fish_weights = list(probabilities.values())

        caught_fish_name = random.choices(fish_names, weights=fish_weights, k=1)[0]
        caught_fish = next(fish for fish in fish_list if fish['name'] == caught_fish_name)

        length = random.uniform(caught_fish['minlength'], caught_fish['maxlength'])
        weight = random.uniform(caught_fish['minweight'], caught_fish['maxweight'])

        return {
            "name": caught_fish_name,
            "length": round(length, 2),
            "weight": round(weight, 2)
        }

    async def fish_button_action(self, location, tool_type, ctx):
        player_id = await self.db.get_or_create_player(ctx.author.id)
        result = await self.attempt_catch_fish(player_id, location, tool_type)
        if isinstance(result, str):  # Error message if no fish are available
            await ctx.send(result)
        else:
            await ctx.send(
                f"You caught a {result['name']}! Length: {result['length']} cm, Weight: {result['weight']} kg."
            )
