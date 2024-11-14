from interactions import Extension, component_callback, Button, ButtonStyle, ComponentContext, StringSelectMenu, StringSelectOption, Embed
import logging
import re

class ShopManager(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db  # Consistent with InventorySystem

        # Define shops with their inventory, location, and availability criteria
        self.shops = {
            "Dave's Fishery": {
                "location": "Dave's Fishery",
                "inventory": [
                    {"name": "Ocean Rod", "type": "Tool", "price": 7500, "rod_type": "Deep"},
                ],
                "requirements": {
                    "quest_completed": 2  # Quest ID required to unlock shop
                },
                "sell_multiplier": 1.25  # Multiplier for selling fish here
            }
        }

   

    async def handle_shop(self, ctx, player_data):
        location = player_data['current_location']
        shop_items = await self.get_shop_items(location)

        # Log to check if shop items are retrieved properly
        logging.info(f"Shop items for {location}: {shop_items}")

        # Create an embed to display shop items
        shop_embed = Embed(
            title=f"{location} Shop",
            description="Items available for purchase:" if shop_items else "No items available for purchase",
            color=0xFFD700  # Gold color for the shop interface
        )

        if shop_items:
            for item in shop_items:
                shop_embed.add_field(name=item["name"], value=f"Price: {item['price']} gold", inline=False)

        # Create a 'Buy' button for each item available
        buy_buttons = [
            Button(style=ButtonStyle.SUCCESS, label=f"Buy {item['name']}", custom_id=f"buy_{item['name'].replace(' ', '_')}")
            for item in shop_items
        ]

        # Add a sell button to allow the player to sell their fish
        sell_button = Button(style=ButtonStyle.PRIMARY, label="Sell Fish", custom_id="sell_fish")

        # Arrange components into rows (up to 5 per row)
        button_rows = [buy_buttons[i:i + 5] for i in range(0, len(buy_buttons), 5)]

        # Always add the sell button as a separate row
        button_rows.append([sell_button])

        # Log to check how buttons are arranged
        logging.info(f"Button rows for shop: {button_rows}")

        # Send the shop embed along with buttons
        try:
            await ctx.send(embeds=[shop_embed], components=button_rows, ephemeral=True)
        except Exception as e:
            logging.error(f"Failed to send shop message: {e}")


    @component_callback("sell_fish")
    async def sell_fish_handler(self, ctx: ComponentContext):
        await ctx.defer(ephemeral=True)
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)

        # Fetch the fish in the player's inventory
        fish_items = await self.bot.db.fetch("""
            SELECT inv.inventoryid, cf.fish_name, cf.length, cf.weight, cf.rarity
            FROM inventory inv
            JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.playerid = $1 AND inv.in_bank = FALSE
        """, player_id)

        if not fish_items:
            await ctx.send("You don't have any fish to sell.", ephemeral=True)
            return

        # Create options for dropdown selection
        options = [
            StringSelectOption(
                label=f"{fish['fish_name']} (Length: {fish['length']} cm, Weight: {fish['weight']} kg, Rarity: {fish['rarity']})",
                value=str(fish['inventoryid'])
            )
            for fish in fish_items
        ]

        # Initialize the StringSelectMenu without 'options' parameter
        sell_select = StringSelectMenu(
            custom_id="select_fish_to_sell",
            placeholder="Select a fish to sell"
        )
        # Set options after initializing
        sell_select.options = options

        # Display the dropdown to select a fish to sell
        await ctx.send("Choose a fish to sell:", components=[[sell_select]], ephemeral=True)
        
    @component_callback("select_fish_to_sell")
    async def select_fish_to_sell_handler(self, ctx: ComponentContext):
        await ctx.defer(ephemeral=True)
        inventory_id = int(ctx.values[0])
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)

        # Fetch the details of the fish being sold
        fish = await self.bot.db.fetchrow("""
            SELECT cf.fish_name, cf.length, cf.weight, cf.rarity
            FROM inventory inv
            JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.inventoryid = $1 AND inv.playerid = $2
        """, inventory_id, player_id)

        if not fish:
            await ctx.send("Error: The selected fish could not be found.", ephemeral=True)
            return

        # Calculate the value of the fish based on its length, weight, and rarity
        base_value = await self._get_base_value(fish["fish_name"])
        price = self.calculate_fish_value(base_value, fish["length"], fish["weight"], fish["rarity"], player_id)

        # Remove the fish from inventory and add gold to player's balance
        await self._remove_fish_from_inventory(player_id, inventory_id)
        await self._add_gold(player_id, price)

        await ctx.send(f"You sold a {fish['fish_name']} for {price:.2f} gold!", ephemeral=True)

    async def _get_base_value(self, fish_name):
        # Fetch base value from a fish table using bot.db
        return await self.bot.db.fetchval("""
            SELECT base_value FROM fish WHERE name = $1
        """, fish_name)

    async def _remove_fish_from_inventory(self, player_id, inventory_id):
        # Remove fish from player's inventory using bot.db
        await self.bot.db.execute("""
            DELETE FROM inventory
            WHERE inventoryid = $1 AND playerid = $2
        """, inventory_id, player_id)

    async def _add_gold(self, player_id, amount):
        # Add gold to player's balance using bot.db
        await self.bot.db.execute("""
            UPDATE player_data
            SET gold_balance = gold_balance + $1
            WHERE playerid = $2
        """, amount, player_id)
        
    async def get_shop_items(self, location):
        # Fetch the inventory items for the given location
        if location in self.shops:
            return self.shops[location]["inventory"]
        return []

# Setup function for ShopManager
def setup(bot):
   ShopManager(bot)
