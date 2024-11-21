from interactions import SlashContext, Extension, component_callback, ComponentContext, StringSelectMenu, StringSelectOption
import logging
import asyncio
import re

class CookingModule(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    async def get_recipes_from_ingredients(self, player_id):
        # Get all items in player's inventory
        inventory_items = await self.db.fetch("""
            SELECT itemid, quantity FROM inventory
            WHERE playerid = $1
        """, player_id)

        if not inventory_items:
            return []

        # Fetch all recipes
        recipes = await self.db.fetch("""
            SELECT * FROM recipes
        """)

        compatible_recipes = []

        # Check if player's inventory has ingredients for each recipe
        for recipe in recipes:
            all_ingredients_available = True

            # Check standard ingredients
            for i in range(1, 7):
                ingredient_id = recipe[f'ingredient{i}_itemid']
                quantity_required = recipe[f'quantity{i}_required']

                if ingredient_id is not None and quantity_required is not None:
                    player_quantity = next((item['quantity'] for item in inventory_items if item['itemid'] == ingredient_id), 0)
                    if player_quantity < quantity_required:
                        all_ingredients_available = False
                        break

            if all_ingredients_available:
                compatible_recipes.append(recipe)

        return compatible_recipes

    async def get_item_name(self, itemid):
        # Fetch the name of an item based on itemid from items table
        return await self.db.fetchval("""
            SELECT name FROM items
            WHERE itemid = $1
        """, itemid)

    @component_callback(re.compile(r"^cook_\d+$"))
    async def cook_button_handler(self, ctx: ComponentContext):
        logging.info("Cook button pressed.")
        await ctx.defer(ephemeral=True)
        player_id = await self.db.get_or_create_player(ctx.author.id)

        # Get compatible recipes based on player's inventory
        compatible_recipes = await self.get_recipes_from_ingredients(player_id)

        if not compatible_recipes:
            await ctx.send("You do not have enough ingredients to cook any recipes.", ephemeral=True)
            return

        # Create options for the select menu with item names
        options = []
        for recipe in compatible_recipes:
            dish_itemid = recipe['dish_itemid']
            dish_name = await self.get_item_name(dish_itemid)  # Get the name of the dish
            options.append(StringSelectOption(label=dish_name, value=str(dish_itemid)))

        # Create a string select menu to choose a recipe to cook
        select_menu = StringSelectMenu(
            custom_id=f"cook_select_menu_{player_id}",
            placeholder="Choose a dish to cook"
        )
        select_menu.options = options

        await ctx.send(components=[select_menu], ephemeral=True)

    @component_callback(re.compile(r"^cook_select_menu_\d+$"))
    async def cook_select_menu_handler(self, ctx: ComponentContext):
        selected_recipe_id = int(ctx.values[0])
        player_id = await self.db.get_or_create_player(ctx.author.id)

        # Attempt to cook the selected dish using the recipes available to the player
        compatible_recipes = await self.get_recipes_from_ingredients(player_id)

        # Check if the selected recipe is available to cook
        recipe = next((r for r in compatible_recipes if r['dish_itemid'] == selected_recipe_id), None)
        if not recipe:
            await ctx.send("You no longer have the required ingredients for this recipe.", ephemeral=True)
            return

        # Proceed with cooking if all requirements are met
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
        """, player_id, selected_recipe_id)

        # Update cooking XP
        xp_gained = recipe['cooking_xp_gained']
        await self.add_cooking_xp(player_id, xp_gained)

        dish_name = await self.get_item_name(selected_recipe_id)
        return_message = f"You have successfully cooked {dish_name}!"
        await ctx.send(return_message, ephemeral=True)
        
    async def attempt_cook_dish(self, player_id, dish_itemid):
        # Get recipe details
        compatible_recipes = await self.get_recipes_from_ingredients(player_id)
        recipe = next((r for r in compatible_recipes if r['dish_itemid'] == dish_itemid), None)

        if not recipe:
            return "Recipe not found for this dish."

        # Check for standard ingredients
        for i in range(1, 7):
            ingredient_id = recipe[f'ingredient{i}_itemid']
            quantity_required = recipe[f'quantity{i}_required']

            if ingredient_id is not None and quantity_required is not None:
                player_quantity = await self.db.fetchval("""
                    SELECT SUM(quantity) FROM inventory
                    WHERE playerid = $1 AND itemid = $2
                """, player_id, ingredient_id)

                if player_quantity is None or player_quantity < quantity_required:
                    return f"Not enough of ingredient: itemid {ingredient_id}"

        # Proceed with cooking if all requirements are met
        for i in range(1, 7):
            ingredient_id = recipe[f'ingredient{i}_itemid']
            quantity_required = recipe[f'quantity{i}_required']

            if ingredient_id is not None and quantity_required is not None:
                await self.db.execute("""
                    UPDATE inventory
                    SET quantity = quantity - $1
                    WHERE playerid = $2 AND itemid = $3
                """, quantity_required, player_id, ingredient_id)

        # Add the cooked dish to inventory, either by updating or inserting
        existing_quantity = await self.db.fetchval("""
            SELECT quantity FROM inventory
            WHERE playerid = $1 AND itemid = $2
        """, player_id, dish_itemid)

        if existing_quantity is not None:
            # If the item already exists, update the quantity
            await self.db.execute("""
                UPDATE inventory
                SET quantity = quantity + 1
                WHERE playerid = $1 AND itemid = $2
            """, player_id, dish_itemid)
        else:
            # If the item doesn't exist, insert a new record
            await self.db.execute("""
                INSERT INTO inventory (playerid, itemid, quantity, isequipped)
                VALUES ($1, $2, 1, FALSE)
            """, player_id, dish_itemid)

        # Update cooking XP
        xp_gained = recipe['cooking_xp_gained']
        await self.add_cooking_xp(player_id, xp_gained)

        dish_name = await self.get_item_name(dish_itemid)
        return f"You have successfully cooked {dish_name}!"



    async def add_cooking_xp(self, player_id, xp_gained):
        await self.db.execute("""
            UPDATE player_skills_xp
            SET cooking_xp = cooking_xp + $1
            WHERE playerid = $2
        """, xp_gained, player_id)

# Setup function to load this as an extension
def setup(bot):
    CookingModule(bot)
