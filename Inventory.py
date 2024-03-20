class Inventory:
    def __init__(self, db):
        self.db = db  # Your Database instance

    async def add_item(self, playerid, itemid, quantity):
        async with self.db.pool.acquire() as conn:
            # Check if the item already exists in the inventory
            existing_qty = await conn.fetchval("""
                SELECT quantity FROM inventory
                WHERE playerid = $1 AND itemid = $2;
            """, playerid, itemid)
            
            if existing_qty is not None:  # If it exists, update the quantity
                new_quantity = existing_qty + quantity
                await conn.execute("""
                    UPDATE inventory
                    SET quantity = $3
                    WHERE playerid = $1 AND itemid = $2;
                """, playerid, itemid, new_quantity)
            else:  # If not, insert a new row
                await conn.execute("""
                    INSERT INTO inventory (playerid, itemid, quantity)
                    VALUES ($1, $2, $3);
                """, playerid, itemid, quantity)

    async def get_inventory(self, playerid):
        async with self.db.pool.acquire() as conn:
            # Fetch all items in the player's inventory
            inventory = await conn.fetch("""
                SELECT * FROM inventory
                WHERE playerid = $1;
            """, playerid)
            return inventory
