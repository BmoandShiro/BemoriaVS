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

        # Get all caught fish for the player
        caught_fish = await self.db.fetch("""
            SELECT id FROM caught_fish
            WHERE player_id = $1
        """, player_id)

        total_fish_count = len(caught_fish)

        if not inventory_items and total_fish_count == 0:
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
                is_any = recipe.get(f'ingredient{i}_is_any', False)  # Assuming this field indicates if "any fish" is allowed

                if ingredient_id is not None and quantity_required is not None:
                    # Check in inventory for standard items
                    player_quantity = next((item['quantity'] for item in inventory_items if item['itemid'] == ingredient_id), 0)
                    if player_quantity < quantity_required:
                        all_ingredients_available = False
                        break

                elif is_any and quantity_required is not None:
                    # Check if the total number of caught fish is enough
                    if total_fish_count < quantity_required:
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
        select_menu.options.extend(options)

        await ctx.send(components=[select_menu], ephemeral=True)


    @component_callback(re.compile(r"^cook_select_menu_\d+$"))
    async def cook_select_menu_handler(self, ctx: ComponentContext):
        try:
            selected_recipe_id = int(ctx.values[0])
            player_id = await self.db.get_or_create_player(ctx.author.id)

            # Fetch recipe details
            recipe = await self.db.fetchrow("""
                SELECT * FROM recipes WHERE dish_itemid = $1
            """, selected_recipe_id)

            if not recipe:
                await ctx.send("Recipe not found for this dish.", ephemeral=True)
                return

            logging.info(f"Recipe details: {recipe}")  # Debug log to check the recipe data

            # Gather information about ingredients that need to be selected
            ingredients_to_select = []

            for i in range(1, 7):
                ingredient_id = recipe.get(f'ingredient{i}_itemid')
                quantity_required = recipe.get(f'quantity{i}_required')
                caught_fish_name = recipe.get(f'caught_fish_name{i}')

                # Handle standard inventory item requirement
                if ingredient_id is not None and quantity_required is not None:
                    # Fetch the available quantity for each ingredient
                    inventory_items = await self.db.fetch("""
                        SELECT inventoryid, itemid, quantity FROM inventory
                        WHERE playerid = $1 AND itemid = $2
                    """, player_id, ingredient_id)

                    if inventory_items:
                        ingredients_to_select.append((ingredient_id, inventory_items, quantity_required))

                # Handle "any fish" requirement
                elif caught_fish_name and caught_fish_name.lower() == "any":
                    # Since caught fish don't stack, their quantity is effectively always 1.
                    # Fetch the caught fish from the player's inventory
                    caught_fish_items = await self.db.fetch("""
                        SELECT id, fish_name FROM caught_fish
                        WHERE player_id = $1
                    """, player_id)

                    if len(caught_fish_items) >= 1:
                        ingredients_to_select.append(("any", caught_fish_items, 1))  # Quantity is always 1 for each caught fish

            # Debug log to check ingredients to select
            logging.info(f"Ingredients to select for recipe {selected_recipe_id}: {ingredients_to_select}")

            # Always prompt for ingredient selection, even if there is only one option available
            if ingredients_to_select:
                await self.prompt_for_ingredient_selection(ctx, player_id, selected_recipe_id, ingredients_to_select)
            else:
                # If no ingredient selection is needed, proceed with cooking
                result = await self.finalize_cooking(player_id, recipe)
                await ctx.send(result, ephemeral=True)

        except Exception as e:
            logging.error(f"Error in cook_select_menu_handler: {e}")
            await ctx.send("An error occurred while processing your request. Please try again.", ephemeral=True)






    async def prompt_for_ingredient_selection(self, ctx, player_id, dish_itemid, ingredients_to_select):
        # For each ingredient that requires selection, prompt the user to choose
        for ingredient, inventory_items, quantity_required in ingredients_to_select:
            if ingredient == "any":  # Identify that any fish can be used
                # Fetch caught fish from the player's inventory only
                caught_fish_in_inventory = await self.db.fetch("""
                    SELECT cf.id, cf.fish_name 
                    FROM caught_fish cf
                    JOIN inventory i ON cf.id = i.caught_fish_id
                    WHERE i.playerid = $1
                """, player_id)

                # Limit the number of caught fish options to a maximum of 25
                limited_fish_items = caught_fish_in_inventory[:25]

                options = [
                    StringSelectOption(label=f"{fish['fish_name']} (ID: {fish['id']})", value=str(fish['id']))
                    for fish in limited_fish_items
                ]
                ingredient_name = "Any Caught Fish"
                custom_id = f"ingredient_fish_select_{dish_itemid}_any_{player_id}"
                logging.info(f"Generated custom ID for 'any fish' selection: {custom_id}")

            else:
                # Standard item selection
                limited_inventory_items = inventory_items[:25]  # Limit options to 25
                options = [
                    StringSelectOption(label=f"{await self.get_item_name(item['itemid'])} (Qty: {item['quantity']})", value=str(item['inventoryid']))
                    for item in limited_inventory_items
                ]
                ingredient_name = await self.get_item_name(ingredient)
                custom_id = f"ingredient_select_{dish_itemid}_{ingredient}_{player_id}"
                logging.info(f"Generated custom ID for standard selection: {custom_id}")

            # Create a string select menu for ingredient selection
            select_menu = StringSelectMenu(
                custom_id=custom_id,
                placeholder=f"Select {quantity_required}x {ingredient_name} to use"
            )
            select_menu.options.extend(options)
            logging.info(f"Sending selection menu with custom_id: {select_menu.custom_id}")
            # Send the menu to the user and wait for selection
            await ctx.send(components=[select_menu], ephemeral=True)





    @component_callback(re.compile(r"^ingredient_(select|fish_select)_\d+(_any|_\w+)_\d+$"))
    async def ingredient_select_handler(self, ctx: ComponentContext):
        try:
            # Split the custom ID to determine the relevant action
            parts = ctx.custom_id.split("_")
        
            if len(parts) == 5:
                # Format for normal items (ingredient_type, dish_itemid, ingredient_id, player_id)
                _, ingredient_type, dish_itemid, ingredient_id, player_id = parts
            elif len(parts) == 4:
                # Format for "any fish" items (ingredient_type, dish_itemid, player_id)
                _, ingredient_type, dish_itemid, player_id = parts
                ingredient_id = "any"
            else:
                await ctx.send("Invalid ingredient selection.", ephemeral=True)
                return

            # Log the received custom ID to help with debugging
            logging.info(f"Custom ID received in ingredient_select_handler: {ctx.custom_id}")

            # Extract the selected inventory ID from the dropdown selection
            selected_inventory_id = int(ctx.values[0])
            logging.info(f"Selected inventory ID: {selected_inventory_id}")

            if ingredient_type == "select":
                # Update the inventory to reduce the selected item's quantity
                await self.db.execute("""
                    UPDATE inventory
                    SET quantity = quantity - 1
                    WHERE inventoryid = $1
                """, selected_inventory_id)

                # If the quantity becomes 0, remove the inventory entry
                await self.db.execute("""
                    DELETE FROM inventory
                    WHERE inventoryid = $1 AND quantity <= 0
                """, selected_inventory_id)

                logging.info(f"Standard ingredient with inventory ID {selected_inventory_id} updated or removed.")

            elif ingredient_type == "fish_select":
                # Remove the selected fish from the caught_fish table
                await self.db.execute("""
                    DELETE FROM caught_fish
                    WHERE id = $1
                """, selected_inventory_id)

                logging.info(f"Caught fish with ID {selected_inventory_id} removed from caught_fish table.")

            # Recheck if all ingredients have been selected
            recipe = await self.db.fetchrow("""
                SELECT * FROM recipes WHERE dish_itemid = $1
            """, int(dish_itemid))

            if not recipe:
                await ctx.send("Recipe not found for this dish.", ephemeral=True)
                return

            # Gather information about remaining ingredients that need to be selected
            ingredients_to_select = []
            for i in range(1, 7):
                ingredient_id = recipe[f'ingredient{i}_itemid']
                quantity_required = recipe[f'quantity{i}_required']
                caught_fish_name = recipe.get(f'caught_fish_name{i}')  # Assuming caught_fish_name{i} is used to identify fish requirements

                if ingredient_id is not None and quantity_required is not None:
                    # Check in inventory for standard items
                    inventory_items = await self.db.fetch("""
                        SELECT inventoryid, itemid, quantity FROM inventory
                        WHERE playerid = $1 AND itemid = $2
                    """, player_id, ingredient_id)

                    if inventory_items:
                        ingredients_to_select.append((ingredient_id, inventory_items, quantity_required))

                elif caught_fish_name and caught_fish_name.lower() == "any" and quantity_required is not None:
                    # Check in caught_fish table for any fish
                    caught_fish_items = await self.db.fetch("""
                        SELECT id, fish_name FROM caught_fish
                        WHERE player_id = $1
                    """, player_id)

                    if len(caught_fish_items) >= quantity_required:
                        ingredients_to_select.append(("any", caught_fish_items, quantity_required))

            if ingredients_to_select:
                # Prompt for the next ingredient selection if there are still ingredients to choose
                await self.prompt_for_ingredient_selection(ctx, player_id, dish_itemid, ingredients_to_select)
            else:
                # All selections are made, finalize the cooking
                result = await self.finalize_cooking(int(player_id), recipe)
                await ctx.send(result, ephemeral=True)

        except Exception as e:
            logging.error(f"Error in ingredient_select_handler: {e}")
            await ctx.send("An error occurred while processing your request. Please try again.", ephemeral=True)









    async def finalize_cooking(self, player_id, recipe):
        # Proceed with cooking if all requirements are met
        for i in range(1, 7):
            ingredient_id = recipe[f'ingredient{i}_itemid']
            fish_name_required = recipe.get(f'ingredient{i}_fish_name')  # Adjust for fish name
            quantity_required = recipe[f'quantity{i}_required']

            if ingredient_id is not None and quantity_required is not None:
                await self.db.execute("""
                    UPDATE inventory
                    SET quantity = quantity - $1
                    WHERE playerid = $2 AND itemid = $3
                """, quantity_required, player_id, ingredient_id)

            elif fish_name_required is not None and quantity_required is not None:
                # Delete or update caught fish entries
                await self.db.execute("""
                    DELETE FROM caught_fish
                    WHERE player_id = $1 AND fish_name = $2
                    LIMIT $3
                """, player_id, fish_name_required, quantity_required)

   


        # Add the cooked dish to inventory
        dish_itemid = recipe['dish_itemid']
        existing_quantity = await self.db.fetchval("""
            SELECT quantity FROM inventory
            WHERE playerid = $1 AND itemid = $2
        """, player_id, dish_itemid)

        if existing_quantity is not None:
            await self.db.execute("""
                UPDATE inventory
                SET quantity = quantity + 1
                WHERE playerid = $1 AND itemid = $2
            """, player_id, dish_itemid)
        else:
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
