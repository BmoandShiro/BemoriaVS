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

        await ctx.send(content=inventory_view, components=[equip_button, unequip_button], ephemeral=True)

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
