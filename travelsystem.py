class TravelSystem:
    def __init__(self, db):
        self.db = db

    async def display_locations(self, current_location_id):
        # Fetch and display available locations to the player
        pass

    async def travel_to_location(self, player_id, location_id):
        # Update the player's current location in the database
        await self.db.update_player_location(player_id, location_id)
        
        # Handle any other logic necessary for changing locations
        pass

# Part of the Database class
async def update_player_location(self, player_id, new_location_id):
    async with self.pool.acquire() as conn:
        await conn.execute("""
            UPDATE players
            SET current_location = $2
            WHERE playerid = $1;
        """, player_id, new_location_id)

