from Inventory import Inventory
from interactions import Extension, component_callback, Button, ButtonStyle, ComponentContext, StringSelectMenu, StringSelectOption

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

        inventory_items = await self.db.fetch("""
            SELECT inv.inventoryid, inv.quantity, inv.isequipped, 
                   COALESCE(i.name, cf.fish_name) AS item_name, cf.length, cf.weight, cf.rarity
            FROM inventory inv
            LEFT JOIN items i ON inv.itemid = i.itemid
            LEFT JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1 AND inv.in_bank = FALSE
        """, player_id)

        if not inventory_items:
            return await ctx.send("Inventory is empty.", ephemeral=True)

        # Build detailed inventory display
        inventory_view = ""
        for item in inventory_items:
            if item['item_name']:
                if item['length'] and item['weight']:
                    inventory_view += f"{item['item_name']} (Rarity: {item['rarity']}, Length: {item['length']} cm, Weight: {item['weight']} kg)\n"
                else:
                    inventory_view += f"{item['item_name']} (x{item['quantity']})"
                if item['isequipped']:
                    inventory_view += " - Equipped"
                inventory_view += "\n"

        # Adding equip, unequip, drop, and transfer buttons
        equip_button = Button(style=ButtonStyle.SUCCESS, label="Equip Item", custom_id="equip_item")
        unequip_button = Button(style=ButtonStyle.DANGER, label="Unequip Item", custom_id="unequip_item")
        drop_button = Button(style=ButtonStyle.DANGER, label="Drop Item", custom_id="drop_item")

        components = [[equip_button, unequip_button, drop_button]]

        # Add transfer buttons if the player is at a bank
        if is_at_bank:
            transfer_to_bank_button = Button(style=ButtonStyle.SECONDARY, label="Transfer to Bank", custom_id="transfer_to_bank")
            transfer_to_inventory_button = Button(style=ButtonStyle.SECONDARY, label="Transfer to Inventory", custom_id="transfer_to_inventory")
            components.append([transfer_to_bank_button, transfer_to_inventory_button])

        # Send the inventory content and appropriate buttons
        await ctx.send(content=inventory_view, components=components, ephemeral=True)
    

    async def display_bank(self, ctx, player_id):
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

            # Adding transfer button to bring items back to inventory
            transfer_to_inventory_button = Button(style=ButtonStyle.SECONDARY, label="Transfer to Inventory", custom_id="transfer_to_inventory")

            # Send the bank inventory content and transfer button
            await ctx.send(content=bank_view, components=[[transfer_to_inventory_button]], ephemeral=True)
        

        

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
        
    @component_callback("bank_\d+")
    async def bank_button_handler(self, ctx: ComponentContext):
        player_id = await self.db.get_or_create_player(ctx.author.id)

        # Fetch items currently in the bank
        bank_items = await self.db.fetch("""
            SELECT inv.inventoryid, inv.quantity, inv.isequipped,
                   COALESCE(i.name, cf.fish_name) AS item_name, cf.length, cf.weight, cf.rarity
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
                if item['isequipped']:
                    bank_view += " - Equipped"
                bank_view += "\n"

        # Adding equip, unequip, drop, and transfer buttons
        equip_button = Button(style=ButtonStyle.SUCCESS, label="Equip Item", custom_id="equip_item")
        unequip_button = Button(style=ButtonStyle.DANGER, label="Unequip Item", custom_id="unequip_item")
        drop_button = Button(style=ButtonStyle.DANGER, label="Drop Item", custom_id="drop_item")
        transfer_to_inventory_button = Button(style=ButtonStyle.SECONDARY, label="Transfer to Inventory", custom_id="transfer_to_inventory")

        components = [[equip_button, unequip_button, drop_button, transfer_to_inventory_button]]

        # Send the bank inventory content and appropriate buttons
        await ctx.send(content=bank_view, components=components, ephemeral=True)

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
