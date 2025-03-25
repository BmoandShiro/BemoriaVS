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

class ForgeModule(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    async def get_player_id(self, discord_id):
        """Fetch the player ID using the Discord ID."""
        return await self.db.fetchval("""
            SELECT playerid FROM players WHERE discord_id = $1
        """, discord_id)

    async def get_item_name(self, item_id):
        """Fetch the name of an item."""
        return await self.db.fetchval("""
            SELECT name FROM items WHERE itemid = $1
        """, item_id)

    @component_callback(re.compile(r"^forge_\d+$"))
    async def forge_button_handler(self, ctx: ComponentContext):
        """Handle the forge button click."""
        original_user_id = int(ctx.custom_id.split("_")[1])
        if ctx.author.id != original_user_id:
            await ctx.send("You are not authorized to interact with this button.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)  # Acknowledge the interaction to prevent expiration
        player_id = await self.get_player_id(ctx.author.id)
        await self.display_forge_interface(ctx, player_id)

    async def display_forge_interface(self, ctx, player_id):
        """Display the forge interface with ore selection."""
        smelt_button = Button(
            style=ButtonStyle.PRIMARY,
            label="Smelt Ore",
            custom_id=f"forge_smelt_{player_id}"
        )

        await ctx.send(
            content="Welcome to the forge! Select ore to smelt:",
            components=[[smelt_button]],
            ephemeral=True
        )

    @component_callback(re.compile(r"^forge_smelt_\d+$"))
    async def smelt_ore_handler(self, ctx: ComponentContext):
        """Handle the ore smelting process."""
        try:
            player_id = await self.get_player_id(ctx.author.id)
            if not player_id:
                raise ValueError("Player ID not found for the current user.")

            # Fetch available ore from player's inventory
            ore_items = await self.db.fetch("""
                SELECT i.inventoryid, i.itemid, i.quantity, items.name
                FROM inventory i
                JOIN items ON i.itemid = items.itemid
                WHERE i.playerid = $1 AND items.name ILIKE '%Ore%'
            """, player_id)

            if not ore_items:
                await ctx.send("You don't have any ore to smelt.", ephemeral=True)
                return

            # Create dropdown options for available ore
            options = [
                StringSelectOption(
                    label=f"{item['name']} (x{item['quantity']})",
                    value=f"{item['inventoryid']}"
                )
                for item in ore_items
            ]

            # Create dropdown menu
            dropdown = StringSelectMenu(
                options[:25],  # Limit to 25 options as first positional argument
                custom_id=f"select_ore_{player_id}",
                placeholder="Choose ore to smelt"
            )

            await ctx.send(
                content="Select ore to smelt:",
                components=[dropdown],
                ephemeral=True
            )

        except Exception as e:
            logging.error(f"Error in smelt_ore_handler: {e}")
            await ctx.send("An error occurred while accessing the forge. Please try again.", ephemeral=True)

    @component_callback(re.compile(r"^select_ore_\d+$"))
    async def select_ore_handler(self, ctx: ComponentContext):
        """Handle ore selection and convert to bars."""
        try:
            player_id = int(ctx.custom_id.split("_")[-1])
            selected_inventory_id = int(ctx.values[0])

            # Get the selected ore details
            ore_details = await self.db.fetchrow("""
                SELECT i.itemid, i.quantity, items.name
                FROM inventory i
                JOIN items ON i.itemid = items.itemid
                WHERE i.inventoryid = $1 AND i.playerid = $2
            """, selected_inventory_id, player_id)

            if not ore_details:
                await ctx.send("Selected ore not found in your inventory.", ephemeral=True)
                return

            # Get the corresponding bar item ID (assuming bar itemid is ore itemid + 1)
            bar_itemid = ore_details['itemid'] + 1

            # Remove one ore from inventory
            await self.db.execute("""
                UPDATE inventory
                SET quantity = quantity - 1
                WHERE inventoryid = $1
            """, selected_inventory_id)

            # Add one bar to inventory
            await self.db.execute("""
                INSERT INTO inventory (playerid, itemid, quantity)
                VALUES ($1, $2, 1)
                ON CONFLICT (playerid, itemid)
                DO UPDATE SET quantity = inventory.quantity + 1
            """, player_id, bar_itemid)

            # Get the bar name
            bar_name = await self.get_item_name(bar_itemid)

            await ctx.send(
                f"Successfully smelted {ore_details['name']} into {bar_name}!",
                ephemeral=True
            )

            # Clean up inventory (remove items with quantity 0)
            await self.db.execute("""
                DELETE FROM inventory
                WHERE quantity <= 0
            """)

        except Exception as e:
            logging.error(f"Error in select_ore_handler: {e}")
            await ctx.send("An error occurred while smelting the ore. Please try again.", ephemeral=True)

# Setup function to load this as an extension
def setup(bot):
    """Setup function to add the extension to the bot."""
    ForgeModule(bot) 