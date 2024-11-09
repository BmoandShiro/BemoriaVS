# inventory_system.py

from Inventory import Inventory  # Ensure Inventory class has a view_inventory method

class InventorySystem:
    def __init__(self, db):
        self.db = db  # Store the database instance

    def get_inventory_for_player(self, player_id):
        """
        Returns an Inventory instance for the specified player ID.
        """
        return Inventory(self.db, player_id)

    async def display_inventory(self, ctx, player_id):
        """
        Retrieves and sends the player's inventory information in the chat.
        """
        # Get the Inventory instance for the player
        inventory = self.get_inventory_for_player(player_id)

        # Retrieve the inventory view from the Inventory instance
        inventory_view = await inventory.view_inventory()  # This calls the view_inventory method in the Inventory class

        # Send the inventory display to the user
        if inventory_view:
            await ctx.send(inventory_view)
        else:
            await ctx.send("Your inventory is empty.")
