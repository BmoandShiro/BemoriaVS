from interactions import Extension, ComponentContext, component_callback, Button, ButtonStyle, Embed, StringSelectMenu, StringSelectOption
import logging
import re

class WaltsWeapons(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        logging.info("WaltsWeapons extension initialized")

    @component_callback(re.compile(r"^walts_shop"))
    async def shop_button_handler(self, ctx: ComponentContext):
        """Handle the Shop button click at Walt's Weapons"""
        try:
            player_id = await self.bot.db.get_or_create_player(ctx.author.id)
            
            # Verify player is at Walts Weapons location
            player_location = await self.db.fetchval("""
                SELECT current_location FROM player_data WHERE playerid = $1
            """, player_id)
            
            if player_location != 11:  # Walts Weapons locationid
                await ctx.send("You must be at Walts Weapons to use this shop.", ephemeral=True)
                return
            
            await ctx.defer(ephemeral=True)
            await self.display_shop(ctx, player_id)
        except Exception as e:
            logging.error(f"Error in shop_button_handler: {e}", exc_info=True)
            await ctx.send("An error occurred while accessing the shop. Please try again later.", ephemeral=True)

    async def display_shop(self, ctx: ComponentContext, player_id):
        """Display Walt's Weapons shop interface"""
        try:
            # Fetch available items in the shop
            items = await self.db.fetch("""
                SELECT i.itemid, i.name, i.description, si.price, si.quantity,
                       i.slashing_damage, i.piercing_damage, i.crushing_damage, i.dark_damage
                FROM shop_items si
                JOIN items i ON si.itemid = i.itemid
                WHERE si.shop_id = 10 AND si.locationid = 11 AND si.is_player_sold = false
                ORDER BY i.itemid
            """)
            
            if not items:
                await ctx.send("The shop is currently empty.", ephemeral=True)
                return

            # Create embed for shop display
            embed = Embed(
                title="Walt's Weapons",
                description="Welcome to Walt's Weapons! Here are the available weapons:",
                color=0xFFD700  # Gold color
            )

            # Add items to embed with damage info
            for item in items:
                damage_parts = []
                if item['slashing_damage'] and item['slashing_damage'] > 0:
                    damage_parts.append(f"S:{item['slashing_damage']}")
                if item['piercing_damage'] and item['piercing_damage'] > 0:
                    damage_parts.append(f"P:{item['piercing_damage']}")
                if item['crushing_damage'] and item['crushing_damage'] > 0:
                    damage_parts.append(f"C:{item['crushing_damage']}")
                if item['dark_damage'] and item['dark_damage'] > 0:
                    damage_parts.append(f"D:{item['dark_damage']}")
                
                damage_str = " / ".join(damage_parts) if damage_parts else "No damage"
                
                embed.add_field(
                    name=f"{item['name']} - {item['price']} gold",
                    value=f"Damage: {damage_str}\n{item['description'] or 'A fine weapon'}",
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
                            label=f"Buy {item['name']} ({item['price']}g)",
                            custom_id=f"walt_buy_{item['itemid']}_{player_id}"
                        )
                    )

            # Group buttons into rows (max 5 per row)
            button_rows = []
            for i in range(0, len(components), 5):
                button_rows.append(components[i:i+5])

            await ctx.send(embeds=[embed], components=button_rows, ephemeral=True)

        except Exception as e:
            logging.error(f"Error in display_shop: {e}", exc_info=True)
            await ctx.send("An error occurred while displaying the shop. Please try again later.", ephemeral=True)

    @component_callback(re.compile(r"^walt_buy_(\d+)_(\d+)$"))
    async def buy_item_handler(self, ctx: ComponentContext):
        """Handle buying an item from Walt's shop"""
        try:
            match = re.match(r"^walt_buy_(\d+)_(\d+)$", ctx.custom_id)
            if not match:
                await ctx.send("Invalid purchase request.", ephemeral=True)
                return
            
            item_id = int(match.group(1))
            button_player_id = int(match.group(2))
            
            # Verify this player clicked the button
            player_id = await self.bot.db.get_or_create_player(ctx.author.id)
            if player_id != button_player_id:
                await ctx.send("You are not authorized to use this button.", ephemeral=True)
                return
            
            await ctx.defer(ephemeral=True)
            
            # Get item details
            item = await self.db.fetchrow("""
                SELECT si.price, si.quantity, i.name
                FROM shop_items si
                JOIN items i ON si.itemid = i.itemid
                WHERE si.shop_id = 10 AND si.locationid = 11 
                AND si.itemid = $1 AND si.is_player_sold = false
            """, item_id)
            
            if not item:
                await ctx.send("This item is not available in the shop.", ephemeral=True)
                return
            
            if item['quantity'] <= 0:
                await ctx.send("This item is out of stock.", ephemeral=True)
                return
            
            # Check if player has enough gold
            player_gold = await self.db.fetchval("""
                SELECT gold_balance FROM player_data WHERE playerid = $1
            """, player_id)
            
            if player_gold < item['price']:
                await ctx.send(f"You don't have enough gold. You need {item['price']} gold, but you only have {player_gold} gold.", ephemeral=True)
                return
            
            # Process purchase
            async with self.db.pool.acquire() as connection:
                async with connection.transaction():
                    # Deduct gold
                    await connection.execute("""
                        UPDATE player_data 
                        SET gold_balance = gold_balance - $1 
                        WHERE playerid = $2
                    """, item['price'], player_id)
                    
                    # Check for existing item in main inventory (not bank, not equipped)
                    existing_item = await connection.fetchrow("""
                        SELECT inventoryid, quantity FROM inventory 
                        WHERE playerid = $1 AND itemid = $2 
                        AND isequipped = FALSE 
                        AND (in_bank = FALSE OR in_bank IS NULL)
                    """, player_id, item_id)
                    
                    if existing_item:
                        # Update existing stack
                        await connection.execute("""
                            UPDATE inventory SET quantity = quantity + 1
                            WHERE inventoryid = $1
                        """, existing_item['inventoryid'])
                    else:
                        # Insert new item
                        await connection.execute("""
                            INSERT INTO inventory (playerid, itemid, quantity, isequipped, in_bank)
                            VALUES ($1, $2, 1, false, false)
                        """, player_id, item_id)
            
            await ctx.send(f"You successfully bought {item['name']} for {item['price']} gold!", ephemeral=True)
            
            # Refresh shop display
            await self.display_shop(ctx, player_id)
            
        except Exception as e:
            logging.error(f"Error in buy_item_handler: {e}", exc_info=True)
            await ctx.send("An error occurred while processing your purchase. Please try again later.", ephemeral=True)

    @component_callback(re.compile(r"^talk_walt"))
    async def talk_walt_handler(self, ctx: ComponentContext):
        """Handle talking to Walt"""
        try:
            player_id = await self.bot.db.get_or_create_player(ctx.author.id)
            
            # Verify player is at Walts Weapons location
            player_location = await self.db.fetchval("""
                SELECT current_location FROM player_data WHERE playerid = $1
            """, player_id)
            
            if player_location != 11:  # Walts Weapons locationid
                await ctx.send("You must be at Walts Weapons to talk to Walt.", ephemeral=True)
                return
            
            await ctx.defer(ephemeral=True)
            
            # Walt's dialogue (placeholder for now, can add quest later)
            embed = Embed(
                title="Walt",
                description="*Walt looks up from polishing a sword.*\n\n"
                           "Well met, traveler! Welcome to my shop. I've got the finest bronze and iron weapons "
                           "this side of the realm. Take a look around, and if you see something you like, "
                           "we can make a deal.\n\n"
                           "I don't deal in the heavy stuff - greatswords, battle axes, polearms - those are "
                           "for the big smiths. But what I have here will serve you well, I promise you that.",
                color=0xFFD700
            )
            
            await ctx.send(embeds=[embed], ephemeral=True)
            
        except Exception as e:
            logging.error(f"Error in talk_walt_handler: {e}", exc_info=True)
            await ctx.send("An error occurred. Please try again.", ephemeral=True)

def setup(bot):
    """Setup function to initialize the WaltsWeapons extension"""
    WaltsWeapons(bot)

