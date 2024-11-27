from interactions import Extension, Button, ButtonStyle, ComponentContext, component_callback, StringSelectMenu, StringSelectOption
import logging
import re


class CauldronModule(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    async def get_player_id(self, discord_id):
        """
        Fetch the player ID using the Discord ID.
        """
        return await self.db.fetchval("""
            SELECT playerid FROM players WHERE discord_id = $1
        """, discord_id)

    async def add_ingredient(self, player_id, inventory_id, quantity):
        """
        Add an ingredient to the cauldron, ensuring the ingredient_id is based on itemid.
        """
        # Fetch the current location of the player
        location_id = await self.db.fetchval("""
            SELECT current_location
            FROM player_data
            WHERE playerid = $1
        """, player_id)

        # Fetch the itemid from the inventory table using the inventory_id
        item_id = await self.db.fetchval("""
            SELECT itemid
            FROM inventory
            WHERE inventoryid = $1
        """, inventory_id)

        if not item_id:
            raise ValueError(f"Invalid inventory_id {inventory_id}. No associated itemid found.")

        # Check if the ingredient already exists in the cauldron
        existing_entry = await self.db.fetchrow("""
            SELECT quantity 
            FROM campfire_cauldron
            WHERE player_id = $1 AND location_id = $2 AND ingredient_id = $3
        """, player_id, location_id, item_id)

        if existing_entry:
            # Update the quantity if the ingredient already exists
            await self.db.execute("""
                UPDATE campfire_cauldron
                SET quantity = quantity + $1
                WHERE player_id = $2 AND location_id = $3 AND ingredient_id = $4
            """, quantity, player_id, location_id, item_id)
        else:
            # Insert a new entry if the ingredient does not exist
            await self.db.execute("""
                INSERT INTO campfire_cauldron (player_id, location_id, ingredient_id, quantity)
                VALUES ($1, $2, $3, $4)
            """, player_id, location_id, item_id, quantity)

        logging.info(f"Added item_id {item_id} to the cauldron at location {location_id} for player_id {player_id}.")



    '''async def validate_cauldron(self, player_id, location_id, recipe_id):
        """
        Validate ingredients in the cauldron for a given recipe.
        """
        cauldron_items = await self.db.fetch("""
            SELECT ingredient_id, quantity FROM campfire_cauldron
            WHERE player_id = $1 AND location_id = $2
        """, player_id, location_id)

        recipe = await self.db.fetchrow("""
            SELECT * FROM recipes WHERE recipeid = $1
        """, recipe_id)

        if not recipe:
            return False, "Recipe not found."

        for i in range(1, 7):
            ingredient_id = recipe[f'ingredient{i}_itemid']
            quantity_required = recipe[f'quantity{i}_required']

            if ingredient_id and quantity_required:
                cauldron_quantity = next(
                    (item['quantity'] for item in cauldron_items if item['ingredient_id'] == ingredient_id),
                    0
                )
                if cauldron_quantity < quantity_required:
                    return False, f"Missing ingredient: {await self.get_item_name(ingredient_id)}"

        return True, None'''

    async def get_item_name(self, item_id):
        """
        Fetch the name of an item.
        """
        return await self.db.fetchval("""
            SELECT name FROM items WHERE itemid = $1
        """, item_id)

    '''@component_callback(re.compile(r"^cauldron_validate_\d+$"))
    async def validate_cauldron_handler(self, ctx: ComponentContext):
        """
        Handle ingredient validation for a cauldron.
        """
        player_id = await self.get_player_id(ctx.author.id)
        location_id = await self.bot.travel_system.get_player_location(player_id)
        recipe_id = int(ctx.custom_id.split("_")[-1])

        valid, error = await self.validate_cauldron(player_id, location_id, recipe_id)
        if valid:
            await ctx.send("Ingredients are valid! Ready to cook.", ephemeral=True)
        else:
            await ctx.send(f"Validation failed: {error}", ephemeral=True)'''

    async def remove_ingredient(self, player_id, location_id, ingredient_id, quantity):
        """
        Remove an ingredient from the cauldron.
        """
        await self.db.execute("""
            UPDATE campfire_cauldron
            SET quantity = quantity - $1
            WHERE player_id = $2 AND location_id = $3 AND ingredient_id = $4
        """, quantity, player_id, location_id, ingredient_id)

        await self.db.execute("""
            DELETE FROM campfire_cauldron
            WHERE quantity <= 0
        """)

    async def display_cauldron_interface(self, ctx, player_id, location_id):
        """
        Display the cauldron interface with validation and ingredient management.
        """
        validate_button = Button(
            style=ButtonStyle.primary,
            label="Validate Ingredients",
            custom_id=f"cauldron_validate_{location_id}"
        )

        await ctx.send(
            content="Manage your cauldron here:",
            components=[[validate_button]],
            ephemeral=True
        )

    @component_callback(re.compile(r"^cauldron_view_\d+$"))
    async def view_cauldron_handler(self, ctx: ComponentContext):
        """
        View the cauldron and its contents, including recipe selection.
        """
        try:
            # Fetch the player ID using the Discord ID
            player_id = await self.get_player_id(ctx.author.id)
            if not player_id:
                raise ValueError("Player ID not found for the current user.")

            # Fetch the current location of the player
            location_id = await self.db.fetchval("""
                SELECT current_location
                FROM player_data
                WHERE playerid = $1
            """, player_id)

            # Initialize cauldron_view
            cauldron_view = ""

            # Check for selected recipe
            selected_recipe = await self.db.fetchval("""
                SELECT recipe_id FROM campfire_cauldron
                WHERE player_id = $1 AND location_id = $2 AND recipe_id IS NOT NULL
            """, player_id, location_id)

            recipe_name = None
            if selected_recipe:
                recipe_name = await self.get_item_name(await self.db.fetchval("""
                    SELECT dish_itemid FROM recipes WHERE recipeid = $1
                """, selected_recipe))
                cauldron_view += f"Selected Recipe: {recipe_name}\n\n"
            else:
                cauldron_view += "No recipe selected. Please select one to begin.\n\n"

            # Fetch items in the cauldron
            cauldron_items = await self.db.fetch("""
                SELECT 
                    cc.ingredient_id, 
                    cc.caught_fish_id, 
                    cc.quantity, 
                    i.name AS ingredient_name, 
                    cf.fish_name AS fish_name
                FROM campfire_cauldron cc
                LEFT JOIN items i ON cc.ingredient_id = i.itemid
                LEFT JOIN caught_fish cf ON cc.caught_fish_id = cf.id
                WHERE cc.player_id = $1 AND cc.location_id = $2
            """, player_id, location_id)

            if not cauldron_items:
                cauldron_view += "The cauldron is empty."
            else:
                cauldron_view += "Items in your cauldron:\n"
                for item in cauldron_items:
                    if item['ingredient_id']:
                        # Display the item name if it has an ingredient_id
                        cauldron_view += f"- {item['ingredient_name']} (x{item['quantity']})\n"
                    elif item['caught_fish_id']:
                        # Display the fish name if it has a caught_fish_id
                        cauldron_view += f"- {item['fish_name']} (x{item['quantity']})\n"

            # Add buttons for interactions
            clear_cauldron_button = Button(
                style=ButtonStyle.DANGER,
                label="Clear Cauldron",
                custom_id=f"clear_cauldron_{location_id}"
            )
            add_ingredient_button = Button(
                style=ButtonStyle.SECONDARY,
                label="Add Ingredient",
                custom_id=f"add_ingredient_{location_id}"
            )
            select_recipe_button = Button(
                style=ButtonStyle.PRIMARY,
                label="Select Recipe",
                custom_id=f"cauldron_select_recipe_{location_id}"
            )
            light_flame_button = Button(
                style=ButtonStyle.SUCCESS,
                label="Light Flame",
                custom_id=f"light_flame_{location_id}"
            )

            await ctx.send(
                content=cauldron_view,
                components=[[select_recipe_button, add_ingredient_button, clear_cauldron_button, light_flame_button]],
                ephemeral=True
            )

        except Exception as e:
            logging.error(f"Error in view_cauldron_handler: {e}")
            await ctx.send("An error occurred while viewing the cauldron. Please try again.", ephemeral=True)





    @component_callback(re.compile(r"^clear_cauldron_\d+$"))
    async def clear_cauldron_handler(self, ctx: ComponentContext):
        """
        Clear the cauldron content for the player at a specific location.
        """
        try:
            # Extract the location ID from the custom ID
            location_id = int(ctx.custom_id.split("_")[-1])
            player_id = await self.get_player_id(ctx.author.id)

            # Clear all items in the cauldron for the player at this location
            await self.db.execute("""
                DELETE FROM campfire_cauldron
                WHERE player_id = $1 AND location_id = $2
            """, player_id, location_id)

            await ctx.send("The cauldron has been cleared.", ephemeral=True)

        except Exception as e:
            logging.error(f"Error in clear_cauldron_handler: {e}")
            await ctx.send("An error occurred while clearing the cauldron. Please try again.", ephemeral=True)

    @component_callback(re.compile(r"^add_ingredient_\d+$"))
    async def add_ingredient_handler(self, ctx: ComponentContext):
        """
        Add an ingredient to the cauldron at a specific location.
        """
        try:
            # Extract the location ID from the custom ID
            location_id = int(ctx.custom_id.split("_")[-1])
            player_id = await self.get_player_id(ctx.author.id)

            # Check if the player has selected a recipe
            selected_recipe = await self.db.fetchrow("""
                SELECT 
                    ingredient1_itemid, ingredient2_itemid, ingredient3_itemid,
                    ingredient4_itemid, ingredient5_itemid, ingredient6_itemid,
                    caught_fish_name1, caught_fish_name2, caught_fish_name3
                FROM recipes
                WHERE recipeid = $1
            """, await self.db.fetchval("""
                SELECT recipe_id FROM campfire_cauldron
                WHERE player_id = $1 AND location_id = $2
            """, player_id, location_id))

            if not selected_recipe:
                return await ctx.send(
                    "Please select a recipe before adding ingredients to the cauldron.",
                    ephemeral=True
                )

            # Extract required ingredients and fish names
            required_item_ids = [
                selected_recipe[f"ingredient{i}_itemid"]
                for i in range(1, 7) if selected_recipe[f"ingredient{i}_itemid"]
            ]
            required_fish_names = [
                selected_recipe[f"caught_fish_name{i}"]
                for i in range(1, 4) if selected_recipe[f"caught_fish_name{i}"]
            ]

            # Fetch items from the player's inventory
            inventory_items = await self.db.fetch("""
                SELECT 
                    i.inventoryid,
                    i.itemid,
                    i.caught_fish_id,
                    i.quantity,
                    COALESCE(cf.fish_name, items.name) AS name,
                    CASE
                        WHEN i.caught_fish_id IS NOT NULL THEN 1
                        ELSE i.quantity
                    END AS effective_quantity
                FROM inventory i
                LEFT JOIN items ON i.itemid = items.itemid
                LEFT JOIN caught_fish cf ON i.caught_fish_id = cf.id
                WHERE i.playerid = $1
            """, player_id)

            if not inventory_items:
                return await ctx.send(
                    "No valid items available in your inventory to add to the cauldron.",
                    ephemeral=True
                )

            # Filter items matching required ingredients or fish
            filtered_items = []
            for item in inventory_items:
                if item["itemid"] in required_item_ids:
                    filtered_items.append(item)
                elif item["caught_fish_id"] and (
                    "any" in required_fish_names or item["name"] in required_fish_names
                ):
                    filtered_items.append(item)

            if not filtered_items:
                return await ctx.send(
                    "You don't have any ingredients matching the selected recipe.",
                    ephemeral=True
                )

            # Build the dropdown options dynamically
            options = [
                StringSelectOption(
                    label=f"{item['name']} (x{item['effective_quantity']})",
                    value=f"{item['inventoryid']}"  # Send inventory ID as the selected value
                )
                for item in filtered_items
            ]

            # Create the dropdown menu
            dropdown = StringSelectMenu(
                custom_id=f"select_ingredient_{location_id}_{player_id}",
                placeholder="Choose an ingredient to add to the cauldron"
            )
            # Add the options to the dropdown menu
            dropdown.options.extend(options[:25])  # Limit to the first 25 items

            # Send the dropdown menu as a component
            await ctx.send(
                content="Select an ingredient to add:",
                components=[dropdown],
                ephemeral=True
            )

        except Exception as e:
            logging.error(f"Error in add_ingredient_handler: {e}")
            await ctx.send(
                "An error occurred while adding the ingredient. Please try again.",
                ephemeral=True
            )
















    @component_callback(re.compile(r"^select_ingredient_\d+_\d+$"))
    async def select_ingredient_handler(self, ctx: ComponentContext):
        """
        Handle ingredient selection to add to the cauldron.
        """
        try:
            location_id, player_id = map(int, ctx.custom_id.split("_")[-2:])
            selected_inventory_id = int(ctx.values[0])

            # Fetch the recipe_id for the player's selected recipe
            recipe_id = await self.db.fetchval("""
                SELECT recipe_id FROM campfire_cauldron
                WHERE player_id = $1 AND location_id = $2
            """, player_id, location_id)

            if not recipe_id:
                return await ctx.send(
                    "No recipe selected. Please select a recipe before adding ingredients.",
                    ephemeral=True
                )

            # Check if the player has the selected item in their inventory
            item = await self.db.fetchrow("""
                SELECT itemid, quantity, caught_fish_id, 
                       CASE 
                           WHEN caught_fish_id IS NOT NULL THEN 1
                           ELSE quantity
                       END AS effective_quantity
                FROM inventory
                WHERE playerid = $1 AND inventoryid = $2
            """, player_id, selected_inventory_id)

            # Log the item details for debugging
            logging.info(f"Player {player_id}, Location {location_id}, Selected Item: {item}")

            if not item:
                return await ctx.send("You do not have this item in your inventory.", ephemeral=True)

            # Check if the player has enough of the selected item
            if item['effective_quantity'] <= 0:
                logging.warning(
                    f"Player {player_id} does not have enough of item ID {item['itemid']} (Effective Quantity: {item['effective_quantity']})."
                )
                return await ctx.send("You do not have enough of this item to add.", ephemeral=True)

            # Determine whether to populate `ingredient_id` or `caught_fish_id`
            ingredient_id = item['itemid'] if item['itemid'] else None
            caught_fish_id = item['caught_fish_id'] if item['caught_fish_id'] else None

            # Add the selected item to the cauldron or update its quantity
            await self.db.execute("""
                INSERT INTO campfire_cauldron (player_id, location_id, recipe_id, ingredient_id, caught_fish_id, quantity)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (player_id, location_id, ingredient_id, caught_fish_id)
                DO UPDATE SET quantity = campfire_cauldron.quantity + EXCLUDED.quantity
            """, player_id, location_id, recipe_id, ingredient_id, caught_fish_id, 1)

            # Log successful addition to the cauldron
            logging.info(
                f"Added item {item['itemid']} or fish {item['caught_fish_id']} to cauldron at location {location_id} for player {player_id}."
            )

            # Decrease the quantity of the item in the player's inventory
            await self.db.execute("""
                UPDATE inventory
                SET quantity = quantity - 1
                WHERE playerid = $1 AND inventoryid = $2
            """, player_id, selected_inventory_id)

            # Fetch the name of the added item or fish
            if ingredient_id:
                item_name = await self.get_item_name(ingredient_id)
            elif caught_fish_id:
                item_name = await self.db.fetchval("""
                    SELECT fish_name FROM caught_fish WHERE id = $1
                """, caught_fish_id)
            else:
                item_name = "Unknown Item"

            await ctx.send(f"Added {item_name} to the cauldron.", ephemeral=True)

        except Exception as e:
            logging.error(f"Error in select_ingredient_handler: {e}")
            await ctx.send("An error occurred while adding the ingredient. Please try again.", ephemeral=True)










    @component_callback(re.compile(r"^cauldron_select_recipe_\d+$"))
    async def select_recipe_handler(self, ctx: ComponentContext):
        """
        Allow the player to select a recipe for the cauldron.
        """
        try:
            location_id = int(ctx.custom_id.split("_")[-1])
            player_id = await self.get_player_id(ctx.author.id)

            # Fetch all recipes
            recipes = await self.db.fetch("""
                SELECT recipeid, dish_itemid FROM recipes
            """)

            if not recipes:
                await ctx.send("No recipes are available at the moment.", ephemeral=True)
                return

            # Build dropdown options for recipes
            options = [
                StringSelectOption(
                    label=f"{await self.get_item_name(recipe['dish_itemid'])}",
                    value=str(recipe['recipeid'])
                )
                for recipe in recipes
            ]

            # Create dropdown menu
            dropdown = StringSelectMenu(
                custom_id=f"select_recipe_{location_id}_{player_id}",
                placeholder="Choose a recipe to prepare"
            )
            dropdown.options = options[:25]  # Limit to the first 25 recipes

            await ctx.send(content="Select a recipe:", components=[dropdown], ephemeral=True)

        except Exception as e:
            logging.error(f"Error in select_recipe_handler: {e}")
            await ctx.send("An error occurred while selecting a recipe. selectrecipehandler", ephemeral=True)
            
    @component_callback(re.compile(r"^select_recipe_\d+_\d+$"))
    async def store_selected_recipe(self, ctx: ComponentContext):
        """
        Store the selected recipe in the cauldron for the player.
        """
        try:
            location_id, player_id = map(int, ctx.custom_id.split("_")[-2:])
            recipe_id = int(ctx.values[0])

            # Check if the record already exists
            existing_record = await self.db.fetchval("""
                SELECT recipe_id FROM campfire_cauldron
                WHERE player_id = $1 AND location_id = $2
            """, player_id, location_id)

            if existing_record:
                # Update the existing record if it exists
                await self.db.execute("""
                    UPDATE campfire_cauldron
                    SET recipe_id = $1
                    WHERE player_id = $2 AND location_id = $3
                """, recipe_id, player_id, location_id)
            else:
                # Insert a new record if none exists
                await self.db.execute("""
                    INSERT INTO campfire_cauldron (player_id, location_id, recipe_id)
                    VALUES ($1, $2, $3)
                """, player_id, location_id, recipe_id)

            # Fetch recipe name for confirmation
            recipe_name = await self.get_item_name(await self.db.fetchval("""
                SELECT dish_itemid FROM recipes WHERE recipeid = $1
            """, recipe_id))

            await ctx.send(f"Selected recipe: {recipe_name}. You can now add ingredients.", ephemeral=True)

        except Exception as e:
            logging.error(f"Error in store_selected_recipe: {e}")
            await ctx.send("An error occurred while selecting the recipe. Please try again.", ephemeral=True)

    @component_callback(re.compile(r"^light_flame_\d+$"))
    async def light_flame_handler(self, ctx: ComponentContext):
        """
        Handle the 'Light Flame' button to complete the cooking process.
        """
        try:
            location_id = int(ctx.custom_id.split("_")[-1])
            player_id = await self.get_player_id(ctx.author.id)

            # Fetch the selected recipe_id
            recipe_id = await self.db.fetchval("""
                SELECT recipe_id
                FROM campfire_cauldron
                WHERE player_id = $1 AND location_id = $2
            """, player_id, location_id)

            if not recipe_id:
                await ctx.send("No recipe selected. Please select a recipe first.", ephemeral=True)
                return

            # Fetch the recipe details
            recipe = await self.db.fetchrow("""
                SELECT ingredient1_itemid, ingredient2_itemid, ingredient3_itemid,
                       ingredient4_itemid, ingredient5_itemid, ingredient6_itemid,
                       quantity1_required, quantity2_required, quantity3_required,
                       quantity4_required, quantity5_required, quantity6_required,
                       caught_fish_name1, caught_fish_name2, caught_fish_name3
                FROM recipes
                WHERE recipeid = $1
            """, recipe_id)

            if not recipe:
                await ctx.send("Invalid recipe. Please select a valid recipe.", ephemeral=True)
                return

            # Fetch and aggregate the current cauldron contents
            cauldron_contents = await self.db.fetch("""
                SELECT ingredient_id, caught_fish_id, SUM(quantity) AS total_quantity
                FROM campfire_cauldron
                WHERE player_id = $1 AND location_id = $2
                GROUP BY ingredient_id, caught_fish_id
            """, player_id, location_id)

            # Validate required ingredients
            for i in range(1, 7):
                ingredient_id = recipe[f'ingredient{i}_itemid']
                quantity_required = recipe[f'quantity{i}_required']

                if ingredient_id and quantity_required:
                    cauldron_item = next(
                        (item for item in cauldron_contents if item['ingredient_id'] == ingredient_id),
                        None
                    )
                    if not cauldron_item or cauldron_item['total_quantity'] < quantity_required:
                        missing_item_name = await self.get_item_name(ingredient_id)
                        await ctx.send(
                            f"Missing or insufficient quantity for ingredient: {missing_item_name}.",
                            ephemeral=True
                        )
                        return

            # Validate required caught fish
            for i in range(1, 4):
                fish_name = recipe.get(f'caught_fish_name{i}')

                if fish_name:
                    if fish_name.lower() == "any":
                        # Match any fish in the cauldron with a caught_fish_id
                        matching_fish = [
                            item for item in cauldron_contents if item['caught_fish_id']
                        ]
                    else:
                        # Match fish with a specific name
                        matching_fish = [
                            item for item in cauldron_contents if item['caught_fish_id']
                            and await self.db.fetchval(
                                "SELECT fish_name FROM caught_fish WHERE id = $1",
                                item['caught_fish_id']
                            ) == fish_name
                        ]

                    # Check if sufficient quantity is available
                    if not matching_fish or sum(f['total_quantity'] for f in matching_fish) < 1:
                        await ctx.send(
                            f"Missing required fish: {fish_name}.",
                            ephemeral=True
                        )
                        return

            # If validation succeeds, cook the dish
            dish_itemid = await self.db.fetchval("""
                SELECT dish_itemid
                FROM recipes
                WHERE recipeid = $1
            """, recipe_id)

            # Add the dish to the player's inventory
            await self.db.execute("""
                INSERT INTO inventory (playerid, itemid, quantity)
                VALUES ($1, $2, $3)
                ON CONFLICT (playerid, itemid)
                DO UPDATE SET quantity = inventory.quantity + EXCLUDED.quantity
            """, player_id, dish_itemid, 1)

            # Clear the cauldron
            await self.db.execute("""
                DELETE FROM campfire_cauldron
                WHERE player_id = $1 AND location_id = $2
            """, player_id, location_id)

            # Notify the user of success
            await ctx.send(f"You successfully cooked {await self.get_item_name(dish_itemid)}!", ephemeral=True)

        except Exception as e:
            logging.error(f"Error in light_flame_handler: {e}")
            await ctx.send("An error occurred while lighting the flame. Please try again.", ephemeral=True)







# Setup function to load this as an extension
def setup(bot):
    CauldronModule(bot)
