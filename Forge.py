import logging
from interactions import (
    Extension, 
    Button, 
    ButtonStyle, 
    ComponentContext, 
    component_callback,
    StringSelectMenu, 
    StringSelectOption
)
import re
from typing import Dict, List, Tuple

class ForgeModule(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        # Define crafting requirements for each bar
        # Format: bar_itemid: [(ore_itemid, quantity), ...]
        self.forge_recipes = {
            # Iron Bar (230) <- Iron Ore (146)
            230: [(146, 3)],
            # Bronze Bar (210) <- Copper Ore (149) + Tin Ore (220)
            210: [(149, 2), (220, 1)],
            # Silver Bar (208) <- Silver Ore (150)
            208: [(150, 3)],
            # Gold Bar (209) <- Gold Ore (151)
            209: [(151, 3)],
            # Steel Bar (231) <- Iron Ore (146) + Steel Ore (147)
            231: [(146, 2), (147, 1)],
            # Platinum Bar (214) <- Platinum Ore (232)
            214: [(232, 3)],
            # Starmetal Bar (216) <- Starmetal Ore (233)
            216: [(233, 3)]
        }

    async def get_player_id(self, discord_id):
        """Fetch the player ID using the Discord ID."""
        return await self.db.fetchval("""
            SELECT playerid FROM players WHERE discord_id = $1
        """, discord_id)

    async def get_item_name(self, item_id):
        """Fetch the name of an item."""
        if item_id is None:
            return None
        return await self.db.fetchval("""
            SELECT name FROM items WHERE itemid = $1
        """, item_id)

    async def get_item_id(self, item_name):
        """Fetch the item ID using the item name."""
        return await self.db.fetchval("""
            SELECT itemid FROM items WHERE name = $1
        """, item_name)

    async def check_ingredients(self, player_id: int, recipe: List[Tuple[int, int]]) -> bool:
        """Check if player has all required ingredients in sufficient quantities."""
        for ore_id, required_qty in recipe:
            if ore_id is None:  # Skip recipes with undefined ore IDs
                return False
            
            quantity = await self.db.fetchval("""
                SELECT quantity FROM inventory
                WHERE playerid = $1 AND itemid = $2
            """, player_id, ore_id)
            
            if not quantity or quantity < required_qty:
                return False
        return True

    async def get_available_bars(self, player_id: int) -> List[Dict]:
        """Get list of bars that can be crafted based on player's inventory."""
        available_bars = []
        
        for bar_id, recipe in self.forge_recipes.items():
            if bar_id is None:  # Skip recipes where we don't have the bar ID yet
                continue
                
            if await self.check_ingredients(player_id, recipe):
                bar_name = await self.get_item_name(bar_id)
                if bar_name:
                    # Get ingredient names for display
                    ingredients = []
                    for ore_id, qty in recipe:
                        ore_name = await self.get_item_name(ore_id)
                        if ore_name:
                            ingredients.append((ore_name, qty))
                    
                    available_bars.append({
                        'name': bar_name,
                        'itemid': bar_id,
                        'recipe': recipe,
                        'ingredients': ingredients
                    })
        
        return available_bars

    @component_callback(re.compile(r"^forge_\d+$"))
    async def forge_button_handler(self, ctx: ComponentContext):
        """Handle the forge button click."""
        original_user_id = int(ctx.custom_id.split("_")[1])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
        player_id = await self.get_player_id(ctx.author.id)
        await self.display_forge_interface(ctx, player_id)

    async def display_forge_interface(self, ctx, player_id):
        """Display the forge interface with bar selection."""
        forge_button = Button(
            style=ButtonStyle.PRIMARY,
            label="Forge Bar",
            custom_id=f"forge_smelt_{player_id}"
        )

        await ctx.send(
            content="Welcome to the forge! Click to see available bars to forge:",
            components=[[forge_button]],
            ephemeral=True
        )

    @component_callback(re.compile(r"^forge_smelt_\d+$"))
    async def smelt_ore_handler(self, ctx: ComponentContext):
        """Handle the bar forging process."""
        try:
            player_id = await self.get_player_id(ctx.author.id)
            if not player_id:
                raise ValueError("Player ID not found for the current user.")

            # Get available bars based on inventory
            available_bars = await self.get_available_bars(player_id)

            if not available_bars:
                await ctx.send("You don't have enough materials to forge any bars.", ephemeral=True)
                return

            # Create dropdown options for available bars
            options = []
            for bar in available_bars:
                recipe_text = ", ".join([f"{qty}x {ore}" for ore, qty in bar['ingredients']])
                options.append(
                    StringSelectOption(
                        label=f"{bar['name']}",
                        value=f"{bar['itemid']}",
                        description=f"Requires: {recipe_text}"
                    )
                )

            # Create dropdown menu
            dropdown = StringSelectMenu(
                options[:25],
                custom_id=f"select_bar_{player_id}",
                placeholder="Choose bar to forge"
            )

            await ctx.send(
                content="Select a bar to forge:",
                components=[dropdown],
                ephemeral=True
            )

        except Exception as e:
            logging.error(f"Error in smelt_ore_handler: {e}")
            await ctx.send("An error occurred while accessing the forge. Please try again.", ephemeral=True)

    @component_callback(re.compile(r"^select_bar_\d+$"))
    async def select_bar_handler(self, ctx: ComponentContext):
        """Handle bar selection and create it from ingredients."""
        try:
            player_id = int(ctx.custom_id.split("_")[-1])
            selected_bar_id = int(ctx.values[0])
            
            recipe = self.forge_recipes.get(selected_bar_id)
            if not recipe:
                await ctx.send("Invalid bar selection.", ephemeral=True)
                return

            # Verify ingredients again
            if not await self.check_ingredients(player_id, recipe):
                await ctx.send("You no longer have the required materials.", ephemeral=True)
                return

            # Remove ingredients from inventory
            for ore_id, required_qty in recipe:
                await self.db.execute("""
                    UPDATE inventory
                    SET quantity = quantity - $1
                    WHERE playerid = $2 AND itemid = $3
                """, required_qty, player_id, ore_id)

            # Add the bar to inventory
            await self.db.execute("""
                INSERT INTO inventory (playerid, itemid, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (playerid, itemid)
                DO UPDATE SET quantity = inventory.quantity + 1
            """, player_id, selected_bar_id)

            # Get names for message
            bar_name = await self.get_item_name(selected_bar_id)
            ingredients_text = []
            for ore_id, qty in recipe:
                ore_name = await self.get_item_name(ore_id)
                ingredients_text.append(f"{qty}x {ore_name}")

            await ctx.send(
                f"Successfully forged {bar_name}! (Used: {', '.join(ingredients_text)})",
                ephemeral=True
            )

            # Clean up inventory (remove items with quantity 0)
            await self.db.execute("""
                DELETE FROM inventory
                WHERE quantity <= 0
            """)

        except Exception as e:
            logging.error(f"Error in select_bar_handler: {e}")
            await ctx.send("An error occurred while forging the bar. Please try again.", ephemeral=True)

# Setup function to load this as an extension
def setup(bot):
    """Setup function to add the extension to the bot."""
    ForgeModule(bot) 