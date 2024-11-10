from interactions import Button, ButtonStyle, ComponentContext


class Inventory:
    def __init__(self, db, player_id):
        self.db = db
        self.player_id = player_id

    async def add_item(self, item_id, quantity=1):
        # Fetch maximum slots and current item count
        max_slots = await self.db.get_inventory_capacity(self.player_id)
        current_item_count = await self.db.fetchval(
            "SELECT COUNT(*) FROM inventory WHERE playerid = $1",
            self.player_id
        )

        # Check if the player has enough slots
        if current_item_count >= max_slots:
            return "Your inventory is full. You cannot add more items."

        # Check if the item exists and if it's stackable
        item_info = await self.db.fetchrow("SELECT * FROM items WHERE itemid = $1", item_id)
        if not item_info:
            return "Invalid item."

        is_stackable = item_info["max_stack"] > 1

        # Add or update item in inventory
        existing_item = await self.db.fetchrow(
            "SELECT * FROM inventory WHERE playerid = $1 AND itemid = $2",
            self.player_id, item_id
        )

        if existing_item and is_stackable:
            new_quantity = existing_item["quantity"] + quantity
            await self.db.execute(
                "UPDATE inventory SET quantity = $1 WHERE inventoryid = $2",
                new_quantity, existing_item["inventoryid"]
            )
        else:
            await self.db.execute(
                "INSERT INTO inventory (playerid, itemid, quantity, isequipped, slot) VALUES ($1, $2, $3, false, NULL)",
                self.player_id, item_id, quantity
            )

        # Calculate remaining slots
        remaining_slots = max_slots - (current_item_count + 1)
        return f"Item added to inventory. Remaining slots: {remaining_slots}."

    async def remove_item(self, item_id, quantity=1):
        # Check if item exists in inventory
        existing_item = await self.db.fetchrow(
            "SELECT * FROM inventory WHERE playerid = $1 AND itemid = $2",
            self.player_id, item_id
        )

        if not existing_item:
            return "Item not found in inventory."

        # Update quantity or remove item if quantity is zero
        if existing_item["quantity"] > quantity:
            new_quantity = existing_item["quantity"] - quantity
            await self.db.execute(
                "UPDATE inventory SET quantity = $1 WHERE inventoryid = $2",
                new_quantity, existing_item["inventoryid"]
            )
        else:
            await self.db.execute(
                "DELETE FROM inventory WHERE inventoryid = $1",
                existing_item["inventoryid"]
            )

        # Calculate remaining slots after removal
        max_slots = await self.db.get_inventory_capacity(self.player_id)
        current_item_count = await self.db.fetchval(
            "SELECT COUNT(*) FROM inventory WHERE playerid = $1",
            self.player_id
        )
        remaining_slots = max_slots - current_item_count

        return f"Item removed from inventory. Remaining slots: {remaining_slots}."
    
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

    async def view_inventory(self, ctx):
        items = await self.db.fetch("""
            SELECT i.itemid, i.name, i.type, inv.quantity, inv.isequipped, inv.slot
            FROM inventory inv
            JOIN items i ON inv.itemid = i.itemid
            WHERE inv.playerid = $1
            ORDER BY inv.isequipped DESC, i.type, i.name
        """, self.player_id)

        if not items:
            return await ctx.send("Inventory is empty.", ephemeral=True)

        # Format and display inventory information
        inventory_list = []
        for item in items:
            equipped_status = "Equipped" if item["isequipped"] else "Not Equipped"
            slot_info = f" in {item['slot']}" if item["isequipped"] and item["slot"] else ""
            inventory_list.append(f"{item['name']} ({item['type']}): {item['quantity']} - {equipped_status}{slot_info}")

        return "\n".join(inventory_list)
