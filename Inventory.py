from interactions import Button, ButtonStyle, ComponentContext

class Inventory:
    def __init__(self, db, player_id):
        self.db = db
        self.player_id = player_id

    async def add_item(self, item_id, quantity=1):
        max_slots = await self.db.get_inventory_capacity(self.player_id)
        current_item_count = await self.db.fetchval(
            "SELECT COUNT(*) FROM inventory WHERE playerid = $1",
            self.player_id
        )

        if current_item_count >= max_slots:
            return "Your inventory is full. You cannot add more items."

        item_info = await self.db.fetchrow("SELECT * FROM items WHERE itemid = $1", item_id)
        if not item_info:
            return "Invalid item."

        is_stackable = item_info["max_stack"] > 1

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

        remaining_slots = max_slots - (current_item_count + 1)
        return f"Item added to inventory. Remaining slots: {remaining_slots}."

    async def remove_item(self, item_id, quantity=1):
        existing_item = await self.db.fetchrow(
            "SELECT * FROM inventory WHERE playerid = $1 AND itemid = $2",
            self.player_id, item_id
        )

        if not existing_item:
            return "Item not found in inventory."

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

        max_slots = await self.db.get_inventory_capacity(self.player_id)
        current_item_count = await self.db.fetchval(
            "SELECT COUNT(*) FROM inventory WHERE playerid = $1",
            self.player_id
        )
        remaining_slots = max_slots - current_item_count

        return f"Item removed from inventory. Remaining slots: {remaining_slots}."

    async def get_tool_belt_capacity(self):
        tool_belt_slots = await self.db.fetchval("""
            SELECT tool_belt_slots FROM player_data WHERE playerid = $1
        """, self.player_id)
        return tool_belt_slots or 12  # Default to 12 if not set

    async def equip_item(self, item_id):
        item_info = await self.db.fetchrow("SELECT * FROM items WHERE itemid = $1", item_id)
        if not item_info:
            return "Item not found."

        slot = None
        if item_info['type'] == "Helmet":
            slot = "helmet"
        elif item_info['type'] == "Chest":
            slot = "chest"
        elif item_info['type'] == "Back":
            slot = "back"
        elif item_info['type'] == "Legs":
            slot = "legs"
        elif item_info['type'] == "Feet":
            slot = "feet"
        elif item_info['type'] == "Neck":
            slot = "neck"
        elif item_info['type'] == "Finger":
            if not await self.is_slot_filled("finger1"):
                slot = "finger1"
            elif not await self.is_slot_filled("finger2"):
                slot = "finger2"
            else:
                return "Both finger slots are occupied."
        elif item_info['type'] == "1H_weapon" and not await self.is_slot_filled("2H_weapon"):
            slot = "1H_weapon"
        elif item_info['type'] == "2H_weapon" and not await self.is_slot_filled("1H_weapon") and not await self.is_slot_filled("2H_weapon"):
            slot = "2H_weapon"
        elif item_info['type'] == "Tool":
            slot = await self.find_available_tool_belt_slot()

        if not slot:
            return f"No available slot for {item_info['name']}."

        await self.db.execute("""
            UPDATE inventory SET isequipped = true, slot = $1 WHERE playerid = $2 AND itemid = $3
        """, slot, self.player_id, item_id)

        return f"{item_info['name']} equipped in {slot}."

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

        inventory_list = []
        for item in items:
            equipped_status = "Equipped" if item["isequipped"] else "Not Equipped"
            slot_info = f" in {item['slot']}" if item["isequipped"] and item["slot"] else ""
            inventory_list.append(f"{item['name']} ({item['type']}): {item['quantity']} - {equipped_status}{slot_info}")

        return "\n".join(inventory_list)
