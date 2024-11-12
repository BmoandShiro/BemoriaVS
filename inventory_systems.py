from Inventory import Inventory
from interactions import Extension, component_callback, Button, ButtonStyle, ComponentContext, StringSelectMenu, StringSelectOption

class InventorySystem(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    def get_inventory_for_player(self, player_id):
        return Inventory(self.db, player_id)

    async def display_inventory(self, ctx, player_id):
        inventory = self.get_inventory_for_player(player_id)
        inventory_view = await inventory.view_inventory(ctx, player_id)

        equip_button = Button(style=ButtonStyle.SUCCESS, label="Equip Item", custom_id="equip_item")
        unequip_button = Button(style=ButtonStyle.DANGER, label="Unequip Item", custom_id="unequip_item")
        drop_button = Button(style=ButtonStyle.DANGER, label="Drop Item", custom_id="drop_item")  
        
        await ctx.send(content=inventory_view, components=[equip_button, unequip_button, drop_button], ephemeral=True)

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

    @component_callback("unequip_item")
    async def unequip_item_handler(self, ctx: ComponentContext):
        player_id = await self.db.get_or_create_player(ctx.author.id)
        items = await self.db.fetch("""
            SELECT i.itemid, i.name FROM inventory inv
            JOIN items i ON inv.itemid = i.itemid
            WHERE inv.playerid = $1 AND inv.isequipped = true
        """, player_id)

        if not items:
            return await ctx.send("No items currently equipped.", ephemeral=True)

        options = [StringSelectOption(label=item['name'], value=str(item['itemid'])) for item in items]
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
        result = await inventory.equip_item(item_id)
        await ctx.send(result, ephemeral=True)

    @component_callback("select_unequip_item")
    async def select_unequip_item_handler(self, ctx: ComponentContext):
        item_id = int(ctx.values[0])
        player_id = await self.db.get_or_create_player(ctx.author.id)
        inventory = self.get_inventory_for_player(player_id)
        result = await inventory.unequip_item(item_id)
        await ctx.send(result, ephemeral=True)

# Setup function to load this as an extension
def setup(bot):
    InventorySystem(bot)
