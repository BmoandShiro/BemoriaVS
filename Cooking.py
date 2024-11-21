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
        try:
            logging.info(f"Prompting for ingredient selection for player ID: {player_id}, dish_itemid: {dish_itemid}.")
            logging.info(f"Ingredients to select: {ingredients_to_select}")

            for ingredient, inventory_items, quantity_required in ingredients_to_select:
                logging.info(f"Processing ingredient: {ingredient}, Quantity Required: {quantity_required}")

                if ingredient == "any":
                    caught_fish_in_inventory = await self.db.fetch("""
                        SELECT cf.id, cf.fish_name 
                        FROM caught_fish cf
                        JOIN inventory i ON cf.id = i.caught_fish_id
                        WHERE i.playerid = $1
                    """, player_id)

                    logging.info(f"Caught fish available for selection: {caught_fish_in_inventory}")
                    limited_fish_items = caught_fish_in_inventory[:25]

                    options = [
                        StringSelectOption(label=f"{fish['fish_name']} (ID: {fish['id']})", value=str(fish['id']))
                        for fish in limited_fish_items
                    ]
                    ingredient_name = "Any Caught Fish"
                    custom_id = f"ingredient_fish_select_{dish_itemid}_any_{player_id}"  # Ensure "fish_select" is used
                    logging.info(f"Generated custom ID for 'any fish' selection: {custom_id}")

                else:
                    limited_inventory_items = inventory_items[:25]
                    options = [
                        StringSelectOption(label=f"{await self.get_item_name(item['itemid'])} (Qty: {item['quantity']})", value=str(item['inventoryid']))
                        for item in limited_inventory_items
                    ]
                    ingredient_name = await self.get_item_name(ingredient)
                    custom_id = f"ingredient_select_{dish_itemid}_{ingredient}_{player_id}"
                    logging.info(f"Generated custom ID for standard selection: {custom_id}")

                logging.debug(f"Custom ID: {custom_id}, Options: {[option.label for option in options]}")

                select_menu = StringSelectMenu(
                    custom_id=custom_id,
                    placeholder=f"Select {quantity_required}x {ingredient_name} to use"
                )
                select_menu.options.extend(options)
                logging.info(f"Sending selection menu with custom_id: {select_menu.custom_id}")

                await ctx.send(components=[select_menu], ephemeral=True)

        except Exception as e:
            logging.error(f"Error in prompt_for_ingredient_selection: {e}")




    @component_callback(re.compile(r"^ingredient_(select|fish_select)_\d+(_any|_\w+)_\d+$"))
    async def ingredient_select_handler(self, ctx: ComponentContext):
        try:
            parts = ctx.custom_id.split("_")
            logging.info(f"Custom ID parts: {parts}")

            if len(parts) == 6:
                _, ingredient_type, _, dish_itemid, _, player_id = parts
                player_id = int(player_id)
                ingredient_id = "any"
            elif len(parts) == 5:
                _, ingredient_type, dish_itemid, ingredient_id, player_id = parts
                player_id = int(player_id)
            else:
                await ctx.send("Invalid ingredient selection.", ephemeral=True)
                logging.error(f"Invalid custom ID format: {ctx.custom_id}")
                return

            selected_id = int(ctx.values[0])
            logging.info(f"Selected ID: {selected_id}, Ingredient Type: {ingredient_type}, Player ID: {player_id}")

            if ingredient_type == "fish":
                logging.info(f"Attempting to delete caught fish with ID: {selected_id} for player ID: {player_id}")
                await self.delete_ingredient(caught_fish_id=selected_id, player_id=player_id)
            else:
                logging.info(f"Ingredient type does not match 'fish_select'. Skipping deletion. Ingredient type: {ingredient_type}")

            recipe = await self.db.fetchrow("""
                SELECT * FROM recipes WHERE dish_itemid = $1
            """, int(dish_itemid))
            if not recipe:
                await ctx.send("Recipe not found for this dish.", ephemeral=True)
                logging.error(f"Recipe with dish_itemid {dish_itemid} not found.")
                return

            logging.info(f"Recipe details: {recipe}")

            ingredients_to_select = []
            for i in range(1, 7):
                ingredient_id = recipe[f'ingredient{i}_itemid']
                quantity_required = recipe[f'quantity{i}_required']
                caught_fish_name = recipe.get(f'caught_fish_name{i}')

                logging.info(f"Checking ingredient {i}: ingredient_id={ingredient_id}, quantity_required={quantity_required}, caught_fish_name={caught_fish_name}")

                if ingredient_id and quantity_required:
                    inventory_items = await self.db.fetch("""
                        SELECT inventoryid, quantity FROM inventory
                        WHERE playerid = $1 AND itemid = $2
                    """, player_id, ingredient_id)
                    if inventory_items:
                        ingredients_to_select.append((ingredient_id, inventory_items, quantity_required))

                elif caught_fish_name and caught_fish_name.lower() == "any" and quantity_required:
                    caught_fish_items = await self.db.fetch("""
                        SELECT id, fish_name FROM caught_fish
                        WHERE player_id = $1
                    """, player_id)
                    if len(caught_fish_items) >= quantity_required:
                        ingredients_to_select.append(("any", caught_fish_items, quantity_required))

            if ingredients_to_select:
                await self.prompt_for_ingredient_selection(ctx, player_id, dish_itemid, ingredients_to_select)
            else:
                logging.info(f"All ingredients selected for recipe {dish_itemid}. Finalizing cooking...")
                await self.finalize_cooking(player_id, recipe)
                await ctx.send(f"You have successfully cooked {await self.get_item_name(recipe['dish_itemid'])}!", ephemeral=True)

        except Exception as e:
            logging.error(f"Error in ingredient_select_handler: {e}")







    async def delete_ingredient(self, caught_fish_id: int, player_id: int):
        try:
            logging.info(f"Deleting inventory entry for caught_fish_id={caught_fish_id}, player_id={player_id}")

            # Delete inventory entry
            inventory_entry = await self.db.fetchrow("""
                SELECT inventoryid
                FROM inventory
                WHERE caught_fish_id = $1 AND playerid = $2
            """, caught_fish_id, player_id)

            if inventory_entry:
                inventory_id = inventory_entry['inventoryid']
                await self.db.execute("""
                    DELETE FROM inventory
                    WHERE inventoryid = $1
                """, inventory_id)
                logging.info(f"Deleted inventory entry with inventoryid={inventory_id} for caught_fish_id={caught_fish_id}")

            # Delete caught fish entry
            await self.db.execute("""
                DELETE FROM caught_fish
                WHERE id = $1
            """, caught_fish_id)
            logging.info(f"Deleted caught fish with id={caught_fish_id}")
        except Exception as e:
            logging.error(f"Error deleting ingredient: {e}")



    async def finalize_cooking(self, player_id, recipe):
        try:
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
            await self.db.execute("""
                UPDATE player_skills_xp
                SET cooking_xp = cooking_xp + $1
                WHERE playerid = $2
            """, xp_gained, player_id)

            # Log success and notify the user
            dish_name = await self.get_item_name(dish_itemid)
            logging.info(f"Successfully cooked {dish_name} for player ID {player_id}.")
            return f"You have successfully cooked {dish_name}!"

        except Exception as e:
            logging.error(f"Error in finalize_cooking: {e}")
            return "An error occurred while finalizing the cooking process. Please try again."




    async def add_cooking_xp(self, player_id, xp_gained):
        await self.db.execute("""
            UPDATE player_skills_xp
            SET cooking_xp = cooking_xp + $1
            WHERE playerid = $2
        """, xp_gained, player_id)

# Setup function to load this as an extension
def setup(bot):
    CookingModule(bot)
