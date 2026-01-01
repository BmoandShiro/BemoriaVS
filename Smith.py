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
        
        # Define crafting requirements for tools
        # Format: tool_itemid: (bar_itemid, quantity)
        # Tool recipes will be loaded dynamically by name to avoid hardcoding item IDs
        self.tool_recipe_definitions = {
            # Tool name: (bar_itemid, bar_amount)
            'Iron Hatchet': {'bar_id': 230, 'bar_amount': 3},  # 3 Iron Bars
        }
        self.tool_recipes = {}  # Will be populated with item IDs
        
        # Define crafting requirements for weapons
        # Format: weapon_itemid: {'bar_id': bar_itemid, 'bar_amount': quantity, 'smithing_level': level}
        # Bronze Weapons (itemid 71-78)
        self.weapon_recipes = {
            71: {'bar_id': 210, 'bar_amount': 1, 'smithing_level': 1},  # Bronze Dagger
            72: {'bar_id': 210, 'bar_amount': 3, 'smithing_level': 4},  # Bronze Battle Axe
            73: {'bar_id': 210, 'bar_amount': 2, 'smithing_level': 3},  # Bronze Hatchet
            74: {'bar_id': 210, 'bar_amount': 2, 'smithing_level': 3},  # Bronze Short Sword
            75: {'bar_id': 210, 'bar_amount': 3, 'smithing_level': 4},  # Bronze Long Sword
            76: {'bar_id': 210, 'bar_amount': 4, 'smithing_level': 5},  # Bronze Greatsword
            77: {'bar_id': 210, 'bar_amount': 3, 'smithing_level': 4},  # Bronze Polearm
            78: {'bar_id': 210, 'bar_amount': 2, 'smithing_level': 3},  # Bronze Spear
            
            # Iron Weapons (itemid 79-86)
            79: {'bar_id': 230, 'bar_amount': 1, 'smithing_level': 6},  # Iron Dagger
            80: {'bar_id': 230, 'bar_amount': 3, 'smithing_level': 10}, # Iron Battle Axe
            81: {'bar_id': 230, 'bar_amount': 2, 'smithing_level': 8},   # Iron Hatchet
            82: {'bar_id': 230, 'bar_amount': 2, 'smithing_level': 8},   # Iron Short Sword
            83: {'bar_id': 230, 'bar_amount': 3, 'smithing_level': 10}, # Iron Long Sword
            84: {'bar_id': 230, 'bar_amount': 4, 'smithing_level': 12}, # Iron Greatsword
            85: {'bar_id': 230, 'bar_amount': 3, 'smithing_level': 10}, # Iron Polearm
            86: {'bar_id': 230, 'bar_amount': 2, 'smithing_level': 8},   # Iron Spear
            
            # Steel Weapons (itemid 87-94)
            87: {'bar_id': 231, 'bar_amount': 1, 'smithing_level': 13},  # Steel Dagger
            88: {'bar_id': 231, 'bar_amount': 3, 'smithing_level': 17},   # Steel Battle Axe
            89: {'bar_id': 231, 'bar_amount': 2, 'smithing_level': 15},  # Steel Hatchet
            90: {'bar_id': 231, 'bar_amount': 2, 'smithing_level': 15},  # Steel Short Sword
            91: {'bar_id': 231, 'bar_amount': 3, 'smithing_level': 17},  # Steel Long Sword
            92: {'bar_id': 231, 'bar_amount': 4, 'smithing_level': 20},  # Steel Greatsword
            93: {'bar_id': 231, 'bar_amount': 3, 'smithing_level': 17},  # Steel Polearm
            94: {'bar_id': 231, 'bar_amount': 2, 'smithing_level': 15},  # Steel Spear
            
            # Necrosteel Weapons (itemid 95-102)
            # NOTE: Necrosteel Bar ID is set to 232 as placeholder - update if different
            95: {'bar_id': 232, 'bar_amount': 1, 'smithing_level': 25},  # Necrosteel Dagger
            96: {'bar_id': 232, 'bar_amount': 3, 'smithing_level': 30},   # Necrosteel Battle Axe
            97: {'bar_id': 232, 'bar_amount': 2, 'smithing_level': 28},  # Necrosteel Hatchet
            98: {'bar_id': 232, 'bar_amount': 2, 'smithing_level': 28},  # Necrosteel Short Sword
            99: {'bar_id': 232, 'bar_amount': 3, 'smithing_level': 30},   # Necrosteel Long Sword
            100: {'bar_id': 232, 'bar_amount': 4, 'smithing_level': 35},  # Necrosteel Greatsword
            101: {'bar_id': 232, 'bar_amount': 3, 'smithing_level': 30}, # Necrosteel Polearm
            102: {'bar_id': 232, 'bar_amount': 2, 'smithing_level': 28}, # Necrosteel Spear
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

    async def get_smithing_level(self, player_id: int) -> int:
        """Get player's smithing level."""
        try:
            level = await self.db.fetchval("""
                SELECT smithing_level FROM players WHERE playerid = $1
            """, player_id)
            return level if level is not None else 1
        except Exception as e:
            logging.error(f"Error in get_smithing_level: {e}")
            return 1

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
            valid_types = [
                'Helmet', 'Chest', 'Hands', 'Legs', 'Feet',  # Base armor slots
                'Back', 'Neck', 'Finger', 'Shield', 'Weapon'  # Additional equipment slots
            ]
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

    async def get_available_tools(self, player_id: int) -> List[Dict]:
        """Get list of tools that can be crafted based on player's inventory."""
        available_tools = []
        
        # First, check what bars the player has
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
            logging.info(f"Player {player_id} has no bars in inventory for tool crafting")
            return []
        
        # Create a dict of bar quantities for easy lookup
        bar_quantities = {bar['itemid']: bar['quantity'] for bar in bars}
        
        # Load tool recipes by looking up item IDs by name
        if not self.tool_recipes:
            for tool_name, recipe in self.tool_recipe_definitions.items():
                tool_id = await self.db.fetchval("""
                    SELECT itemid FROM items WHERE LOWER(name) = LOWER($1)
                """, tool_name)
                if tool_id:
                    self.tool_recipes[tool_id] = recipe
                    logging.info(f"Loaded tool recipe: {tool_name} (ID: {tool_id}) requires {recipe['bar_amount']}x bar_id {recipe['bar_id']}")
        
        # For each tool recipe, check if we have enough materials
        for tool_id, recipe in self.tool_recipes.items():
            available_qty = bar_quantities.get(recipe['bar_id'], 0)
            has_materials = available_qty >= recipe['bar_amount']
            
            if not has_materials:
                continue
            
            # Get tool data
            tool_data = await self.db.fetchrow("""
                SELECT itemid, name, description, type, rarity
                FROM items 
                WHERE itemid = $1
            """, tool_id)
            
            if not tool_data:
                continue
            
            # Get bar data
            bar_data = await self.db.fetchrow("""
                SELECT name FROM items 
                WHERE itemid = $1 AND type = 'bar'
            """, recipe['bar_id'])
            
            if not bar_data:
                continue
            
            tool_info = {
                'name': tool_data['name'],
                'itemid': tool_id,
                'bar_id': recipe['bar_id'],
                'bar_name': bar_data['name'],
                'required_qty': recipe['bar_amount'],
                'description': tool_data['description'],
                'rarity': tool_data['rarity']
            }
            available_tools.append(tool_info)
        
        return available_tools

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
        """Display the smithing interface with armor, tool, and weapon selection."""
        craft_armor_button = Button(
            style=ButtonStyle.PRIMARY,
            label="Craft Armor",
            custom_id=f"smith_craft_{player_id}"  # Using player_id from database
        )
        
        craft_tool_button = Button(
            style=ButtonStyle.PRIMARY,
            label="Craft Tool",
            custom_id=f"smith_craft_tool_{player_id}"
        )
        
        craft_weapon_button = Button(
            style=ButtonStyle.PRIMARY,
            label="Craft Weapon",
            custom_id=f"smith_craft_weapon_{player_id}"
        )

        await ctx.send(
            content="Welcome to the smithy! Choose what to craft:",
            components=[[craft_armor_button, craft_tool_button, craft_weapon_button]],
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

    @component_callback(re.compile(r"^smith_craft_tool_\d+$"))
    async def smith_craft_tool_handler(self, ctx: ComponentContext):
        """Handle the tool crafting process."""
        try:
            # Get player ID from the button's custom_id
            player_id = int(ctx.custom_id.split("_")[3])
            logging.info(f"Smith craft tool handler called for player_id: {player_id}")
            
            # Verify this player is the one who clicked
            authorized_discord_id = await self.db.fetchval("""
                SELECT discord_id::text FROM players 
                WHERE playerid = $1
            """, player_id)
            
            if str(ctx.author.id) != authorized_discord_id:
                await ctx.send("You are not authorized to use this button.", ephemeral=True)
                return

            # Get available tools based on inventory
            available_tools = await self.get_available_tools(player_id)
            logging.info(f"Available tools for player {player_id}: {available_tools}")

            if not available_tools:
                await ctx.send("You don't have enough materials to craft any tools.", ephemeral=True)
                return

            # Create dropdown options for available tools
            options = []
            for tool in available_tools:
                option = StringSelectOption(
                    label=f"{tool['name']}",
                    value=str(tool['itemid']),
                    description=f"Requires: {tool['required_qty']}x {tool['bar_name']} | {tool['rarity']}"
                )
                options.append(option)
                logging.info(f"Added dropdown option: {tool['name']}")

            # Create dropdown menu
            dropdown = StringSelectMenu(
                custom_id=f"select_tool_{player_id}",
                placeholder="Choose tool to craft"
            )
            # Set options after creating the menu
            dropdown.options = options[:25]  # Limit to 25 options

            await ctx.send(
                content="Select tool to craft:",
                components=[dropdown],
                ephemeral=True
            )

        except Exception as e:
            logging.error(f"Error in smith_craft_tool_handler: {e}")
            await ctx.send("An error occurred while accessing the smithy. Please try again.", ephemeral=True)

    @component_callback(re.compile(r"^select_tool_\d+$"))
    async def select_tool_handler(self, ctx: ComponentContext):
        """Handle tool selection and create it from bars."""
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

            selected_tool_id = int(ctx.values[0])
            
            recipe = self.tool_recipes.get(selected_tool_id)
            if not recipe:
                await ctx.send("Invalid tool selection.", ephemeral=True)
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

            # Add the tool to inventory
            await self.db.execute("""
                INSERT INTO inventory (playerid, itemid, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (playerid, itemid)
                DO UPDATE SET quantity = inventory.quantity + 1
            """, player_id, selected_tool_id)

            # Get names for message
            tool_name = await self.get_item_name(selected_tool_id)
            bar_name = await self.get_item_name(bar_id)

            await ctx.send(
                f"Successfully crafted {tool_name}! (Used: {required_qty}x {bar_name})",
                ephemeral=True
            )

            # Clean up inventory (remove items with quantity 0)
            await self.db.execute("""
                DELETE FROM inventory
                WHERE quantity <= 0
            """)

        except Exception as e:
            logging.error(f"Error in select_tool_handler: {e}")
            await ctx.send("An error occurred while crafting the tool. Please try again.", ephemeral=True)

    async def get_available_weapons(self, player_id: int) -> List[Dict]:
        """Get list of weapons that can be crafted based on player's inventory and smithing level."""
        available_weapons = []
        
        # Get player's smithing level
        player_level = await self.get_smithing_level(player_id)
        
        # First, check what bars the player has
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
            logging.info(f"Player {player_id} has no bars in inventory for weapon crafting")
            return []
        
        # Create a dict of bar quantities for easy lookup
        bar_quantities = {bar['itemid']: bar['quantity'] for bar in bars}
        
        # For each weapon recipe, check if we have enough materials and level
        for weapon_id, recipe in self.weapon_recipes.items():
            # Check smithing level requirement
            if player_level < recipe['smithing_level']:
                continue
            
            # Check if we have enough of the required bar
            available_qty = bar_quantities.get(recipe['bar_id'], 0)
            has_materials = available_qty >= recipe['bar_amount']
            
            if not has_materials:
                continue
            
            # Get weapon data
            weapon_data = await self.db.fetchrow("""
                SELECT itemid, name, description, type, rarity,
                       slashing_damage, piercing_damage, crushing_damage, dark_damage
                FROM items 
                WHERE itemid = $1
            """, weapon_id)
            
            if not weapon_data:
                continue
            
            # Get bar data
            bar_data = await self.db.fetchrow("""
                SELECT name FROM items 
                WHERE itemid = $1 AND type = 'bar'
            """, recipe['bar_id'])
            
            if not bar_data:
                continue
            
            # Calculate total damage
            total_damage = (
                (weapon_data['slashing_damage'] or 0) +
                 (weapon_data['piercing_damage'] or 0) +
                 (weapon_data['crushing_damage'] or 0) +
                 (weapon_data['dark_damage'] or 0))
            
            weapon_info = {
                'name': weapon_data['name'],
                'itemid': weapon_id,
                'bar_id': recipe['bar_id'],
                'bar_name': bar_data['name'],
                'required_qty': recipe['bar_amount'],
                'smithing_level': recipe['smithing_level'],
                'description': weapon_data['description'],
                'rarity': weapon_data['rarity'],
                'total_damage': total_damage,
                'slashing': weapon_data['slashing_damage'] or 0,
                'piercing': weapon_data['piercing_damage'] or 0,
                'crushing': weapon_data['crushing_damage'] or 0,
                'dark': weapon_data['dark_damage'] or 0
            }
            available_weapons.append(weapon_info)
        
        return available_weapons

    @component_callback(re.compile(r"^smith_craft_weapon_\d+$"))
    async def smith_craft_weapon_handler(self, ctx: ComponentContext):
        """Handle the weapon crafting process."""
        try:
            # Get player ID from the button's custom_id
            player_id = int(ctx.custom_id.split("_")[3])
            logging.info(f"Smith craft weapon handler called for player_id: {player_id}")
            
            # Verify this player is the one who clicked
            authorized_discord_id = await self.db.fetchval("""
                SELECT discord_id::text FROM players 
                WHERE playerid = $1
            """, player_id)
            
            if str(ctx.author.id) != authorized_discord_id:
                await ctx.send("You are not authorized to use this button.", ephemeral=True)
                return

            # Get available weapons based on inventory and level
            available_weapons = await self.get_available_weapons(player_id)
            logging.info(f"Available weapons for player {player_id}: {available_weapons}")

            if not available_weapons:
                await ctx.send("You don't have enough materials or smithing level to craft any weapons.", ephemeral=True)
                return

            # Create dropdown options for available weapons
            options = []
            for weapon in available_weapons:
                damage_str = f"S:{weapon['slashing']}/P:{weapon['piercing']}/C:{weapon['crushing']}"
                if weapon['dark'] > 0:
                    damage_str += f"/D:{weapon['dark']}"
                option = StringSelectOption(
                    label=f"{weapon['name']} (Total: {weapon['total_damage']})",
                    value=str(weapon['itemid']),
                    description=f"Req: {weapon['required_qty']}x {weapon['bar_name']} | Lvl: {weapon['smithing_level']} | {damage_str}"
                )
                options.append(option)
                logging.info(f"Added dropdown option: {weapon['name']}")

            # Create dropdown menu
            dropdown = StringSelectMenu(
                custom_id=f"select_weapon_{player_id}",
                placeholder="Choose weapon to craft"
            )
            # Set options after creating the menu
            dropdown.options = options[:25]  # Limit to 25 options

            await ctx.send(
                content="Select weapon to craft:",
                components=[dropdown],
                ephemeral=True
            )

        except Exception as e:
            logging.error(f"Error in smith_craft_weapon_handler: {e}")
            await ctx.send("An error occurred while accessing the smithy. Please try again.", ephemeral=True)

    @component_callback(re.compile(r"^select_weapon_\d+$"))
    async def select_weapon_handler(self, ctx: ComponentContext):
        """Handle weapon selection and create it from bars."""
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

            selected_weapon_id = int(ctx.values[0])
            
            recipe = self.weapon_recipes.get(selected_weapon_id)
            if not recipe:
                await ctx.send("Invalid weapon selection.", ephemeral=True)
                return

            # Check smithing level
            player_level = await self.get_smithing_level(player_id)
            if player_level < recipe['smithing_level']:
                await ctx.send(f"You need smithing level {recipe['smithing_level']} to craft this weapon. You are level {player_level}.", ephemeral=True)
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

            # Add the weapon to inventory
            await self.db.execute("""
                INSERT INTO inventory (playerid, itemid, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (playerid, itemid)
                DO UPDATE SET quantity = inventory.quantity + 1
            """, player_id, selected_weapon_id)

            # Get names for message
            weapon_name = await self.get_item_name(selected_weapon_id)
            bar_name = await self.get_item_name(bar_id)

            await ctx.send(
                f"Successfully crafted {weapon_name}! (Used: {required_qty}x {bar_name})",
                ephemeral=True
            )

            # Clean up inventory (remove items with quantity 0)
            await self.db.execute("""
                DELETE FROM inventory
                WHERE quantity <= 0
            """)

        except Exception as e:
            logging.error(f"Error in select_weapon_handler: {e}")
            await ctx.send("An error occurred while crafting the weapon. Please try again.", ephemeral=True)

# Setup function to load this as an extension
def setup(bot):
    """Setup function to add the extension to the bot."""
    SmithModule(bot) 