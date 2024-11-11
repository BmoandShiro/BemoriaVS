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
        location = str(location)
        print(f"Fetching fish for location: {location}, tool_type: {tool_type}")  # Debug output
        
        query = """
            SELECT * FROM fish
            WHERE location = $1 AND rodtype = $2
        """
        fish_list = await self.db.fetch(query, location, tool_type)
        print(f"Fish list retrieved: {fish_list}")  # Verify the retrieved fish list
        
        # Check if drop_modifier exists; if not, set default
        for fish in fish_list:
            fish["drop_modifier"] = fish.get("drop_modifier", 1.0)
        
        return fish_list

    def roll_for_rarity(self, player_xp):
        # Define rarity distribution with possible multiplicative modifiers
        base_rarity_distribution = {
            "common": 50,
            "uncommon": 25,
            "rare": 15,
            "very_rare": 8,
            "legendary": 2  # Very low probability for legendary items
        }

        # Modify distribution based on player's fishing skill level
        if player_xp > 50:
            base_rarity_distribution["rare"] += 3
            base_rarity_distribution["uncommon"] += 2
            base_rarity_distribution["common"] -= 2
            base_rarity_distribution["very_rare"] += 1
            base_rarity_distribution["legendary"] += 1  # Slight boost for high-level players

        # Generate cumulative weights for rarity
        total_weight = sum(base_rarity_distribution.values())
        roll = random.uniform(0, total_weight)
        
        current_weight = 0
        for rarity, weight in base_rarity_distribution.items():
            current_weight += weight
            if roll <= current_weight:
                print(f"Rolled rarity: {rarity}")  # Debug output
                return rarity

    def roll_for_fish(self, fish_list, rarity):
        # Filter fish by the rarity tier
        filtered_fish = [fish for fish in fish_list if fish["qualitytier"].lower() == rarity]
        
        if not filtered_fish:
            return None

        # Calculate relative weights with drop_modifier for fine-tuning
        total_weight = sum(fish["catch_probability"] * fish["drop_modifier"] for fish in filtered_fish)
        roll = random.uniform(0, total_weight)
        
        current_weight = 0
        for fish in filtered_fish:
            current_weight += fish["catch_probability"] * fish["drop_modifier"]
            if roll <= current_weight:
                print(f"Selected fish: {fish['name']} with rarity: {rarity}")  # Debug output
                return fish

    async def attempt_catch_fish(self, player_id, location, tool_type):
        print(f"Attempting to catch fish for player: {player_id} at location: {location} with tool: {tool_type}")  # Debug output
        
        fish_list = await self.fetch_fish_for_location(location, tool_type)
        if not fish_list:
            print("No fish available.")  # Debug output
            return "No fish available for this location and tool type."

        player_xp = await self.get_player_xp_level(player_id)
        print(f"Player XP Level: {player_xp}")  # Debug output

        # Step 1: Roll for rarity
        rarity = self.roll_for_rarity(player_xp)
        
        # Step 2: Roll for fish within the selected rarity
        fish = self.roll_for_fish(fish_list, rarity)
        if not fish:
            print("No fish found in the rolled rarity.")  # Debug output
            return "No fish of that rarity available."

        # Step 3: Randomize length and weight within specified range
        length = random.uniform(fish['minlength'], fish['maxlength'])
        weight = random.uniform(fish['minweight'], fish['maxweight'])

        result = {
            "name": fish["name"],
            "rarity": rarity,
            "length": round(length, 2),
            "weight": round(weight, 2)
        }
        print(f"Catch result: {result}")  # Debug output
        return result

    async def fish_button_action(self, location, tool_type, ctx):
        try:
            player_id = await self.db.get_or_create_player(ctx.author.id)
            result = await self.attempt_catch_fish(player_id, location, tool_type)
            
            if isinstance(result, str):  # Error message if no fish are available
                await ctx.send(result)
            else:
                await ctx.send(
                    f"You caught a {result['rarity'].capitalize()} {result['name']}! "
                    f"Length: {result['length']} cm, Weight: {result['weight']} kg."
                )
        except Exception as e:
            print(f"Error during fish interaction: {e}")
            await ctx.send("An error occurred while attempting to fish. Please try again later.", ephemeral=True)