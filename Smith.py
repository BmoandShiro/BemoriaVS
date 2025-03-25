import logging
from interactions import (
    Extension, 
    Button, 
    ButtonStyle, 
    ComponentContext, 
    component_callback,
    StringSelectMenu, 
    StringSelectOption
)
import re
from typing import Dict, List, Tuple

class SmithModule(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        # Define crafting requirements for armor
        # Format: armor_itemid: (bar_itemid, quantity)
        self.smith_recipes = {
            # Bronze Armor (IDs 1-5, using Bronze Bar 210)
            1: {'bar_id': 210, 'bar_amount': 5},  # Bronze Helmet - 5 bars
            2: {'bar_id': 210, 'bar_amount': 12}, # Bronze Chestplate - 12 bars
            3: {'bar_id': 210, 'bar_amount': 4},  # Bronze Gauntlets - 4 bars
            4: {'bar_id': 210, 'bar_amount': 9},  # Bronze Leggings - 9 bars
            5: {'bar_id': 210, 'bar_amount': 6},  # Bronze Boots - 6 bars
            
            # Iron Armor (IDs 6-10, using Iron Bar 230)
            6: {'bar_id': 230, 'bar_amount': 5},  # Iron Helmet - 5 bars
            7: {'bar_id': 230, 'bar_amount': 12}, # Iron Chestplate - 12 bars
            8: {'bar_id': 230, 'bar_amount': 4},  # Iron Gauntlets - 4 bars
            9: {'bar_id': 230, 'bar_amount': 9},  # Iron Leggings - 9 bars
            10: {'bar_id': 230, 'bar_amount': 6}, # Iron Boots - 6 bars
            
            # Steel Armor (IDs 11-15, using Steel Bar 231)
            11: {'bar_id': 231, 'bar_amount': 5},  # Steel Helmet - 5 bars
            12: {'bar_id': 231, 'bar_amount': 12}, # Steel Chestplate - 12 bars
            13: {'bar_id': 231, 'bar_amount': 4},  # Steel Gauntlets - 4 bars
            14: {'bar_id': 231, 'bar_amount': 9},  # Steel Leggings - 9 bars
            15: {'bar_id': 231, 'bar_amount': 6},  # Steel Boots - 6 bars
        }

    async def get_player_id(self, discord_id):
        """Fetch the player ID using the Discord ID."""
        return await self.db.fetchval("""
            SELECT playerid FROM players WHERE discord_id = $1
        """, str(discord_id))

    async def get_item_name(self, item_id):
        """Fetch the name of an item."""
        if item_id is None:
            return None
        return await self.db.fetchval("""
            SELECT name FROM items WHERE itemid = $1
        """, item_id)

    async def check_materials(self, player_id: int, bar_id: int, required_qty: int) -> bool:
        """Check if player has enough metal bars."""
        try:
            quantity = await self.db.fetchval("""
                SELECT quantity FROM inventory
                WHERE playerid = $1 AND itemid = $2
            """, player_id, bar_id)
            
            logging.info(f"Checking materials for player {player_id}: itemid {bar_id}, required {required_qty}, has {quantity}")
            has_enough = quantity is not None and quantity >= required_qty
            logging.info(f"Has enough materials: {has_enough}")
            return has_enough
        except Exception as e:
            logging.error(f"Error in check_materials: {e}")
            return False

    async def get_available_armor(self, player_id: int) -> List[Dict]:
        """Get list of armor that can be crafted based on player's inventory."""
        available_armor = []
        
        # First, let's check what bars the player has
        bars = await self.db.fetch("""
            SELECT i.itemid, i.quantity, items.name, items.description, items.type, items.rarity
            FROM inventory i 
            JOIN items ON i.itemid = items.itemid 
            WHERE i.playerid = $1 
            AND i.in_bank = FALSE
            AND items.type = 'bar'
            AND i.quantity > 0
        """, player_id)
        
        if not bars:
            logging.info(f"Player {player_id} has no bars in inventory")
            return []
            
        # Log each bar found
        for bar in bars:
            logging.info(f"Found bar in inventory: ID={bar['itemid']}, Name={bar['name']}, Quantity={bar['quantity']}, Type={bar['type']}")
        
        # Create a dict of bar quantities for easy lookup
        bar_quantities = {bar['itemid']: bar['quantity'] for bar in bars}
        logging.info(f"Bar quantities dictionary: {bar_quantities}")
        
        # For each recipe, check if we have enough materials
        for armor_id, recipe in self.smith_recipes.items():
            logging.info(f"\nChecking recipe for armor_id {armor_id}:")
            logging.info(f"- Requires {recipe['bar_amount']}x bar_id {recipe['bar_id']}")
            
            # Check if we have enough of the required bar
            available_qty = bar_quantities.get(recipe['bar_id'], 0)
            has_materials = available_qty >= recipe['bar_amount']
            logging.info(f"- Have {available_qty} bars, need {recipe['bar_amount']}, has_enough: {has_materials}")
            
            if not has_materials:
                logging.info(f"- Skipping armor {armor_id}: insufficient materials")
                continue
                
            # Get complete item data for both armor and bar
            armor_data = await self.db.fetchrow("""
                SELECT itemid, name, description, type, rarity
                FROM items 
                WHERE itemid = $1
            """, armor_id)
            
            if not armor_data:
                logging.info(f"- Skipping armor {armor_id}: armor data not found")
                continue
                
            logging.info(f"- Found armor data: {armor_data}")
            logging.info(f"- Armor type: {armor_data['type']}")
            
            # Check if the type is valid
            valid_types = ['Helmet', 'Chestplate', 'Gauntlets', 'Leggings', 'Boots', 
                          'Headpiece', 'Chestpiece', 'Gloves']
            if armor_data['type'] not in valid_types:
                logging.info(f"- Skipping armor {armor_id}: invalid type '{armor_data['type']}'. Valid types are: {valid_types}")
                continue
                
            bar_data = await self.db.fetchrow("""
                SELECT name, description, type, rarity
                FROM items 
                WHERE itemid = $1 AND type = 'bar'
            """, recipe['bar_id'])
            
            if not bar_data:
                logging.info(f"- Skipping armor {armor_id}: bar data not found or not of type 'bar'")
                continue
            
            armor_info = {
                'name': armor_data['name'],
                'itemid': armor_id,
                'bar_id': recipe['bar_id'],
                'bar_name': bar_data['name'],
                'required_qty': recipe['bar_amount'],
                'description': armor_data['description'],
                'armor': 0,  # Temporary placeholder until we add armor column
                'rarity': armor_data['rarity']
            }
            available_armor.append(armor_info)
            logging.info(f"- Added to available armor: {armor_info['name']} (requires {recipe['bar_amount']}x {bar_data['name']})")
        
        logging.info(f"\nFinal available armor list ({len(available_armor)} items):")
        for armor in available_armor:
            logging.info(f"- {armor['name']} (Armor: {armor['armor']}) - Requires: {armor['required_qty']}x {armor['bar_name']}")
        
        return available_armor

    @component_callback(re.compile(r"^smith_\d+$"))
    async def smith_button_handler(self, ctx: ComponentContext):
        """Handle the smith button click."""
        try:
            # Get player ID directly from players table using discord_id
            player_id = await self.db.fetchval("""
                SELECT playerid FROM players 
                WHERE discord_id = $1
            """, ctx.author.id)  # Discord ID is already a number, no need for str() or casting

            if not player_id:
                await ctx.send("Could not find your player data. Please make sure you're registered.", ephemeral=True)
                return

            await ctx.defer(ephemeral=True)
            await self.display_smith_interface(ctx, player_id)
        except Exception as e:
            logging.error(f"Error in smith_button_handler: {e}")
            await ctx.send("An error occurred. Please try again.", ephemeral=True)

    async def display_smith_interface(self, ctx, player_id):
        """Display the smithing interface with armor selection."""
        smith_button = Button(
            style=ButtonStyle.PRIMARY,
            label="Craft Armor",
            custom_id=f"smith_craft_{player_id}"  # Using player_id from database
        )

        await ctx.send(
            content="Welcome to the smithy! Click to see available armor to craft:",
            components=[[smith_button]],
            ephemeral=True
        )

    @component_callback(re.compile(r"^smith_craft_\d+$"))
    async def smith_craft_handler(self, ctx: ComponentContext):
        """Handle the armor crafting process."""
        try:
            # Get player ID from the button's custom_id
            player_id = int(ctx.custom_id.split("_")[2])
            logging.info(f"Smith craft handler called for player_id: {player_id}")
            
            # Verify this player is the one who clicked
            authorized_discord_id = await self.db.fetchval("""
                SELECT discord_id::text FROM players 
                WHERE playerid = $1
            """, player_id)
            
            if str(ctx.author.id) != authorized_discord_id:
                await ctx.send("You are not authorized to use this button.", ephemeral=True)
                return

            # Get available armor based on inventory
            available_armor = await self.get_available_armor(player_id)
            logging.info(f"Available armor for player {player_id}: {available_armor}")

            if not available_armor:
                await ctx.send("You don't have enough materials to craft any armor.", ephemeral=True)
                return

            # Create dropdown options for available armor
            options = []
            for armor in available_armor:
                option = StringSelectOption(
                    label=f"{armor['name']} (Armor: {armor['armor']})",
                    value=str(armor['itemid']),
                    description=f"Requires: {armor['required_qty']}x {armor['bar_name']} | {armor['rarity']}"
                )
                options.append(option)
                logging.info(f"Added dropdown option: {armor['name']}")

            # Create dropdown menu
            dropdown = StringSelectMenu(
                custom_id=f"select_armor_{player_id}",
                placeholder="Choose armor to craft"
            )
            # Set options after creating the menu
            dropdown.options = options[:25]  # Limit to 25 options

            await ctx.send(
                content="Select armor to craft:",
                components=[dropdown],
                ephemeral=True
            )

        except Exception as e:
            logging.error(f"Error in smith_craft_handler: {e}")
            await ctx.send("An error occurred while accessing the smithy. Please try again.", ephemeral=True)

    @component_callback(re.compile(r"^select_armor_\d+$"))
    async def select_armor_handler(self, ctx: ComponentContext):
        """Handle armor selection and create it from bars."""
        try:
            # Get player ID from the dropdown's custom_id
            player_id = int(ctx.custom_id.split("_")[2])
            
            # Verify this player is the one who clicked
            authorized_discord_id = await self.db.fetchval("""
                SELECT discord_id::text FROM players 
                WHERE playerid = $1
            """, player_id)
            
            if str(ctx.author.id) != authorized_discord_id:
                await ctx.send("You are not authorized to use this dropdown.", ephemeral=True)
                return

            selected_armor_id = int(ctx.values[0])
            
            recipe = self.smith_recipes.get(selected_armor_id)
            if not recipe:
                await ctx.send("Invalid armor selection.", ephemeral=True)
                return

            bar_id, required_qty = recipe['bar_id'], recipe['bar_amount']
            
            # Verify materials again
            if not await self.check_materials(player_id, bar_id, required_qty):
                await ctx.send("You no longer have enough materials.", ephemeral=True)
                return

            # Remove bars from inventory
            await self.db.execute("""
                UPDATE inventory
                SET quantity = quantity - $1
                WHERE playerid = $2 AND itemid = $3
            """, required_qty, player_id, bar_id)

            # Add the armor to inventory
            await self.db.execute("""
                INSERT INTO inventory (playerid, itemid, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (playerid, itemid)
                DO UPDATE SET quantity = inventory.quantity + 1
            """, player_id, selected_armor_id)

            # Get names for message
            armor_name = await self.get_item_name(selected_armor_id)
            bar_name = await self.get_item_name(bar_id)

            await ctx.send(
                f"Successfully crafted {armor_name}! (Used: {required_qty}x {bar_name})",
                ephemeral=True
            )

            # Clean up inventory (remove items with quantity 0)
            await self.db.execute("""
                DELETE FROM inventory
                WHERE quantity <= 0
            """)

        except Exception as e:
            logging.error(f"Error in select_armor_handler: {e}")
            await ctx.send("An error occurred while crafting the armor. Please try again.", ephemeral=True)

# Setup function to load this as an extension
def setup(bot):
    """Setup function to add the extension to the bot."""
    SmithModule(bot) 