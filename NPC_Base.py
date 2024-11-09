class NPCBase:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def give_item(self, ctx, player_id, item_name, quantity=1):
        item_id = await self.db.fetchval("SELECT itemid FROM items WHERE name = $1", item_name)
        if item_id:
            await self.db.execute(
                "INSERT INTO inventory (playerid, itemid, quantity) VALUES ($1, $2, $3) "
                "ON CONFLICT (playerid, itemid) DO UPDATE SET quantity = inventory.quantity + $3",
                player_id, item_id, quantity
            )
            await ctx.send(f"You received {quantity} x {item_name}.")
        else:
            await ctx.send("Item not found.")

