
# shop_manager.py

from interactions import Embed

class ShopManager:
    def __init__(self):
        # Define shops with their inventory, location, and availability criteria
        self.shops = {
            "Dave's Fishery": {
                "location": "Dave's Fishery",
                "inventory": [
                    {"name": "Ocean Rod", "type": "Tool", "price": 7500, "rod_type": "Deep"},
                ],
                "requirements": {
                    "quest_completed": 2  # Quest ID required to unlock shop
                }
            }
        }

    async def can_access_shop(self, player_location, player):
        shop = self.shops.get(player_location)
        if shop and await player.quest_completed(shop['requirements']['quest_completed']):
            return True
        return False

    async def get_shop_items(self, location):
        if location in self.shops:
            return self.shops[location]["inventory"]
        return []

    async def handle_buy(self, ctx, player, item_name):
        # Fetch shop inventory and match the item
        location = player.current_location
        items = await self.get_shop_items(location)

        item_to_buy = next((item for item in items if item["name"] == item_name), None)
        if not item_to_buy:
            await ctx.send("Item not found in the shop.")
            return

        # Check if player has enough gold
        if player.gold_balance < item_to_buy["price"]:
            await ctx.send("You don't have enough gold to buy this item.")
            return

        # Deduct gold and add item to inventory
        await self._deduct_gold(player.player_id, item_to_buy["price"])
        await self._add_item_to_inventory(player.player_id, item_to_buy)

        await ctx.send(f"You successfully bought {item_name} for {item_to_buy['price']} gold!")

    async def handle_sell(self, ctx, player, fish_id):
        # Assess the value of the fish and add gold to player's balance
        fish = await self._get_fish_details(fish_id)
        if not fish:
            await ctx.send("Fish not found.")
            return

        base_value = await self._get_base_value(fish["name"])
        price = self.calculate_fish_value(base_value, fish["length"], fish["weight"])

        # Remove fish from inventory and add gold to balance
        await self._remove_fish_from_inventory(player.player_id, fish_id)
        await self._add_gold(player.player_id, price)

        await ctx.send(f"You sold a {fish['name']} for {price} gold!")

    async def calculate_fish_value(self, base_value, length, weight):
        # Calculate value based on base value, length, and weight
        return base_value + (length * 0.5) + (weight * 1.0)

    # Private functions for handling DB operations
    async def _deduct_gold(self, player_id, amount):
        # Deduct the gold from the player's balance in the DB
        await self.db.execute("""
            UPDATE player_data
            SET gold_balance = gold_balance - $1
            WHERE playerid = $2
        """, amount, player_id)

    async def _add_gold(self, player_id, amount):
        # Add gold to the player's balance
        await self.db.execute("""
            UPDATE player_data
            SET gold_balance = gold_balance + $1
            WHERE playerid = $2
        """, amount, player_id)

    async def _add_item_to_inventory(self, player_id, item):
        # Add item to player's inventory
        await self.db.execute("""
            INSERT INTO inventory (playerid, itemid, quantity, isequipped, slot)
            VALUES ($1, $2, 1, false, NULL)
        """, player_id, item["name"])

    async def _remove_fish_from_inventory(self, player_id, fish_id):
        # Remove fish from player's inventory
        await self.db.execute("""
            DELETE FROM caught_fish
            WHERE id = $1 AND player_id = $2
        """, fish_id, player_id)

    async def _get_fish_details(self, fish_id):
        # Fetch fish details from DB
        return await self.db.fetchrow("""
            SELECT * FROM caught_fish WHERE id = $1
        """, fish_id)

    async def _get_base_value(self, fish_name):
        # Fetch base value from a fish table
        return await self.db.fetchval("""
            SELECT base_value FROM fish WHERE name = $1
        """, fish_name)
    
    async def handle_shop(ctx, player):
        # Fetch available items for the current shop location
        location = player.current_location
        shop_items = await self.get_shop_items(location)

        if not shop_items:
            await ctx.send("There are no items available in this shop.")
            return

        # Create an embed to display shop items
        shop_embed = Embed(
            title=f"{location} Shop",
            description="Items available for purchase:",
            color=0xFFD700  # Gold color for the shop interface
        )

        for item in shop_items:
            shop_embed.add_field(name=item["name"], value=f"Price: {item['price']} gold", inline=False)

        # Create a 'Buy' button for each item available
        shop_buttons = [
            Button(style=ButtonStyle.SUCCESS, label=f"Buy {item['name']}", custom_id=f"buy_{item['name']}_{ctx.author.id}")
            for item in shop_items
        ]

        # Arrange buttons in rows of up to 5 each
        button_rows = [shop_buttons[i:i + 5] for i in range(0, len(shop_buttons), 5)]

        # Send the shop embed along with buttons
        await ctx.send(embeds=[shop_embed], components=button_rows)
