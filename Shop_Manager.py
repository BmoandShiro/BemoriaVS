from interactions import Extension, component_callback, Button, ButtonStyle, ComponentContext, StringSelectMenu, StringSelectOption, Embed
import logging
import re

class ShopManager(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db  # Consistent with InventorySystem

    async def load_shops(self):
        # Fetch all shop locations and details from the database
        shop_details = await self.db.fetch("""
            SELECT s.shop_id, s.shop_location, s.itemid, s.quantity, s.price, i.name, i.type
            FROM shop_items s
            JOIN items i ON s.itemid = i.itemid
        """)

        # Organize shop details into a dictionary similar to self.shops
        shops = {}
        for record in shop_details:
            location = record["shop_location"]

            # If this location is not yet in the dictionary, initialize it
            if location not in shops:
                shops[location] = {
                    "location": location,
                    "inventory": [],
                    "sell_multiplier": 1.0,  # Default sell multiplier
                    "requirements": {}  # Placeholder for requirements
                }
            
            # Append the item details to the shop's inventory
            shops[location]["inventory"].append({
                "name": record["name"],
                "type": record["type"],
                "price": record["price"],
                "quantity": record["quantity"]
            })

        return shops

   

    async def handle_shop(self, ctx, player_data):
        # Ensure you get the current location ID from player's data
        if 'current_location' not in player_data:
            await ctx.send("Error: Player's current location not found.", ephemeral=True)
            return

        location_id = player_data['current_location']

        # Fetch the actual location name from the locations table using the location_id
        location_data = await self.db.fetchrow("""
            SELECT name
            FROM locations
            WHERE locationid = $1
        """, location_id)

        if not location_data:
            await ctx.send("Error: Unable to retrieve location details for the provided location ID.", ephemeral=True)
            return

        location_name = location_data["name"]

        # Fetch shop items for the location
        shop_items = await self.get_shop_items(location_name)

        # Log to check if shop items are retrieved properly
        logging.info(f"Shop items for {location_name}: {shop_items}")

        # Create an embed to display shop items
        shop_embed = Embed(
            title=f"{location_name} Shop",
            description="Items available for purchase:" if shop_items else "No items available for purchase",
            color=0xFFD700  # Gold color for the shop interface
        )

        # Add shop items to the embed
        if shop_items:
            options = []
            for item in shop_items:
                # Add items to the embed
                shop_embed.add_field(name=item["name"], value=f"Price: {item['price']} gold", inline=False)

                # Prepare options for StringSelectMenu
                options.append(StringSelectOption(
                    label=f"{item['name']} - {item['price']} gold",
                    value=f"{item['name'].replace(' ', '_')}"
                ))

            # Initialize the StringSelectMenu for buying items
            buy_select = StringSelectMenu(
                custom_id="select_item_to_buy",
                placeholder="Select an item to buy",
                options=options
            )

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
        # Fetch shop items for the given location from the database
        shop_items = await self.db.fetch("""
            SELECT i.name, s.price, i.type, s.quantity
            FROM shop_items s
            JOIN items i ON s.itemid = i.itemid
            WHERE s.shop_location = $1
        """, str(location))

        return shop_items
    
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

    async def _deduct_gold(self, player_id, amount):
        # Deduct the gold from the player's balance in the DB
        await self.db.execute("""
            UPDATE player_data
            SET gold_balance = gold_balance - $1
            WHERE playerid = $2
        """, amount, player_id)

    async def _add_item_to_inventory(self, player_id, item):
        # Add the purchased item to the player's inventory
        await self.db.execute("""
            INSERT INTO inventory (playerid, itemid, quantity, isequipped)
            VALUES ($1, (SELECT itemid FROM items WHERE name = $2), 1, FALSE)
        """, player_id, item['name'])

# Setup function for ShopManager
def setup(bot):
   ShopManager(bot)
