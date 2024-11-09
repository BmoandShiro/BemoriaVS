class Inventory:
    def __init__(self, db, player_id):
        self.db = db
        self.player_id = player_id

    async def add_item(self, item_id, quantity=1):
        """
        Adds an item to the player's inventory. If the item is stackable, increases the quantity.
        Otherwise, adds a new entry for each unit if the item is not stackable.
        """
        # Check if the item exists in items table and is stackable
        item_info = await self.db.fetchrow("SELECT * FROM items WHERE itemid = $1", item_id)
        if not item_info:
            return "Invalid item."

        is_stackable = item_info["max_stack"] > 1

        # Check if the item already exists in the player's inventory
        existing_item = await self.db.fetchrow("""
            SELECT * FROM inventory WHERE playerid = $1 AND itemid = $2
        """, self.player_id, item_id)

        if existing_item and is_stackable:
            # Increase quantity if stackable
            new_quantity = existing_item["quantity"] + quantity
            await self.db.execute("""
                UPDATE inventory SET quantity = $1 WHERE inventoryid = $2
            """, new_quantity, existing_item["inventoryid"])
        else:
            # Add new entry if not stackable or doesn't exist in inventory
            await self.db.execute("""
                INSERT INTO inventory (playerid, itemid, quantity, isequipped, slot)
                VALUES ($1, $2, $3, false, NULL)
            """, self.player_id, item_id, quantity)

        return "Item added to inventory."

    async def remove_item(self, item_id, quantity=1):
        """
        Removes an item from the player's inventory. If stackable, decreases the quantity.
        If quantity reaches zero, removes the item from the inventory.
        """
        existing_item = await self.db.fetchrow("""
            SELECT * FROM inventory WHERE playerid = $1 AND itemid = $2
        """, self.player_id, item_id)

        if not existing_item:
            return "Item not found in inventory."

        if existing_item["quantity"] > quantity:
            # Decrease quantity if stackable and quantity is greater than 1
            new_quantity = existing_item["quantity"] - quantity
            await self.db.execute("""
                UPDATE inventory SET quantity = $1 WHERE inventoryid = $2
            """, new_quantity, existing_item["inventoryid"])
        else:
            # Remove the item if quantity is zero
            await self.db.execute("""
                DELETE FROM inventory WHERE inventoryid = $1
            """, existing_item["inventoryid"])

        return "Item removed from inventory."

    async def equip_item(self, item_id, slot):
        """
        Equips an item by setting isequipped to True and assigning it to the specified slot.
        Ensures only one item is equipped per slot.
        """
        # Check if item exists in inventory and is not already equipped
        item_in_inventory = await self.db.fetchrow("""
            SELECT * FROM inventory WHERE playerid = $1 AND itemid = $2
        """, self.player_id, item_id)

        if not item_in_inventory:
            return "Item not found in inventory."

        # Unequip any existing item in the same slot
        await self.db.execute("""
            UPDATE inventory SET isequipped = false, slot = NULL
            WHERE playerid = $1 AND slot = $2
        """, self.player_id, slot)

        # Equip the new item
        await self.db.execute("""
            UPDATE inventory SET isequipped = true, slot = $1 WHERE inventoryid = $2
        """, slot, item_in_inventory["inventoryid"])

        return "Item equipped."

    async def unequip_item(self, item_id):
        """
        Unequips an item by setting isequipped to False and clearing the slot.
        """
        # Check if the item is currently equipped
        item_in_inventory = await self.db.fetchrow("""
            SELECT * FROM inventory WHERE playerid = $1 AND itemid = $2 AND isequipped = true
        """, self.player_id, item_id)

        if not item_in_inventory:
            return "Item is not equipped."

        # Unequip the item
        await self.db.execute("""
            UPDATE inventory SET isequipped = false, slot = NULL WHERE inventoryid = $1
        """, item_in_inventory["inventoryid"])

        return "Item unequipped."

    async def view_inventory(self):
        """
        Retrieves and displays all items in the player's inventory.
        Shows item name, type, quantity, equipped status, and slot if equipped.
        """
        items = await self.db.fetch("""
            SELECT i.name, i.type, inv.quantity, inv.isequipped, inv.slot
            FROM inventory inv
            JOIN items i ON inv.itemid = i.itemid
            WHERE inv.playerid = $1
            ORDER BY inv.isequipped DESC, i.type, i.name
        """, self.player_id)

        if not items:
            return "Inventory is empty."

        # Display formatted inventory
        inventory_list = []
        for item in items:
            equipped_status = "Equipped" if item["isequipped"] else "Not Equipped"
            slot_info = f" in {item['slot']}" if item["isequipped"] and item["slot"] else ""
            inventory_list.append(f"{item['name']} ({item['type']}): {item['quantity']} - {equipped_status}{slot_info}")

        return "\n".join(inventory_list)

