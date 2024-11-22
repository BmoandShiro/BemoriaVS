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

    async def add_ingredient(self, player_id, location_id, ingredient_id, quantity):
        """
        Add an ingredient to the cauldron.
        """
        existing_entry = await self.db.fetchrow("""
            SELECT quantity FROM campfire_cauldron
            WHERE player_id = $1 AND location_id = $2 AND ingredient_id = $3
        """, player_id, location_id, ingredient_id)

        if existing_entry:
            await self.db.execute("""
                UPDATE campfire_cauldron
                SET quantity = quantity + $1
                WHERE player_id = $2 AND location_id = $3 AND ingredient_id = $4
            """, quantity, player_id, location_id, ingredient_id)
        else:
            await self.db.execute("""
                INSERT INTO campfire_cauldron (player_id, location_id, ingredient_id, quantity)
                VALUES ($1, $2, $3, $4)
            """, player_id, location_id, ingredient_id, quantity)

    async def validate_cauldron(self, player_id, location_id, recipe_id):
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

        return True, None

    async def get_item_name(self, item_id):
        """
        Fetch the name of an item.
        """
        return await self.db.fetchval("""
            SELECT name FROM items WHERE itemid = $1
        """, item_id)

    @component_callback(re.compile(r"^cauldron_validate_\d+$"))
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
            await ctx.send(f"Validation failed: {error}", ephemeral=True)

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
        try:
            # Fetch player_id using discordid
            player_id = await self.get_player_id(ctx.author.id)
            if not player_id:
                await ctx.send("Player not found. Please register first.", ephemeral=True)
                return

            # Fetch items in the cauldron for the player
            cauldron_items = await self.db.fetch("""
                SELECT cc.ingredient_id, cc.quantity, i.name AS ingredient_name
                FROM campfire_cauldron cc
                JOIN items i ON cc.ingredient_id = i.itemid
                WHERE cc.player_id = $1
            """, player_id)

            # Build the cauldron view content
            if not cauldron_items:
                cauldron_view = "The cauldron is empty."
            else:
                cauldron_view = "Items in your cauldron:\n"
                for item in cauldron_items:
                    cauldron_view += f"- {item['ingredient_name']} (x{item['quantity']})\n"

            # Add buttons for interacting with the cauldron
            clear_cauldron_button = Button(
                style=ButtonStyle.DANGER,
                label="Clear Cauldron",
                custom_id=f"clear_cauldron_{player_id}"
            )
            add_ingredient_button = Button(
                style=ButtonStyle.SECONDARY,
                label="Add Ingredient",
                custom_id=f"add_ingredient_{player_id}"
            )

            # Send the cauldron view with buttons
            await ctx.send(
                content=cauldron_view,
                components=[[add_ingredient_button, clear_cauldron_button]],
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

            # Fetch items from the player's inventory
            inventory_items = await self.db.fetch("""
                SELECT 
                    i.inventoryid,
                    i.itemid,
                    i.caught_fish_id,
                    i.quantity,
                    CASE 
                        WHEN i.caught_fish_id IS NOT NULL THEN cf.fish_name
                        ELSE items.name
                    END AS name,
                    CASE
                        WHEN i.caught_fish_id IS NOT NULL THEN 1
                        ELSE i.quantity
                    END AS effective_quantity
                FROM 
                    inventory i
                LEFT JOIN 
                    items ON i.itemid = items.itemid
                LEFT JOIN 
                    caught_fish cf ON i.caught_fish_id = cf.id
                WHERE 
                    i.playerid = $1
            """, player_id)

            if not inventory_items:
                return await ctx.send("No valid items available to add to the cauldron.", ephemeral=True)

            # Build the dropdown options
            options = [
                StringSelectOption(
                    label=f"{item['name']} (x{item['effective_quantity']})",
                    value=str(item['inventoryid'])
                )
                for item in inventory_items
            ]

            # Create a dropdown menu
            dropdown = StringSelectMenu(
                custom_id=f"select_ingredient_{location_id}_{player_id}",
                placeholder="Choose an ingredient to add to the cauldron",
            )
            dropdown.options = options[:25]  # Add options here, limiting to 25

            await ctx.send(content="Select an ingredient to add:", components=[dropdown], ephemeral=True)

        except Exception as e:
            logging.error(f"Error in add_ingredient_handler: {e}")
            await ctx.send("An error occurred while adding the ingredient. Please try again.", ephemeral=True)








    @component_callback(re.compile(r"^select_ingredient_\d+_\d+$"))
    async def select_ingredient_handler(self, ctx: ComponentContext):
        """
        Handle ingredient selection to add to the cauldron.
        """
        try:
            location_id, player_id = map(int, ctx.custom_id.split("_")[-2:])
            selected_item_id = int(ctx.values[0])

            # Check if the player has the selected item in their inventory
            item = await self.db.fetchrow("""
                SELECT itemid, quantity
                FROM inventory
                WHERE playerid = $1 AND itemid = $2
            """, player_id, selected_item_id)

            if not item or item['quantity'] <= 0:
                return await ctx.send("You do not have enough of this item to add.", ephemeral=True)

            # Add the selected item to the cauldron or update its quantity
            await self.db.execute("""
                INSERT INTO campfire_cauldron (player_id, location_id, ingredient_id, quantity)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (player_id, location_id, ingredient_id)
                DO UPDATE SET quantity = campfire_cauldron.quantity + EXCLUDED.quantity
            """, player_id, location_id, selected_item_id, 1)

            # Decrease the quantity of the item in the player's inventory
            await self.db.execute("""
                UPDATE inventory
                SET quantity = quantity - 1
                WHERE playerid = $1 AND itemid = $2
            """, player_id, selected_item_id)

            await ctx.send(f"Added {await self.get_item_name(selected_item_id)} to the cauldron.", ephemeral=True)

        except Exception as e:
            logging.error(f"Error in select_ingredient_handler: {e}")
            await ctx.send("An error occurred while adding the ingredient. Please try again.", ephemeral=True)


# Setup function to load this as an extension
def setup(bot):
    CauldronModule(bot)
