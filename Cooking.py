from interactions import SlashContext, Extension, component_callback, ComponentContext
import logging
import asyncio
import re

class CookingModule(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    async def get_recipe_for_dish(self, dish_itemid):
        # Fetch all details for the given dish recipe
        return await self.db.fetchrow("""
            SELECT * FROM recipes
            WHERE dish_itemid = $1
        """, dish_itemid)

    async def attempt_cook_dish(self, player_id, dish_itemid):
        # Get recipe details
        recipe = await self.get_recipe_for_dish(dish_itemid)
        if not recipe:
            return "Recipe not found for this dish."

        # Check for required caught fish
        for i in range(1, 4):  # Loop through caught_fish_name1 to caught_fish_name3
            caught_fish_name = recipe[f'caught_fish_name{i}']
            if caught_fish_name:
                # Check if the player has the required caught fish
                fish_exists = await self.db.fetchval("""
                    SELECT COUNT(*) FROM inventory inv
                    JOIN caught_fish cf ON inv.caught_fish_id = cf.id
                    WHERE inv.playerid = $1 AND cf.fish_name = $2
                """, player_id, caught_fish_name)
                if fish_exists == 0:
                    return f"You don't have the required fish: {caught_fish_name}"

        # Check for standard ingredients
        for i in range(1, 7):  # Loop through ingredient1_itemid to ingredient6_itemid
            ingredient_id = recipe[f'ingredient{i}_itemid']
            quantity_required = recipe[f'quantity{i}_required']

            if ingredient_id is not None and quantity_required is not None:
                # Check if player has enough of the ingredient
                player_quantity = await self.db.fetchval("""
                    SELECT SUM(quantity) FROM inventory
                    WHERE playerid = $1 AND itemid = $2
                """, player_id, ingredient_id)

                if player_quantity is None or player_quantity < quantity_required:
                    return f"Not enough of ingredient: itemid {ingredient_id}"

        # Check for required tool, if applicable
        if recipe['required_tool']:
            has_tool = await self.get_equipped_cooking_tool(player_id, recipe['required_tool'])
            if not has_tool:
                return f"Required tool missing: {recipe['required_tool']}"

        # If all requirements are met, proceed with cooking
        # Remove required caught fish from inventory
        for i in range(1, 4):
            caught_fish_name = recipe[f'caught_fish_name{i}']
            if caught_fish_name:
                await self.db.execute("""
                    DELETE FROM inventory
                    WHERE inventoryid = (
                        SELECT inv.inventoryid
                        FROM inventory inv
                        JOIN caught_fish cf ON inv.caught_fish_id = cf.id
                        WHERE inv.playerid = $1 AND cf.fish_name = $2
                        LIMIT 1
                    )
                """, player_id, caught_fish_name)

        # Remove standard ingredients from inventory
        for i in range(1, 7):
            ingredient_id = recipe[f'ingredient{i}_itemid']
            quantity_required = recipe[f'quantity{i}_required']

            if ingredient_id is not None and quantity_required is not None:
                await self.db.execute("""
                    UPDATE inventory
                    SET quantity = quantity - $1
                    WHERE playerid = $2 AND itemid = $3
                """, quantity_required, player_id, ingredient_id)

        # Add the cooked dish to inventory
        await self.db.execute("""
            INSERT INTO inventory (playerid, itemid, quantity, isequipped)
            VALUES ($1, $2, 1, FALSE)
        """, player_id, dish_itemid)

        # Update cooking XP
        xp_gained = recipe['cooking_xp_gained']
        await self.add_cooking_xp(player_id, xp_gained)

        return f"You have successfully cooked {dish_itemid}!"

    async def get_equipped_cooking_tool(self, player_id, required_tool):
        tool = await self.db.fetchrow("""
            SELECT itemid FROM inventory
            WHERE playerid = $1 AND isequipped = TRUE AND name = $2
        """, player_id, required_tool)
        return tool is not None

    async def add_cooking_xp(self, player_id, xp_gained):
        await self.db.execute("""
            UPDATE player_skills_xp
            SET cooking_xp = cooking_xp + $1
            WHERE playerid = $2
        """, xp_gained, player_id)

    @component_callback(re.compile(r"^cook_\d+$"))
    async def cook_button_handler(self, ctx: ComponentContext):
        logging.info("Cook button pressed.")
        await ctx.defer(ephemeral=True)
        player_id = await self.db.get_or_create_player(ctx.author.id)

        # This is a placeholder. You'd likely pass the dish item ID here based on UI or selection.
        dish_itemid = 201  # Example dish ID for testing

        result = await self.attempt_cook_dish(player_id, dish_itemid)
        await ctx.send(result, ephemeral=True)

# Setup function to load this as an extension
def setup(bot):
    CookingModule(bot)
