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
                "location": "Dave Fishery",
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

        # Add shop items to the embed
        if shop_items:
            for item in shop_items:
                shop_embed.add_field(name=item["name"], value=f"Price: {item['price']} gold", inline=False)

            # Create a dropdown selection for buying items
            options = [
                StringSelectOption(
                    label=f"{item['name']} - {item['price']} gold",
                    value=f"{item['name'].replace(' ', '_')}"
                )
                for item in shop_items
            ]

            # Initialize the StringSelectMenu for buying items
            buy_select = StringSelectMenu(
                custom_id="select_item_to_buy",
                placeholder="Select an item to buy"
            )
            # Set options after initializing
            buy_select.options = options

            # Arrange components with sell button and buy selection dropdown
            components = [[buy_select], [Button(style=ButtonStyle.PRIMARY, label="Sell Fish", custom_id="sell_fish")]]
        else:
            components = [[Button(style=ButtonStyle.PRIMARY, label="Sell Fish", custom_id="sell_fish")]]

        # Log to check how buttons are arranged
        logging.info(f"Components for shop: {components}")

        # Send the shop embed along with components
        try:
            await ctx.send(embeds=[shop_embed], components=components, ephemeral=True)
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
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)

        # Fetch the details of the fish being sold
        fish = await self.bot.db.fetchrow("""
            SELECT cf.fish_name, cf.length, cf.weight, cf.rarity
            FROM inventory inv
            JOIN caught_fish cf ON inv.caught_fish_id = cf.id
            WHERE inv.inventoryid = $1 AND inv.playerid = $2
        """, int(ctx.values[0]), player_id)

        if not fish:
            await ctx.send("Error: The selected fish could not be found.", ephemeral=True)
            return

        # Fetch player data to get the current location
        player_data = await self.bot.db.fetchrow("""
            SELECT current_location
            FROM player_data
            WHERE playerid = $1
        """, player_id)

        if not player_data:
            await ctx.send("Error: Unable to retrieve player data.", ephemeral=True)
            return

        # Calculate the value of the fish
        base_value = await self._get_base_value(fish["fish_name"])
        price = self._calculate_fish_value(
            base_value, 
            fish["length"], 
            fish["weight"], 
            fish["rarity"], 
            player_data['current_location']
        )

        # Remove the fish from inventory and add gold to player's balance
        await self._remove_fish_from_inventory(player_id, int(ctx.values[0]))
        await self._add_gold(player_id, price)

        await ctx.send(f"You sold a {fish['fish_name']} for {price:.2f} gold!", ephemeral=True)
        

    @component_callback("select_item_to_buy")
    async def select_item_to_buy_handler(self, ctx: ComponentContext):
        await ctx.defer(ephemeral=True)  # Defer the response to avoid timeout
        player_id = await self.bot.db.get_or_create_player(ctx.author.id)
        item_name = ctx.values[0].replace('_', ' ')

        # Fetch the shop items for the current location
        player_data = await self.bot.db.fetchrow("""
            SELECT current_location
            FROM player_data
            WHERE playerid = $1
        """, player_id)

        if not player_data:
            await ctx.send("Error: Unable to retrieve player data.", ephemeral=True)
            return

        location = player_data['current_location']
        shop_items = await self.get_shop_items(location)

        # Find the item in the shop
        item_to_buy = next((item for item in shop_items if item["name"].lower() == item_name.lower()), None)

        if not item_to_buy:
            await ctx.send("Error: Item not found in this shop.", ephemeral=True)
            return

        # Check if player has enough gold
        player_data = await self.bot.db.fetchrow("""
            SELECT gold_balance
            FROM player_data
            WHERE playerid = $1
        """, player_id)

        if player_data["gold_balance"] < item_to_buy["price"]:
            await ctx.send("You don't have enough gold to buy this item.", ephemeral=True)
            return

        # Deduct gold and add item to player's inventory
        await self._deduct_gold(player_id, item_to_buy["price"])
        await self._add_item_to_inventory(player_id, item_to_buy)

        await ctx.send(f"You successfully bought {item_to_buy['name']} for {item_to_buy['price']} gold!", ephemeral=True)




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
    
    def _calculate_fish_value(self, base_value, length, weight, rarity, location):
        # Ensure all values are of type float
        base_value = float(base_value)
        length = float(length)
        weight = float(weight)

        # Calculate value based on base value, length, weight, and rarity
        rarity_multiplier = {
            "common": 1.0, 
            "uncommon": 1.1, 
            "rare": 1.25, 
            "very rare": 1.5, 
            "legendary": 2.0
        }
        location_multiplier = self.shops.get(location, {}).get("sell_multiplier", 1.0)

        # Base value modified by length and weight, then adjusted by rarity and location
        value = (base_value * length * weight) * rarity_multiplier.get(rarity.lower(), 1.0) * location_multiplier
        return value


# Setup function for ShopManager
def setup(bot):
   ShopManager(bot)
