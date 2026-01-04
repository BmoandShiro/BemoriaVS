from Inventory import Inventory
from interactions import Extension, component_callback, Button, ButtonStyle, ComponentContext, StringSelectMenu, StringSelectOption
import re

class InventorySystem(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    def get_inventory_for_player(self, player_id):
        return Inventory(self.db, player_id)

    async def display_inventory(self, ctx, player_id):
        # Get the player's current location and check if it's a bank
        player_data = await self.db.fetchrow("""
            SELECT l.type AS location_type, pd.current_location
            FROM player_data pd
            JOIN locations l ON l.locationid = pd.current_location
            WHERE pd.playerid = $1
        """, player_id)

        is_at_bank = player_data and player_data['location_type'].lower() == "bank"

        # Only show unequipped items in main inventory
        inventory_items = await self.db.fetch("""
            SELECT inv.inventoryid, inv.quantity, inv.isequipped, 
                   COALESCE(i.name, cf.fish_name) AS item_name, cf.length, cf.weight, cf.rarity
            FROM inventory inv
            LEFT JOIN items i ON inv.itemid = i.itemid
            LEFT JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1 AND inv.in_bank = FALSE AND inv.isequipped = FALSE
        """, player_id)

        if not inventory_items:
            inventory_view = "Inventory is empty (no unequipped items)."
        else:
            # Build detailed inventory display (only unequipped items)
            inventory_view = ""
            for item in inventory_items:
                if item['item_name']:
                    if item['length'] and item['weight']:
                        inventory_view += f"{item['item_name']} (Rarity: {item['rarity']}, Length: {item['length']} cm, Weight: {item['weight']} kg)\n"
                    else:
                        inventory_view += f"{item['item_name']} (x{item['quantity']})\n"

        # Adding equip, use, drop, and view equipped buttons
        equip_button = Button(style=ButtonStyle.SUCCESS, label="Equip Item", custom_id="equip_item")
        use_button = Button(style=ButtonStyle.SUCCESS, label="Use Item", custom_id="use_item")
        view_equipped_button = Button(style=ButtonStyle.PRIMARY, label="View Equipped", custom_id="view_equipped")
        drop_button = Button(style=ButtonStyle.DANGER, label="Drop Item", custom_id="drop_item")

        components = [[equip_button, use_button, view_equipped_button, drop_button]]

        # Add transfer buttons if the player is at a bank
        if is_at_bank:
            transfer_to_bank_button = Button(style=ButtonStyle.SECONDARY, label="Transfer to Bank", custom_id="transfer_to_bank")
            transfer_to_inventory_button = Button(style=ButtonStyle.SECONDARY, label="Transfer to Inventory", custom_id="transfer_to_inventory")
            components.append([transfer_to_bank_button, transfer_to_inventory_button])

        # Send the inventory content and appropriate buttons
        await ctx.send(content=inventory_view, components=components, ephemeral=True)
    

    async def display_bank(self, ctx, player_id, message=None):
        bank_items = await self.db.fetch("""
            SELECT inv.inventoryid, inv.quantity, COALESCE(i.name, cf.fish_name) AS item_name, cf.length, cf.weight, cf.rarity
            FROM inventory inv
            LEFT JOIN items i ON inv.itemid = i.itemid
            LEFT JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1 AND inv.in_bank = TRUE
        """, player_id)

        if not bank_items:
            return await ctx.send("Bank is empty.", ephemeral=True)

        # Build detailed bank inventory display
        bank_view = ""
        for item in bank_items:
            if item['item_name']:
                if item['length'] and item['weight']:
                    bank_view += f"{item['item_name']} (Rarity: {item['rarity']}, Length: {item['length']} cm, Weight: {item['weight']} kg)\n"
                else:
                    bank_view += f"{item['item_name']} (x{item['quantity']})"
                bank_view += "\n"

        # Adding transfer buttons
        transfer_to_inventory_button = Button(style=ButtonStyle.SECONDARY, label="Transfer to Inventory", custom_id=f"transfer_to_inventory_{player_id}")
        transfer_to_bank_button = Button(style=ButtonStyle.SECONDARY, label="Transfer to Bank", custom_id=f"transfer_to_bank_{player_id}")

        components = [[transfer_to_inventory_button, transfer_to_bank_button]]

        if message:
            await message.edit(content=bank_view, components=components)
        else:
            await ctx.send(content=bank_view, components=components, ephemeral=True)
        

        

    @component_callback("transfer_to_bank")
    async def transfer_to_bank_handler(self, ctx: ComponentContext):
        player_id = await self.db.get_or_create_player(ctx.author.id)
        # Fetch items that can be transferred to the bank
        items = await self.db.fetch("""
            SELECT inv.inventoryid, inv.quantity, COALESCE(i.name, cf.fish_name) AS item_name
            FROM inventory inv
            LEFT JOIN items i ON inv.itemid = i.itemid
            LEFT JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1 AND inv.in_bank = FALSE
        """, player_id)

        if not items:
            return await ctx.send("No items available to transfer to the bank.", ephemeral=True)

        options = [StringSelectOption(label=item['item_name'], value=str(item['inventoryid'])) for item in items]
        transfer_select = StringSelectMenu(custom_id="select_transfer_to_bank", placeholder="Select an item to transfer to bank")
        transfer_select.options = options

        # Show the dropdown after clicking the transfer button
        await ctx.send("Choose an item to transfer to bank:", components=[[transfer_select]], ephemeral=True)
        
    

    @component_callback("select_transfer_to_bank")
    async def select_transfer_to_bank_handler(self, ctx: ComponentContext):
        inventory_id = int(ctx.values[0])
        player_id = await self.db.get_or_create_player(ctx.author.id)

        # Move item from inventory to bank
        await self.db.execute("""
            UPDATE inventory SET in_bank = TRUE WHERE inventoryid = $1 AND playerid = $2
        """, inventory_id, player_id)

        await ctx.send("Item transferred to bank.", ephemeral=True)

    @component_callback("transfer_to_inventory")
    async def transfer_to_inventory_handler(self, ctx: ComponentContext):
        player_id = await self.db.get_or_create_player(ctx.author.id)

        # Fetch items currently in the bank
        bank_items = await self.db.fetch("""
            SELECT inv.inventoryid, inv.quantity, COALESCE(i.name, cf.fish_name) AS item_name
            FROM inventory inv
            LEFT JOIN items i ON inv.itemid = i.itemid
            LEFT JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1 AND inv.in_bank = TRUE
        """, player_id)

        if not bank_items:
            return await ctx.send("No items available to transfer from the bank.", ephemeral=True)

        # Create options for dropdown selection
        options = [StringSelectOption(label=f"{item['item_name']} (x{item['quantity']})", value=str(item['inventoryid'])) for item in bank_items]
        transfer_select = StringSelectMenu(custom_id="select_transfer_to_inventory", placeholder="Select an item to transfer to inventory")
        transfer_select.options = options

        # Display the dropdown to select an item to transfer
        await ctx.send("Choose an item to transfer to inventory:", components=[[transfer_select]], ephemeral=True)

    @component_callback("select_transfer_to_inventory")
    async def select_transfer_to_inventory_handler(self, ctx: ComponentContext):
        inventory_id = int(ctx.values[0])
        player_id = await self.db.get_or_create_player(ctx.author.id)

        # Move item from bank to inventory
        await self.db.execute("""
            UPDATE inventory SET in_bank = FALSE WHERE inventoryid = $1 AND playerid = $2
        """, inventory_id, player_id)

        await ctx.send("Item transferred to inventory.", ephemeral=True)
        
    

    @component_callback("equip_item")
    async def equip_item_handler(self, ctx: ComponentContext):
        player_id = await self.db.get_or_create_player(ctx.author.id)
        items = await self.db.fetch("""
            SELECT i.itemid, i.name FROM inventory inv
            JOIN items i ON inv.itemid = i.itemid
            WHERE inv.playerid = $1 AND inv.isequipped = false
        """, player_id)

        if not items:
            return await ctx.send("No items available to equip.", ephemeral=True)

        options = [StringSelectOption(label=item['name'], value=str(item['itemid'])) for item in items]
        equip_select = StringSelectMenu(custom_id="select_equip_item", placeholder="Select an item to equip")
        equip_select.options = options

        await ctx.send("Choose an item to equip:", components=[equip_select], ephemeral=True)

    @component_callback("use_item")
    async def use_item_handler(self, ctx: ComponentContext):
        player_id = await self.db.get_or_create_player(ctx.author.id)
        items = await self.db.fetch("""
            SELECT i.itemid, i.name, i.type FROM inventory inv
            JOIN items i ON inv.itemid = i.itemid
            WHERE inv.playerid = $1 AND inv.isequipped = false
        """, player_id)

        if not items:
            return await ctx.send("No items available to use.", ephemeral=True)

        # List of known food items (by name, as fallback if type isn't set correctly)
        known_food_items = [
            'Chips', 'Smoked Fish Fillet', 'Fish and Chips', 'Fishball Stew'
        ]
        
        # Filter to only show usable items
        # Primary: Check by type (Consumable, Food, Grimoire)
        # Fallback: Check by name for specific items
        usable_items = [
            item for item in items 
            if item['type'] == 'Grimoire' 
            or item['type'] == 'Food' 
            or item['type'] == 'Consumable'
            or item['name'] == 'Player Locatinator'
            or item['name'] in known_food_items  # Fallback for items not yet updated
        ]
        
        if not usable_items:
            return await ctx.send("You don't have any usable items in your inventory.", ephemeral=True)

        options = [StringSelectOption(label=item['name'], value=str(item['itemid'])) for item in usable_items]
        use_select = StringSelectMenu(custom_id="select_use_item", placeholder="Select an item to use")
        use_select.options = options

        await ctx.send("Choose an item to use:", components=[use_select], ephemeral=True)

    @component_callback("select_use_item")
    async def select_use_item_handler(self, ctx: ComponentContext):
        item_id = int(ctx.values[0])
        player_id = await self.db.get_or_create_player(ctx.author.id)
        
        # Get item details
        item_info = await self.db.fetchrow("""
            SELECT itemid, name, type FROM items WHERE itemid = $1
        """, item_id)
        
        if not item_info:
            await ctx.send("Item not found.", ephemeral=True)
            return
        
        # Check if player has the item
        has_item = await self.db.fetchval("""
            SELECT COUNT(*) > 0
            FROM inventory
            WHERE playerid = $1 AND itemid = $2 AND isequipped = FALSE
        """, player_id, item_id)
        
        if not has_item:
            await ctx.send("You don't have this item in your inventory.", ephemeral=True)
            return
        
        # Handle specific items
        if item_info['name'] == 'Player Locatinator':
            # Show player locator
            await self.show_player_locator(ctx, player_id)
        elif item_info['type'] == 'Food' or item_info['type'] == 'Consumable':
            # Handle food consumption
            await self.consume_food(ctx, player_id, item_id, item_info['name'])
        else:
            await ctx.send(f"{item_info['name']} cannot be used yet.", ephemeral=True)
    
    async def consume_food(self, ctx, player_id, item_id, item_name):
        """Handle food consumption with healing and other effects."""
        # Get food effects based on item name
        food_effects = self.get_food_effects(item_name)
        
        if not food_effects:
            await ctx.send(f"{item_name} cannot be consumed.", ephemeral=True)
            return
        
        # Get current player stats
        player_stats = await self.db.fetchrow("""
            SELECT health, mana, stamina, max_health, max_mana, max_stamina
            FROM player_data
            WHERE playerid = $1
        """, player_id)
        
        if not player_stats:
            await ctx.send("Error: Could not retrieve player stats.", ephemeral=True)
            return
        
        # Calculate new stats with effects
        new_health = min(player_stats['health'] + food_effects.get('health', 0), player_stats['max_health'])
        new_mana = min(player_stats['mana'] + food_effects.get('mana', 0), player_stats['max_mana'])
        new_stamina = min(player_stats['stamina'] + food_effects.get('stamina', 0), player_stats['max_stamina'])
        
        # Calculate actual healing/restoration (capped at max)
        health_healed = new_health - player_stats['health']
        mana_restored = new_mana - player_stats['mana']
        stamina_restored = new_stamina - player_stats['stamina']
        
        # Update player stats
        await self.db.execute("""
            UPDATE player_data
            SET health = $1, mana = $2, stamina = $3
            WHERE playerid = $4
        """, new_health, new_mana, new_stamina, player_id)
        
        # Remove one quantity of the food item
        inventory_entry = await self.db.fetchrow("""
            SELECT inventoryid, quantity
            FROM inventory
            WHERE playerid = $1 AND itemid = $2 AND isequipped = FALSE
            LIMIT 1
        """, player_id, item_id)
        
        if inventory_entry:
            if inventory_entry['quantity'] > 1:
                # Decrease quantity
                await self.db.execute("""
                    UPDATE inventory
                    SET quantity = quantity - 1
                    WHERE inventoryid = $1
                """, inventory_entry['inventoryid'])
            else:
                # Remove item if quantity is 1
                await self.db.execute("""
                    DELETE FROM inventory
                    WHERE inventoryid = $1
                """, inventory_entry['inventoryid'])
        
        # Build consumption message
        effects = []
        if health_healed > 0:
            effects.append(f"**+{health_healed} HP**")
        if mana_restored > 0:
            effects.append(f"**+{mana_restored} Mana**")
        if stamina_restored > 0:
            effects.append(f"**+{stamina_restored} Stamina**")
        
        if effects:
            message = f"🍽️ You consumed **{item_name}**! {' '.join(effects)}"
            if new_health >= player_stats['max_health'] and health_healed > 0:
                message += " (Health at maximum)"
            if new_mana >= player_stats['max_mana'] and mana_restored > 0:
                message += " (Mana at maximum)"
            if new_stamina >= player_stats['max_stamina'] and stamina_restored > 0:
                message += " (Stamina at maximum)"
        else:
            message = f"🍽️ You consumed **{item_name}**, but you're already at maximum stats!"
        
        await ctx.send(message, ephemeral=True)
    
    def get_food_effects(self, item_name):
        """Get the effects of a food item. Returns dict with health, mana, stamina, and future modifiers."""
        # Food healing values
        food_effects_map = {
            'Chips': {'health': 10},
            'Smoked Fish Fillet': {'health': 12},
            'Fish and Chips': {'health': 20},
            'Fishball Stew': {'health': 25}
        }
        
        # Return effects for this food item, or None if not found
        return food_effects_map.get(item_name)
    
    async def show_player_locator(self, ctx, player_id):
        """Display all players with their location, HP, mana, and stamina."""
        from interactions import Embed
        
        # Get all players with their current stats
        all_players = await self.db.fetch("""
            SELECT 
                pd.playerid,
                pd.health,
                pd.mana,
                pd.stamina,
                l.name AS location_name,
                players.discord_id
            FROM player_data pd
            JOIN locations l ON l.locationid = pd.current_location
            JOIN players ON players.playerid = pd.playerid
            ORDER BY l.name, pd.playerid
        """)
        
        if not all_players:
            await ctx.send("No players found in the server.", ephemeral=True)
            return
        
        # Create embed with player information
        embed = Embed(
            title="Player Locatinator",
            description="Viewing all players in the server:",
            color=0x00FF00
        )
        
        # Group by location for better organization
        players_by_location = {}
        for player in all_players:
            location = player['location_name']
            if location not in players_by_location:
                players_by_location[location] = []
            players_by_location[location].append(player)
        
        # Add fields for each location
        for location, players in sorted(players_by_location.items()):
            player_list = []
            for p in players:
                try:
                    user = await self.bot.fetch_user(p['discord_id'])
                    player_name = user.display_name if user else f"Player {p['playerid']}"
                except:
                    player_name = f"Player {p['playerid']}"
                
                player_list.append(
                    f"**{player_name}** - HP: {p['health']}, Mana: {p['mana']}, Stamina: {p['stamina']}"
                )
            
            # Discord embed fields have a 1024 character limit, so split if needed
            field_value = "\n".join(player_list)
            if len(field_value) > 1024:
                # Split into multiple fields if too long
                chunks = [player_list[i:i+10] for i in range(0, len(player_list), 10)]
                for i, chunk in enumerate(chunks):
                    embed.add_field(
                        name=f"{location} (Part {i+1})" if i > 0 else location,
                        value="\n".join(chunk),
                        inline=False
                    )
            else:
                embed.add_field(
                    name=location,
                    value=field_value,
                    inline=False
                )
        
        await ctx.send(embeds=[embed], ephemeral=True)

    @component_callback("unequip_item")
    async def unequip_item_handler(self, ctx: ComponentContext):
        player_id = await self.db.get_or_create_player(ctx.author.id)
        items = await self.db.fetch("""
            SELECT inv.inventoryid, i.itemid, i.name, inv.slot, inv.quantity
            FROM inventory inv
            JOIN items i ON inv.itemid = i.itemid
            WHERE inv.playerid = $1 AND inv.isequipped = true
            ORDER BY inv.slot, i.name
        """, player_id)

        if not items:
            return await ctx.send("No items currently equipped.", ephemeral=True)

        # Use inventoryid as value to handle duplicate items in different slots
        options = []
        for item in items:
            # Map slot names to user-friendly names
            slot_display_map = {
                'left_hand': 'Off Hand',
                '1H_weapon': 'Primary Hand',
                '2H_weapon': 'Two-Handed Weapon'
            }
            slot_name = slot_display_map.get(item['slot'], item['slot'].replace('_', ' ').title() if item['slot'] else 'Unknown Slot')
            label = f"{item['name']} ({slot_name})"
            if item['quantity'] > 1:
                label += f" x{item['quantity']}"
            options.append(StringSelectOption(
                label=label,
                value=str(item['inventoryid'])  # Use inventoryid instead of itemid
            ))
        
        unequip_select = StringSelectMenu(custom_id="select_unequip_item", placeholder="Select an item to unequip")
        unequip_select.options = options

        await ctx.send("Choose an item to unequip:", components=[unequip_select], ephemeral=True)
        

    @component_callback("drop_item")
    async def drop_item_handler(self, ctx: ComponentContext):
        player_id = await self.db.get_or_create_player(ctx.author.id)
        # Fetch both items and fish from inventory
        items = await self.db.fetch("""
            SELECT inv.inventoryid, COALESCE(i.name, cf.fish_name) AS name 
            FROM inventory inv
            LEFT JOIN items i ON inv.itemid = i.itemid
            LEFT JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1
        """, player_id)

        if not items:
            return await ctx.send("No items available to drop.", ephemeral=True)

        options = [StringSelectOption(label=item['name'], value=str(item['inventoryid'])) for item in items]
        drop_select = StringSelectMenu(custom_id="select_drop_item", placeholder="Select an item to drop")
        drop_select.options = options

        await ctx.send("Choose an item to drop:", components=[drop_select], ephemeral=True)


    @component_callback("select_drop_item")
    async def select_drop_item_handler(self, ctx: ComponentContext):
        inventory_id = int(ctx.values[0])
        player_id = await self.db.get_or_create_player(ctx.author.id)

        # Find out if the item is a fish or a regular item
        item = await self.db.fetchrow("""
            SELECT caught_fish_id FROM inventory WHERE inventoryid = $1 AND playerid = $2
        """, inventory_id, player_id)

        if item and item["caught_fish_id"]:
            # If it's a fish, remove it from the inventory first
            await self.db.execute("DELETE FROM inventory WHERE inventoryid = $1 AND playerid = $2", inventory_id, player_id)
            # Then remove it from the caught_fish table
            await self.db.execute("DELETE FROM caught_fish WHERE id = $1", item["caught_fish_id"])
        else:
            # If it's not a fish, simply remove it from the inventory table
            await self.db.execute("DELETE FROM inventory WHERE inventoryid = $1 AND playerid = $2", inventory_id, player_id)

        await ctx.send("Item dropped successfully.", ephemeral=True)


    @component_callback("select_equip_item")
    async def select_equip_item_handler(self, ctx: ComponentContext):
        item_id = int(ctx.values[0])
        player_id = await self.db.get_or_create_player(ctx.author.id)
        inventory = self.get_inventory_for_player(player_id)
        
        # Check if this is a hatchet/axe that needs slot selection
        item_info = await self.db.fetchrow("SELECT name, type FROM items WHERE itemid = $1", item_id)
        if item_info:
            item_name_lower = item_info.get('name', '').lower()
            is_hatchet_or_axe = ('hatchet' in item_name_lower or 'axe' in item_name_lower) and item_info['type'] == "Weapon"
            
            if is_hatchet_or_axe:
                # Show slot selection menu for hatchets/axes
                options = [
                    StringSelectOption(
                        label="Tool Belt Slot (for Woodcutting)",
                        value=f"tool_{item_id}",
                        description="Use as a tool for woodcutting"
                    ),
                    StringSelectOption(
                        label="Primary Hand (for Combat)",
                        value=f"right_{item_id}",
                        description="Equip in primary hand for combat"
                    ),
                    StringSelectOption(
                        label="Off Hand (for Combat)",
                        value=f"left_{item_id}",
                        description="Equip in off hand for combat"
                    )
                ]
                
                slot_select = StringSelectMenu(
                    custom_id=f"select_hatchet_slot_{player_id}",
                    placeholder="Choose where to equip this hatchet/axe"
                )
                slot_select.options = options
                
                await ctx.send(
                    content=f"**{item_info['name']}** can be equipped in multiple ways. Choose where to equip it:",
                    components=[[slot_select]],
                    ephemeral=True
                )
                return
        
        # For other items, equip normally
        result = await inventory.equip_item(item_id)
        await ctx.send(result, ephemeral=True)
    
    @component_callback(re.compile(r"^select_hatchet_slot_\d+$"))
    async def select_hatchet_slot_handler(self, ctx: ComponentContext):
        """Handle hatchet/axe slot selection."""
        try:
            player_id = int(ctx.custom_id.split("_")[3])
            
            # Verify authorization
            authorized_discord_id = await self.db.fetchval("""
                SELECT discord_id::text FROM players WHERE playerid = $1
            """, player_id)
            
            if str(ctx.author.id) != authorized_discord_id:
                await ctx.send("You are not authorized to use this.", ephemeral=True)
                return
            
            selected_value = ctx.values[0]
            slot_type, item_id = selected_value.split("_", 1)
            item_id = int(item_id)
            
            # Get inventory instance
            inventory = self.get_inventory_for_player(player_id)
            
            # Determine the actual slot name
            if slot_type == "tool":
                # Find available tool belt slot
                slot = await inventory.find_available_tool_belt_slot()
                if not slot:
                    await ctx.send("No available tool belt slots. Please unequip a tool first.", ephemeral=True)
                    return
            elif slot_type == "right":
                # Check if primary hand (1H_weapon) is available
                # Also check if 2H weapon is blocking
                if await inventory.is_slot_filled("2H_weapon"):
                    await ctx.send("Cannot equip in primary hand while a 2-handed weapon is equipped.", ephemeral=True)
                    return
                if await inventory.is_slot_filled("1H_weapon"):
                    await ctx.send("Primary hand is already occupied. Please unequip the item first.", ephemeral=True)
                    return
                slot = "1H_weapon"  # Using 1H_weapon as primary hand
            elif slot_type == "left":
                # For off hand, check if 2H weapon is blocking
                if await inventory.is_slot_filled("2H_weapon"):
                    await ctx.send("Cannot equip in off hand while a 2-handed weapon is equipped.", ephemeral=True)
                    return
                # Check if left_hand slot exists and is available
                if await inventory.is_slot_filled("left_hand"):
                    await ctx.send("Off hand is already occupied. Please unequip the item first.", ephemeral=True)
                    return
                slot = "left_hand"
            else:
                await ctx.send("Invalid slot selection.", ephemeral=True)
                return
            
            # Equip the item to the selected slot
            result = await inventory.equip_item(item_id, slot)
            await ctx.send(result, ephemeral=True)
            
        except Exception as e:
            import logging
            logging.error(f"Error in select_hatchet_slot_handler: {e}")
            await ctx.send("An error occurred while equipping the item. Please try again.", ephemeral=True)

    @component_callback("select_unequip_item")
    async def select_unequip_item_handler(self, ctx: ComponentContext):
        inventory_id = int(ctx.values[0])  # Now using inventoryid instead of itemid
        player_id = await self.db.get_or_create_player(ctx.author.id)
        
        # Get item details for the message
        item_data = await self.db.fetchrow("""
            SELECT i.name, inv.slot, inv.quantity, inv.itemid
            FROM inventory inv
            JOIN items i ON inv.itemid = i.itemid
            WHERE inv.inventoryid = $1 AND inv.playerid = $2
        """, inventory_id, player_id)
        
        if not item_data:
            await ctx.send("Item not found.", ephemeral=True)
            return
        
        # Handle unequipping: merge with existing stack or unequip entry
        # Due to unique constraint on unequipped items, we must merge if one exists
        # Check for existing entry WITHIN the transaction to avoid race conditions
        async with self.db.pool.acquire() as connection:
            async with connection.transaction():
                # Check if there's already an unequipped entry for this item (within transaction)
                existing_unequipped = await connection.fetchrow("""
                    SELECT inventoryid, quantity FROM inventory 
                    WHERE playerid = $1 AND itemid = $2 AND isequipped = false 
                    AND (in_bank = FALSE OR in_bank IS NULL)
                    AND inventoryid != $3
                """, player_id, item_data['itemid'], inventory_id)
                
                if existing_unequipped:
                    # Merge with existing unequipped stack
                    await connection.execute("""
                        UPDATE inventory SET quantity = quantity + $1
                        WHERE inventoryid = $2
                    """, item_data['quantity'], existing_unequipped['inventoryid'])
                    
                    # Delete the equipped entry (to avoid constraint violation)
                    await connection.execute("""
                        DELETE FROM inventory WHERE inventoryid = $1
                    """, inventory_id)
                else:
                    # No existing unequipped entry, just unequip this one
                    # This is safe because there's no unequipped entry to conflict with
                    await connection.execute("""
                        UPDATE inventory SET isequipped = false, slot = NULL 
                        WHERE inventoryid = $1 AND playerid = $2
                    """, inventory_id, player_id)
        
        # Map slot names to user-friendly names
        slot_display_map = {
            'left_hand': 'Off Hand',
            '1H_weapon': 'Primary Hand',
            '2H_weapon': 'Two-Handed Weapon'
        }
        slot_name = slot_display_map.get(item_data['slot'], item_data['slot'].replace('_', ' ').title() if item_data['slot'] else 'Unknown Slot')
        await ctx.send(f"{item_data['name']} unequipped from {slot_name}.", ephemeral=True)

    @component_callback("view_equipped")
    async def view_equipped_handler(self, ctx: ComponentContext):
        """Display all equipped items in a separate menu."""
        player_id = await self.db.get_or_create_player(ctx.author.id)
        
        # Fetch all equipped items
        equipped_items = await self.db.fetch("""
            SELECT inv.inventoryid, inv.quantity, inv.slot,
                   COALESCE(i.name, cf.fish_name) AS item_name, 
                   i.type AS item_type,
                   cf.length, cf.weight, cf.rarity
            FROM inventory inv
            LEFT JOIN items i ON inv.itemid = i.itemid
            LEFT JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1 AND inv.isequipped = TRUE
            ORDER BY inv.slot
        """, player_id)

        if not equipped_items:
            return await ctx.send("No items are currently equipped.", ephemeral=True)

        # Build equipped items display organized by slot
        equipped_view = "**Equipped Items:**\n\n"
        
        # Organize by slot type
        slot_groups = {}
        for item in equipped_items:
            slot = item['slot'] or 'unknown'
            
            if slot not in slot_groups:
                slot_groups[slot] = []
            slot_groups[slot].append(item)
        
        # Display items grouped by slot
        slot_display_map = {
            'left_hand': 'Off Hand',
            '1H_weapon': 'Primary Hand',
            '2H_weapon': 'Two-Handed Weapon'
        }
        for slot, items in slot_groups.items():
            slot_name = slot_display_map.get(slot, slot.replace('_', ' ').title() if slot != 'unknown' else 'Unknown Slot')
            equipped_view += f"**{slot_name}:**\n"
            for item in items:
                if item['item_name']:
                    if item['length'] and item['weight']:
                        equipped_view += f"  • {item['item_name']} (Rarity: {item['rarity']}, Length: {item['length']} cm, Weight: {item['weight']} kg)\n"
                    else:
                        equipped_view += f"  • {item['item_name']}"
                        if item['quantity'] > 1:
                            equipped_view += f" (x{item['quantity']})"
                        equipped_view += "\n"
            equipped_view += "\n"

        # Add unequip button
        unequip_button = Button(style=ButtonStyle.DANGER, label="Unequip Item", custom_id="unequip_item")

        await ctx.send(content=equipped_view, components=[[unequip_button]], ephemeral=True)

# Setup function to load this as an extension
def setup(bot):
    InventorySystem(bot)
    
