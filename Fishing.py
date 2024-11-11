import interactions
from interactions import SlashContext, Extension, component_callback, ComponentContext

import random
import time

class FishingModule:
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db  # Access the database instance directly from the bot
        
    async def calculate_catch_probability(self, fish_list):
        # Calculate probabilities based on catch_probability and drop_modifier for each fish
        probabilities = {
            fish['name']: float(fish['catch_probability']) * float(fish['drop_modifier']) for fish in fish_list
        }
        total_probability = sum(probabilities.values())
    
        # Normalize probabilities so they sum to 1
        normalized_probabilities = {name: prob / total_probability for name, prob in probabilities.items()}
    
        return normalized_probabilities



    async def get_player_xp_level(self, player_id):
        # Retrieve fishing XP from player_skills_xp table
        xp_level = await self.db.fetchval("SELECT fishing_xp FROM player_skills_xp WHERE playerid = $1", player_id)
        return xp_level or 1  # Default to level 1 if no XP found



    async def fetch_fish_for_location(self, location, tool_type):
        print(f"Fetching fish for location: '{location}', tool_type: '{tool_type}'")  # Debugging output

        # Convert location to a string to match the expected input type
        location = str(location)

        query = """
            SELECT * FROM fish
            WHERE location = $1 AND rodtype = $2
        """
        fish_list = await self.db.fetch(query, location, tool_type)
    
        # Convert each fish record to a dictionary and set default drop_modifier if missing
        fish_list = [{**dict(fish), "drop_modifier": fish.get("drop_modifier", 1.0)} for fish in fish_list]
    
        print(f"Fish list retrieved: {fish_list}")  # Check if any results are retrieved
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
        total_weight = sum(float(fish["catch_probability"]) * float(fish["drop_modifier"]) for fish in filtered_fish)
        roll = random.uniform(0, total_weight)
    
        current_weight = 0
        for fish in filtered_fish:
            current_weight += float(fish["catch_probability"]) * float(fish["drop_modifier"])
            if roll <= current_weight:
                print(f"Selected fish: {fish['name']} with rarity: {rarity}")  # Debug output
                return fish


    async def attempt_catch_fish(self, player_id, location, tool_type):
        fish_list = await self.fetch_fish_for_location(location, tool_type)
        if not fish_list:
            return "No fish available for this location and tool type."

        xp_level = await self.get_player_xp_level(player_id)
        catch_time = max(1, 10 - xp_level)
        time.sleep(catch_time)

        rarity = self.roll_for_rarity(xp_level)
        caught_fish = self.roll_for_fish(fish_list, rarity)
    
        if not caught_fish:
            return "No fish matched the rolled rarity."

        length = random.uniform(float(caught_fish['minlength']), float(caught_fish['maxlength']))
        weight = random.uniform(float(caught_fish['minweight']), float(caught_fish['maxweight']))
        xp_gained = caught_fish.get('xp_gained', 10)
        await self.add_fishing_xp(player_id, xp_gained)

        # Insert the caught fish into `caught_fish` table
        caught_fish_id = await self.db.fetchval("""
            INSERT INTO caught_fish (player_id, fish_name, length, weight, rarity, xp_gained)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """, player_id, caught_fish['name'], round(length, 2), round(weight, 2), rarity, xp_gained)

        # Insert the caught fish into `inventory` table
        await self.db.execute("""
            INSERT INTO inventory (playerid, caught_fish_id, quantity, isequipped)
            VALUES ($1, $2, 1, false)
        """, player_id, caught_fish_id)

        return {
            "name": caught_fish['name'],
            "length": round(length, 2),
            "weight": round(weight, 2),
            "xp_gained": xp_gained,
            "rarity": rarity
        }



    async def add_fishing_xp(self, player_id, xp_gained):
        """Update fishing XP for the player"""
        await self.db.execute("""
            UPDATE player_skills_xp
            SET fishing_xp = fishing_xp + $1
            WHERE playerid = $2
        """, xp_gained, player_id)



    async def fish_button_action(self, location, ctx):
        try:
            # Get the player ID
            player_id = await self.db.get_or_create_player(ctx.author.id)
        
            # Fetch the equipped fishing tool's specific rod type from items table
            tool = await self.db.fetchrow("""
                SELECT it.rodtype FROM inventory inv
                JOIN items it ON inv.itemid = it.itemid
                WHERE inv.playerid = $1 AND inv.isequipped = true AND it.type = 'Tool'
            """, player_id)
        
            if not tool or not tool['rodtype']:
                await ctx.send("You need to equip a fishing tool with a specified rod type to fish.")
                return
        
            tool_type = tool['rodtype']
        
            # Attempt to catch a fish with the specified location and tool type
            result = await self.attempt_catch_fish(player_id, location, tool_type)  # Pass player_id

            if isinstance(result, str):  # Error message if no fish are available
                await ctx.send(result)
            else:
                await ctx.send(
                    f"You caught a {result['rarity'].capitalize()} {result['name']}! "
                    f"Length: {result['length']} cm, Weight: {result['weight']} kg. "
                    f"XP Gained: {result['xp_gained']}."
                )

        except Exception as e:
            print(f"Error during fishing interaction: {e}")
            await ctx.send(f"An error occurred: {e}")
            

    


