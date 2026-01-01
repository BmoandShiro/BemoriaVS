from interactions import Button, ButtonStyle, ComponentContext

class Inventory:
    def __init__(self, db, player_id):
        self.db = db
        self.player_id = player_id

    async def add_item(self, item_id, quantity=1):
        max_slots = await self.db.get_inventory_capacity(self.player_id)
        # Only count items in main inventory (not in bank, not equipped) - same logic as UI
        current_item_count = await self.db.fetchval(
            "SELECT COUNT(*) FROM inventory WHERE playerid = $1 AND isequipped = FALSE AND (in_bank = FALSE OR in_bank IS NULL)",
            self.player_id
        )

        if current_item_count >= max_slots:
            return "Your inventory is full. You cannot add more items."

        item_info = await self.db.fetchrow("SELECT * FROM items WHERE itemid = $1", item_id)
        if not item_info:
            return "Invalid item."

        is_stackable = item_info["max_stack"] > 1

        # Check for existing item in main inventory (not bank)
        existing_item = await self.db.fetchrow(
            "SELECT * FROM inventory WHERE playerid = $1 AND itemid = $2 AND (in_bank = FALSE OR in_bank IS NULL)",
            self.player_id, item_id
        )

        if existing_item:
            if is_stackable:
                # Update existing stackable item in inventory
                new_quantity = existing_item["quantity"] + quantity
                import logging
                logging.info(f"Found existing item in inventory. Updating: inventoryid={existing_item['inventoryid']}, current_qty={existing_item['quantity']}, adding={quantity}, new_qty={new_quantity}")
                
                result = await self.db.execute(
                    "UPDATE inventory SET quantity = $1 WHERE inventoryid = $2",
                    new_quantity, existing_item["inventoryid"]
                )
                logging.info(f"UPDATE result: {result}")
                
                # Verify the update worked
                verify = await self.db.fetchrow(
                    "SELECT quantity FROM inventory WHERE inventoryid = $1",
                    existing_item["inventoryid"]
                )
                logging.info(f"Verified quantity after update: {verify['quantity'] if verify else 'NOT FOUND'}")
            else:
                # Item exists but is not stackable
                return "You already have this non-stackable item in your inventory."
        else:
            # Item doesn't exist in main inventory, check if it exists in bank
            existing_in_bank = await self.db.fetchrow(
                "SELECT * FROM inventory WHERE playerid = $1 AND itemid = $2 AND in_bank = TRUE",
                self.player_id, item_id
            )
            
            if existing_in_bank:
                if is_stackable:
                    # Move from bank to inventory and update quantity
                    new_quantity = existing_in_bank["quantity"] + quantity
                    import logging
                    logging.info(f"Found item in bank. Moving to inventory and updating: {existing_in_bank['quantity']} + {quantity} = {new_quantity}")
                    await self.db.execute(
                        "UPDATE inventory SET quantity = $1, in_bank = FALSE WHERE inventoryid = $2",
                        new_quantity, existing_in_bank["inventoryid"]
                    )
                else:
                    return "This item is in your bank. Please transfer it to inventory first."
            else:
                # Item doesn't exist anywhere, insert new entry
                if current_item_count >= max_slots:
                    return "Your inventory is full. You cannot add more items."
                
                import logging
                logging.info(f"Inserting new item: item_id={item_id}, quantity={quantity}")
                await self.db.execute(
                    "INSERT INTO inventory (playerid, itemid, quantity, isequipped, slot, in_bank) VALUES ($1, $2, $3, false, NULL, false)",
                    self.player_id, item_id, quantity
                )

        # Recalculate remaining slots after addition (only count main inventory, not bank, not equipped)
        new_item_count = await self.db.fetchval(
            "SELECT COUNT(*) FROM inventory WHERE playerid = $1 AND isequipped = FALSE AND (in_bank = FALSE OR in_bank IS NULL)",
            self.player_id
        )
        remaining_slots = max_slots - new_item_count
        return f"Item added to inventory. Remaining slots: {remaining_slots}."

    async def remove_item(self, item_id, quantity=1):
        existing_item = await self.db.fetchrow(
            "SELECT * FROM inventory WHERE playerid = $1 AND itemid = $2",
            self.player_id, item_id
        )

        if not existing_item:
            return "Item not found in inventory."

        if existing_item["quantity"] > quantity:
            # Reduce quantity and let the trigger handle further deletions if needed
            new_quantity = existing_item["quantity"] - quantity
            await self.db.execute(
                "UPDATE inventory SET quantity = $1 WHERE inventoryid = $2",
                new_quantity, existing_item["inventoryid"]
            )
        else:
            # Set quantity to 0, triggering automatic deletion
            await self.db.execute(
                "UPDATE inventory SET quantity = 0 WHERE inventoryid = $1",
                existing_item["inventoryid"]
            )

        max_slots = await self.db.get_inventory_capacity(self.player_id)
        current_item_count = await self.db.fetchval(
            "SELECT COUNT(*) FROM inventory WHERE playerid = $1",
            self.player_id
        )
        remaining_slots = max_slots - current_item_count

        return f"Item removed from inventory. Remaining slots: {remaining_slots}."

    
    async def remove_item_by_inventory_id(self, inventory_id):
        # Fetch item details from inventory to determine if it's a caught fish
        existing_item = await self.db.fetchrow("""
            SELECT * FROM inventory WHERE inventoryid = $1 AND playerid = $2
        """, inventory_id, self.player_id)

        if not existing_item:
            return "Item not found in inventory."

        # If the item is a caught fish, delete it from both inventory and caught_fish table
        if existing_item["caught_fish_id"]:
            await self.db.execute("""
                DELETE FROM caught_fish WHERE id = $1
            """, existing_item["caught_fish_id"])

        # Delete the item from the inventory table
        await self.db.execute("""
            DELETE FROM inventory WHERE inventoryid = $1
        """, inventory_id)

        return "Item dropped from inventory."

    async def get_tool_belt_capacity(self):
        tool_belt_slots = await self.db.fetchval("""
            SELECT tool_belt_slots FROM player_data WHERE playerid = $1
        """, self.player_id)
        return tool_belt_slots or 12  # Default to 12 if not set

    async def equip_item(self, item_id, slot=None):
        """
        Equip an item to a specific slot.
        If slot is None, automatically determines the slot based on item type.
        Returns a special string "SELECT_SLOT" if the item needs slot selection (hatchets/axes).
        Only equips ONE item from a stack, splitting the stack if necessary.
        """
        item_info = await self.db.fetchrow("SELECT * FROM items WHERE itemid = $1", item_id)
        if not item_info:
            return "Item not found."
        
        # Check if item is already equipped in the target slot (if slot is specified)
        # For weapons, we allow equipping the same item in different slots (dual-wielding)
        if slot:
            slot_already_filled = await self.db.fetchval("""
                SELECT COUNT(*) > 0 FROM inventory 
                WHERE playerid = $1 AND itemid = $2 AND isequipped = true AND slot = $3
            """, self.player_id, item_id, slot)
            
            if slot_already_filled:
                return f"This item is already equipped in {slot.replace('_', ' ').title()}."
        
        # Find an unequipped inventory entry for this item
        inventory_entry = await self.db.fetchrow("""
            SELECT inventoryid, quantity FROM inventory 
            WHERE playerid = $1 AND itemid = $2 AND isequipped = false 
            AND (in_bank = FALSE OR in_bank IS NULL)
            ORDER BY inventoryid
            LIMIT 1
        """, self.player_id, item_id)
        
        if not inventory_entry:
            return "Item not found in inventory."
        
        inventory_id = inventory_entry['inventoryid']
        quantity = inventory_entry['quantity']
        
         # If the item is a fishing rod, make sure no other rod is equipped
        if item_info['type'] == "Tool" and item_info['rodtype']:
            # Check if the player already has a rod equipped
            equipped_rod = await self.db.fetchrow("""
                SELECT inventoryid FROM inventory
                WHERE playerid = $1 AND isequipped = true AND itemid IN (
                    SELECT itemid FROM items WHERE type = 'Tool' AND rodtype IS NOT NULL
                )
            """, self.player_id)

            # If a rod is equipped, unequip it first
            if equipped_rod:
                await self.db.execute("""
                    UPDATE inventory SET isequipped = false, slot = NULL
                    WHERE inventoryid = $1
                """, equipped_rod["inventoryid"])

        # If slot is provided, use it directly (for hatchets/axes with user selection)
        if slot:
            # Special validation for weapon slots
            if slot in ["1H_weapon", "left_hand"]:
                # Can't equip 1H weapons if 2H weapon is equipped
                if await self.is_slot_filled("2H_weapon"):
                    return "Cannot equip a 1-handed weapon while a 2-handed weapon is equipped."
            elif slot == "2H_weapon":
                # Can't equip 2H weapon if either hand is occupied
                if await self.is_slot_filled("1H_weapon") or await self.is_slot_filled("left_hand"):
                    return "Cannot equip a 2-handed weapon while 1-handed weapons are equipped in either hand."
                # Can't equip 2H weapon if another 2H weapon is already equipped
                if await self.is_slot_filled("2H_weapon"):
                    return "You can only equip one 2-handed weapon at a time."
            
            # Validate the slot is available
            if await self.is_slot_filled(slot):
                return f"Slot {slot} is already occupied."
            
            # Handle stack splitting: if quantity > 1, split the stack
            # Now that we allow multiple equipped entries, we can create a new equipped entry
            if quantity > 1:
                # Reduce the original stack by 1
                await self.db.execute("""
                    UPDATE inventory SET quantity = quantity - 1 
                    WHERE inventoryid = $1
                """, inventory_id)
                
                # Create a new equipped entry with quantity 1
                await self.db.execute("""
                    INSERT INTO inventory (playerid, itemid, quantity, isequipped, slot, in_bank)
                    VALUES ($1, $2, 1, true, $3, false)
                """, self.player_id, item_id, slot)
            else:
                # Quantity is 1, just equip this entry
                await self.db.execute("""
                    UPDATE inventory SET isequipped = true, slot = $1 
                    WHERE inventoryid = $2
                """, slot, inventory_id)
            
            slot_display = slot.replace('_', ' ').title()
            return f"{item_info['name']} equipped in {slot_display}."

        # Auto-determine slot if not provided
        determined_slot = None
        if item_info['type'] == "Helmet":
            determined_slot = "helmet"
        elif item_info['type'] == "Chest":
            determined_slot = "chest"
        elif item_info['type'] == "Back":
            determined_slot = "back"
        elif item_info['type'] == "Legs":
            determined_slot = "legs"
        elif item_info['type'] == "Feet":
            determined_slot = "feet"
        elif item_info['type'] == "Neck":
            determined_slot = "neck"
        elif item_info['type'] == "Finger":
            if not await self.is_slot_filled("finger1"):
                determined_slot = "finger1"
            elif not await self.is_slot_filled("finger2"):
                determined_slot = "finger2"
            else:
                return "Both finger slots are occupied."
        elif item_info['type'] == "1H_weapon":
            # 1H weapons can be equipped in either hand, but not if 2H weapon is equipped
            if await self.is_slot_filled("2H_weapon"):
                return "Cannot equip a 1-handed weapon while a 2-handed weapon is equipped."
            # Try right hand first, then left hand
            if not await self.is_slot_filled("1H_weapon"):
                determined_slot = "1H_weapon"
            elif not await self.is_slot_filled("left_hand"):
                determined_slot = "left_hand"
            else:
                return "Both hands are occupied. Please unequip a weapon first."
        elif item_info['type'] == "2H_weapon":
            # 2H weapons require both hands to be free and no other 2H weapon equipped
            if await self.is_slot_filled("2H_weapon"):
                return "You can only equip one 2-handed weapon at a time."
            if await self.is_slot_filled("1H_weapon") or await self.is_slot_filled("left_hand"):
                return "Cannot equip a 2-handed weapon while 1-handed weapons are equipped in either hand."
            determined_slot = "2H_weapon"
        elif item_info['type'] == "Tool":
            determined_slot = await self.find_available_tool_belt_slot()
        elif item_info['type'] == "Weapon":
            # Check if it's a hatchet/axe (can be equipped in multiple ways)
            item_name_lower = item_info.get('name', '').lower()
            if 'hatchet' in item_name_lower or 'axe' in item_name_lower:
                # Return special indicator that slot selection is needed
                return "SELECT_SLOT"
            elif 'pickaxe' in item_name_lower:
                # Pickaxes always go to tool belt
                determined_slot = await self.find_available_tool_belt_slot()
            else:
                # Other weapons - treat as 1H weapons, can go in either hand
                # But not if 2H weapon is equipped
                if await self.is_slot_filled("2H_weapon"):
                    return "Cannot equip a weapon while a 2-handed weapon is equipped."
                # Try right hand first, then left hand
                if not await self.is_slot_filled("1H_weapon"):
                    determined_slot = "1H_weapon"
                elif not await self.is_slot_filled("left_hand"):
                    determined_slot = "left_hand"
                else:
                    return "Both hands are occupied. Please unequip a weapon first."

        if not determined_slot:
            return f"No available slot for {item_info['name']}."

        # Handle stack splitting: if quantity > 1, split the stack
        # Now that we allow multiple equipped entries, we can create a new equipped entry
        if quantity > 1:
            # Reduce the original stack by 1
            await self.db.execute("""
                UPDATE inventory SET quantity = quantity - 1 
                WHERE inventoryid = $1
            """, inventory_id)
            
            # Create a new equipped entry with quantity 1
            await self.db.execute("""
                INSERT INTO inventory (playerid, itemid, quantity, isequipped, slot, in_bank)
                VALUES ($1, $2, 1, true, $3, false)
            """, self.player_id, item_id, determined_slot)
        else:
            # Quantity is 1, just equip this entry
            await self.db.execute("""
                UPDATE inventory SET isequipped = true, slot = $1 
                WHERE inventoryid = $2
            """, determined_slot, inventory_id)

        slot_display = determined_slot.replace('_', ' ').title()
        return f"{item_info['name']} equipped in {slot_display}."

    async def find_available_tool_belt_slot(self):
        tool_belt_slots = await self.get_tool_belt_capacity()
        for i in range(tool_belt_slots):
            slot_name = f"tool_belt_{i}"
            if not await self.is_slot_filled(slot_name):
                return slot_name
        return None

    async def is_slot_filled(self, slot):
        return await self.db.fetchval("""
            SELECT COUNT(*) > 0 FROM inventory WHERE playerid = $1 AND slot = $2 AND isequipped = true
        """, self.player_id, slot)

    async def unequip_item(self, item_id):
        item_in_inventory = await self.db.fetchrow("""
            SELECT * FROM inventory WHERE playerid = $1 AND itemid = $2 AND isequipped = true
        """, self.player_id, item_id)

        if not item_in_inventory:
            return "Item is not equipped."

        await self.db.execute("""
            UPDATE inventory SET isequipped = false, slot = NULL WHERE inventoryid = $1
        """, item_in_inventory["inventoryid"])

        return "Item unequipped."

    async def view_inventory(self, ctx, player_id):
        # Fetch inventory data, including both regular items and caught fish entries
        inventory_entries = await self.db.fetch("""
            SELECT inv.inventoryid, inv.quantity, inv.isequipped, 
                   i.name AS item_name, cf.fish_name AS fish_name, cf.length, cf.weight, cf.rarity
            FROM inventory inv
            LEFT JOIN items i ON inv.itemid = i.itemid
            LEFT JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1
        """, player_id)

        # Initialize display content and components list
        inventory_display = ""
        components = []

        for entry in inventory_entries:
            if entry["item_name"]:  # Regular item
                item_display = f"{entry['item_name']} (x{entry['quantity']})"
                if entry["isequipped"]:
                    item_display += " - Equipped"
                    components.append#(Button(style=ButtonStyle.RED, label="Unequip", custom_id=f"unequip_{entry['inventoryid']}"))
                else:
                    components.append#(Button(style=ButtonStyle.GREEN, label="Equip", custom_id=f"equip_{entry['inventoryid']}"))
                inventory_display += item_display + "\n"

            elif entry["fish_name"]:  # Caught fish entry, no equip/unequip buttons
                fish_display = (f"{entry['fish_name']} (Rarity: {entry['rarity']}, "
                                f"Length: {entry['length']} cm, Weight: {entry['weight']} kg)")
                inventory_display += fish_display + "\n"

        # Send the inventory content with buttons only for equippable items
        await ctx.send(
            content=inventory_display or "Inventory is empty.",
            components=components if components else None
        )

