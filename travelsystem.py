class TravelSystem:
    def __init__(self, db):
        self.db = db

    async def display_locations(self, current_location_id):
        # Fetch and display available locations to the player
        available_paths = await self.get_available_paths(current_location_id)
        for path in available_paths:
            print(f"Path ID: {path['path_id']}, To Location: {path['to_location_name']}, Condition: {path['condition_description']}")

        # Fetch and display connected parent and child locations
        connected_locations = await self.get_connected_locations(current_location_id)
        for loc in connected_locations:
            print(f"Connected Location: {loc['name']}")

    async def travel_to_location(self, player_id, location_id):
        # Update the player's current location in the database
        await self.db.update_player_location(player_id, location_id)
        # Handle any other logic necessary for changing locations
        pass

    async def get_available_paths(self, current_location_id):
        async with self.db.pool.acquire() as conn:
            query = """
            SELECT p.path_id, 
                   CASE 
                     WHEN p.from_location_id = $1 THEN l_to.name 
                     ELSE l_from.name 
                   END AS to_location_name, 
                   p.condition, 
                   p.condition_description
            FROM public.paths p
            JOIN public.locations l_from ON p.from_location_id = l_from.locationid
            JOIN public.locations l_to ON p.to_location_id = l_to.locationid
            WHERE p.from_location_id = $1 OR p.to_location_id = $1
            """
            results = await conn.fetch(query, current_location_id)
            return results

    async def get_connected_locations(self, current_location_id):
        async with self.db.pool.acquire() as conn:
            query = """
            SELECT l2.locationid, l2.name
            FROM public.locations l1
            JOIN public.locations l2 ON l1.parentlocationid = l2.locationid OR l2.parentlocationid = l1.locationid
            WHERE l1.locationid = $1
            """
            results = await conn.fetch(query, current_location_id)
            return results

# Part of the Database class
class Database:
    def __init__(self, pool):
        self.pool = pool

    async def update_player_location(self, player_id, new_location_id):
        async with self.pool.acquire() as conn:
            await conn.execute("""
            UPDATE players
            SET current_location = $2
            WHERE playerid = $1
            """, player_id, new_location_id)
