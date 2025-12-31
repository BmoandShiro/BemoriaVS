from interactions import Extension
import logging
import json

class DynamicPricing(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.price_cache = {}  # Cache for storing dynamic prices
        
    async def get_shop_config(self, shop_id):
        """Get shop-specific configuration including default markup rates"""
        config = await self.db.fetchrow("""
            SELECT default_markup_rate, default_sell_rate
            FROM shop_config 
            WHERE shop_id = $1
        """, shop_id)
        
        return {
            'markup_rate': config['default_markup_rate'] if config else 0.2,  # 20% default markup
            'sell_rate': config['default_sell_rate'] if config else 0.75  # 75% default sell value
        }

    async def get_item_price_rules(self, shop_id, item_id):
        """Get item-specific pricing rules for a shop"""
        rules = await self.db.fetchrow("""
            SELECT custom_buy_price, custom_sell_price, markup_rate, sell_rate,
                   min_price, max_price, quantity_affects_price
            FROM shop_item_rules
            WHERE shop_id = $1 AND itemid = $2
        """, shop_id, item_id)
        
        return rules

    async def calculate_quantity_modifier(self, shop_id, item_id, base_price):
        """Calculate price modifier based on quantity in shop"""
        quantity = await self.db.fetchval("""
            SELECT quantity FROM shop_items 
            WHERE shop_id = $1 AND itemid = $2 AND is_player_sold = true
        """, shop_id, item_id)
        
        if not quantity:
            return 1.0
            
        # Basic supply/demand modifier: price decreases as quantity increases
        # Can be customized per shop/item using shop_item_rules
        return max(0.5, 1.0 - (quantity * 0.01))  # Minimum 50% of base price

    async def get_dynamic_price(self, shop_id, item_id, is_buying=True):
        """
        Calculate dynamic price for an item
        is_buying=True means player is buying from shop (higher price)
        is_buying=False means player is selling to shop (lower price)
        """
        # Get base price from shop_items table
        base_item = await self.db.fetchrow("""
            SELECT price, is_player_sold FROM shop_items 
            WHERE itemid = $1 AND shop_id = $2
            ORDER BY is_player_sold DESC
            LIMIT 1
        """, item_id, shop_id)
        
        if not base_item:
            return None
            
        base_price = base_item['price']
        shop_config = await self.get_shop_config(shop_id)
        price_rules = await self.get_item_price_rules(shop_id, item_id)
        
        if is_buying:
            # Check for custom buy price first
            if price_rules and price_rules['custom_buy_price'] is not None:
                return price_rules['custom_buy_price']
                
            # If item was player-sold, apply markup
            if base_item['is_player_sold']:
                markup_rate = (price_rules['markup_rate'] 
                             if price_rules and price_rules['markup_rate'] is not None 
                             else shop_config['markup_rate'])
                             
                price = base_price * (1 + markup_rate)
            else:
                price = base_price
                
            # Apply quantity modifier if enabled for this item
            if price_rules and price_rules['quantity_affects_price']:
                quantity_mod = await self.calculate_quantity_modifier(shop_id, item_id, price)
                price *= quantity_mod
                
            # Enforce min/max prices if set
            if price_rules:
                if price_rules['min_price'] is not None:
                    price = max(price, price_rules['min_price'])
                if price_rules['max_price'] is not None:
                    price = min(price, price_rules['max_price'])
                    
            return price
            
        else:  # Selling to shop
            # Check for custom sell price first
            if price_rules and price_rules['custom_sell_price'] is not None:
                return price_rules['custom_sell_price']
                
            # Apply sell rate
            sell_rate = (price_rules['sell_rate'] 
                        if price_rules and price_rules['sell_rate'] is not None 
                        else shop_config['sell_rate'])
                        
            return base_price * sell_rate
            
    async def process_purchase(self, ctx, player_id, shop_id, item_id, quantity=1):
        """Process a player purchasing an item from a shop"""
        price = await self.get_dynamic_price(shop_id, item_id, is_buying=True)
        if not price:
            await ctx.send("This item is not available in the shop.", ephemeral=True)
            return False
            
        total_cost = price * quantity
        
        # Check if player has enough gold
        player_gold = await self.db.fetchval("""
            SELECT gold_balance FROM player_data WHERE playerid = $1
        """, player_id)
        
        if player_gold < total_cost:
            await ctx.send("You don't have enough gold for this purchase.", ephemeral=True)
            return False
            
        # Process transaction
        async with self.db.acquire() as connection:
            async with connection.transaction():
                # Deduct gold
                await connection.execute("""
                    UPDATE player_data 
                    SET gold_balance = gold_balance - $1 
                    WHERE playerid = $2
                """, total_cost, player_id)
                
                # Add to inventory
                await connection.execute("""
                    INSERT INTO inventory (playerid, itemid, quantity, isequipped)
                    VALUES ($1, $2, $3, false)
                    ON CONFLICT (playerid, itemid) 
                    DO UPDATE SET quantity = inventory.quantity + $3
                """, player_id, item_id, quantity)
                
                # Update shop stock
                await connection.execute("""
                    UPDATE shop_items 
                    SET quantity = quantity - $1 
                    WHERE itemid = $2 AND shop_id = $3 AND quantity >= $1
                """, quantity, item_id, shop_id)
                
        await ctx.send(f"You bought {quantity}x item for {total_cost} gold.", ephemeral=True)
        return True
        
    async def process_sale(self, ctx, player_id, shop_id, inventory_id, quantity=1):
        """Process a player selling an item to a shop"""
        # Get item details from inventory
        item = await self.db.fetchrow("""
            SELECT i.itemid, i.quantity, si.price 
            FROM inventory i
            JOIN shop_items si ON i.itemid = si.itemid
            WHERE i.inventoryid = $1 AND i.playerid = $2 AND si.shop_id = $3
        """, inventory_id, player_id, shop_id)
        
        if not item:
            await ctx.send("This item cannot be sold to this shop.", ephemeral=True)
            return False
            
        if item['quantity'] < quantity:
            await ctx.send("You don't have enough of this item to sell.", ephemeral=True)
            return False
            
        sell_price = await self.get_dynamic_price(shop_id, item['itemid'], is_buying=False)
        total_value = sell_price * quantity
        
        # Process transaction
        async with self.db.acquire() as connection:
            async with connection.transaction():
                # Add gold to player
                await connection.execute("""
                    UPDATE player_data 
                    SET gold_balance = gold_balance + $1 
                    WHERE playerid = $2
                """, total_value, player_id)
                
                # Remove from inventory
                if item['quantity'] == quantity:
                    await connection.execute("""
                        DELETE FROM inventory 
                        WHERE inventoryid = $1 AND playerid = $2
                    """, inventory_id, player_id)
                else:
                    await connection.execute("""
                        UPDATE inventory 
                        SET quantity = quantity - $1 
                        WHERE inventoryid = $2 AND playerid = $3
                    """, quantity, inventory_id, player_id)
                
                # Add to shop's inventory
                await connection.execute("""
                    INSERT INTO shop_items (itemid, shop_id, price, quantity, is_player_sold)
                    VALUES ($1, $2, $3, $4, true)
                    ON CONFLICT (itemid, shop_id, is_player_sold) 
                    DO UPDATE SET 
                        quantity = shop_items.quantity + $4,
                        price = EXCLUDED.price
                """, item['itemid'], shop_id, sell_price, quantity)
                
        await ctx.send(f"You sold {quantity}x item for {total_value} gold.", ephemeral=True)
        
        # Update any relevant quest progress
        await self.update_shop_quest_progress(player_id, shop_id, total_value)
        return True
        
    async def update_shop_quest_progress(self, player_id, shop_id, gold_value):
        """Update progress for any active shop-related quests"""
        quest = await self.db.fetchrow("""
            SELECT q.quest_id, q.objective, pq.progress 
            FROM quests q
            JOIN player_quests pq ON q.quest_id = pq.quest_id
            WHERE pq.player_id = $1 
            AND pq.status = 'in_progress'
            AND q.objective->>'type' = 'sell_to_shop'
            AND q.objective->>'shop_id' = $2
        """, player_id, shop_id)
        
        if quest:
            current_progress = float(quest['progress'] or 0)
            new_progress = current_progress + gold_value
            target_value = float(json.loads(quest['objective'])['target_value'])
            
            await self.db.execute("""
                UPDATE player_quests 
                SET progress = $1,
                    status = CASE WHEN $1 >= $4 THEN 'completed' ELSE 'in_progress' END
                WHERE player_id = $2 AND quest_id = $3
            """, new_progress, player_id, quest['quest_id'], target_value) 