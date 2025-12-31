from interactions import Extension, SlashContext, component_callback, ComponentContext, Button, ButtonStyle, Embed
import logging
import json
import re

def setup(bot):
    """Setup function to initialize the GeneralStore extension"""
    logging.info("Setting up GeneralStore extension...")
    GeneralStore(bot)
    logging.info("GeneralStore extension initialized successfully.")

class GeneralStore(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.price_cache = {}  # Cache for storing dynamic prices
        self.markup_rate = 0.2  # 20% markup on sold items
        logging.info("GeneralStore class initialized")
        
    async def get_dynamic_price(self, item_id, is_buying=True):
        """
        Calculate dynamic price for an item
        is_buying=True means player is buying from shop (higher price)
        is_buying=False means player is selling to shop (lower price)
        """
        # Get base price from shop_items table
        base_price = await self.db.fetchval("""
            SELECT price FROM shop_items 
            WHERE itemid = $1 AND shop_id = 2
        """, item_id)
        
        if not base_price:
            return None
            
        if is_buying:
            # Apply markup if item was previously sold to shop
            sold_count = await self.db.fetchval("""
                SELECT quantity FROM shop_items 
                WHERE itemid = $1 AND shop_id = 2 AND is_player_sold = true
            """, item_id)
            
            if sold_count:
                return base_price * (1 + self.markup_rate)
            
        return base_price if is_buying else base_price * 0.75  # 25% reduction when selling
        
    async def buy_item(self, ctx: ComponentContext, player_id, item_id, quantity=1):
        """Handle player buying an item from the shop"""
        price = await self.get_dynamic_price(item_id, is_buying=True)
        if not price:
            await ctx.send("This item is not available in the shop.", ephemeral=True)
            return
            
        total_cost = price * quantity
        
        # Check if player has enough gold
        player_gold = await self.db.fetchval("""
            SELECT gold_balance FROM player_data WHERE playerid = $1
        """, player_id)
        
        if player_gold < total_cost:
            await ctx.send("You don't have enough gold for this purchase.", ephemeral=True)
            return
            
        # Add item to player's inventory and deduct gold
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
                
                # Update shop stock if it was a player-sold item
                await connection.execute("""
                    UPDATE shop_items 
                    SET quantity = quantity - $1 
                    WHERE itemid = $2 AND shop_id = 2 AND is_player_sold = true
                    AND quantity >= $1
                """, quantity, item_id)
                
        await ctx.send(f"You bought {quantity}x item for {total_cost} gold.", ephemeral=True)
        
    async def sell_item(self, ctx: ComponentContext, player_id, inventory_id, quantity=1):
        """Handle player selling an item to the shop"""
        # Get item details from inventory
        item = await self.db.fetchrow("""
            SELECT i.itemid, i.quantity, si.price 
            FROM inventory i
            JOIN shop_items si ON i.itemid = si.itemid
            WHERE i.inventoryid = $1 AND i.playerid = $2 AND si.shop_id = 2
        """, inventory_id, player_id)
        
        if not item:
            await ctx.send("This item cannot be sold to the general store.", ephemeral=True)
            return
            
        if item['quantity'] < quantity:
            await ctx.send("You don't have enough of this item to sell.", ephemeral=True)
            return
            
        sell_price = await self.get_dynamic_price(item['itemid'], is_buying=False)
        total_value = sell_price * quantity
        
        # Process the sale
        async with self.db.acquire() as connection:
            async with connection.transaction():
                # Add gold to player
                await connection.execute("""
                    UPDATE player_data 
                    SET gold_balance = gold_balance + $1 
                    WHERE playerid = $2
                """, total_value, player_id)
                
                # Remove items from inventory
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
                
                # Add to shop's player-sold items
                await connection.execute("""
                    INSERT INTO shop_items (itemid, shop_id, price, quantity, is_player_sold)
                    VALUES ($1, 2, $2, $3, true)
                    ON CONFLICT (itemid, shop_id, is_player_sold) 
                    DO UPDATE SET quantity = shop_items.quantity + $3
                """, item['itemid'], sell_price * (1 + self.markup_rate), quantity)
                
        await ctx.send(f"You sold {quantity}x item for {total_value} gold.", ephemeral=True)
        
        # Update quest progress if applicable
        await self.update_quest_progress(player_id, total_value)
        
    async def update_quest_progress(self, player_id, gold_value):
        """Update progress for Ingrid's quest if active"""
        quest = await self.db.fetchrow("""
            SELECT q.quest_id, q.objective, pq.progress 
            FROM quests q
            JOIN player_quests pq ON q.quest_id = pq.quest_id
            WHERE pq.player_id = $1 AND pq.status = 'in_progress'
            AND q.npc_id = 'ingrid'  -- Assuming this is Ingrid's NPC ID
        """, player_id)
        
        if quest:
            current_progress = float(quest['progress'] or 0)
            new_progress = current_progress + gold_value
            
            await self.db.execute("""
                UPDATE player_quests 
                SET progress = $1,
                    status = CASE WHEN $1 >= 4500 THEN 'completed' ELSE 'in_progress' END
                WHERE player_id = $2 AND quest_id = $3
            """, new_progress, player_id, quest['quest_id'])

    @component_callback("Shop")
    async def shop_button_handler(self, ctx: ComponentContext):
        """Handle the Shop button click"""
        try:
            logging.info("Shop button clicked - starting handler")
            player_id = await self.bot.db.get_or_create_player(ctx.author.id)
            logging.info(f"Got player_id: {player_id}")
            await self.display_shop(ctx, player_id)
        except Exception as e:
            logging.error(f"Error in shop_button_handler: {str(e)}", exc_info=True)
            await ctx.send("An error occurred while accessing the shop. Please try again later.", ephemeral=True)

    async def display_shop(self, ctx: ComponentContext, player_id):
        """Display the shop interface with available items"""
        try:
            logging.info("Starting display_shop")
            # Fetch available items in the shop
            items = await self.db.fetch("""
                SELECT i.itemid, i.name, i.description, si.price, si.quantity
                FROM shop_items si
                JOIN items i ON si.itemid = i.itemid
                WHERE si.shop_id = 2 AND si.is_player_sold = false
                ORDER BY i.name
            """)
            logging.info(f"Fetched {len(items) if items else 0} items from shop")

            if not items:
                await ctx.send("The shop is currently empty.", ephemeral=True)
                return

            # Create embed for shop display
            embed = Embed(
                title="General Store",
                description="Welcome to the General Store! Here are the available items:",
                color=0x00FF00
            )

            # Add items to embed
            for item in items:
                price = await self.get_dynamic_price(item['itemid'], is_buying=True)
                if price:
                    embed.add_field(
                        name=f"{item['name']} - {price} gold",
                        value=f"{item['description']}\nQuantity: {item['quantity']}",
                        inline=False
                    )

            # Add player's gold balance
            player_gold = await self.db.fetchval("""
                SELECT gold_balance FROM player_data WHERE playerid = $1
            """, player_id)
            embed.set_footer(text=f"Your gold: {player_gold}")

            # Create buttons for each item
            components = []
            for item in items:
                if item['quantity'] > 0:
                    components.append(
                        Button(
                            style=ButtonStyle.PRIMARY,
                            label=f"Buy {item['name']}",
                            custom_id=f"buy_item_{item['itemid']}"
                        )
                    )

            logging.info(f"Sending shop display with {len(components)} buy buttons")
            await ctx.send(embeds=[embed], components=components, ephemeral=True)
            logging.info("Shop display sent successfully")

        except Exception as e:
            logging.error(f"Error in display_shop: {str(e)}", exc_info=True)
            await ctx.send("An error occurred while displaying the shop. Please try again later.", ephemeral=True)

    @component_callback(re.compile(r"^buy_item_(\d+)$"))
    async def buy_item_handler(self, ctx: ComponentContext):
        """Handle buying an item from the shop"""
        try:
            item_id = int(ctx.custom_id.split("_")[2])
            player_id = await self.bot.db.get_or_create_player(ctx.author.id)
            await self.buy_item(ctx, player_id, item_id)
            # Refresh shop display after purchase
            await self.display_shop(ctx, player_id)
        except Exception as e:
            logging.error(f"Error in buy_item_handler: {e}")
            await ctx.send("An error occurred while processing your purchase. Please try again later.", ephemeral=True) 