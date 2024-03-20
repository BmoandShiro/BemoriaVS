import asyncpg
import asyncio


class Database:
    def __init__(self, dsn):
        self.dsn = dsn
        self.pool = None
        
    

    async def connect(self):
        self.pool = await asyncpg.create_pool(dsn=self.dsn)

    async def close(self):
        await self.pool.close()

    async def create_pool(self):
        print("DSN being used:", self.dsn)
        self.pool = await asyncpg.create_pool(self.dsn)
    async def fetch_races(self):
        if self.pool is None:
            await self.create_pool()  # Make sure the pool is created before using it

        async with self.pool.acquire() as conn:
            races = await conn.fetch('SELECT raceid, name FROM races ORDER BY raceid')
            return races

        await conn.execute(
            """
         INSERT INTO player_data (playerid, raceid) VALUES ($1, $2)
         ON CONFLICT (playerid) DO UPDATE SET raceid = EXCLUDED.raceid
            """,
            discord_id,  # Use integer directly
            raceid)
            
    async def fetch_background_titles(self):
        async with self.pool.acquire() as conn:
            titles = await conn.fetch('SELECT titleid, titlename FROM titles WHERE background = true ORDER BY titleid')
            return titles

    async def save_player_choice(self, discord_id, raceid):
        # Acquire a connection from the pool
        async with self.pool.acquire() as conn:
            # Ensure the player exists and get the playerid
            player_id = await conn.fetchval("""
                INSERT INTO players (discord_id)
                VALUES ($1)
                ON CONFLICT (discord_id) DO NOTHING
                RETURNING playerid;
            """, discord_id)

            # If player_id is None, it means the player already exists; fetch the existing playerid
            if player_id is None:
                player_id = await conn.fetchval("SELECT playerid FROM players WHERE discord_id = $1", discord_id)

            # Insert or update player's race choice
            await conn.execute("""
                INSERT INTO player_data (playerid, raceid)
                VALUES ($1, $2)
                ON CONFLICT (playerid) DO UPDATE
                SET raceid = EXCLUDED.raceid;
            """, player_id, raceid)

    

            
    async def get_or_create_player(self, discord_id):
            async with self.pool.acquire() as conn:
                # Try to get the player by Discord ID
                player = await conn.fetchrow(
                    "SELECT playerid FROM players WHERE discord_id = $1",
                    discord_id
                )
                if player:
                    return player['playerid']
                else:
                    # If not found, insert the new player and return the new ID
                    playerid = await conn.fetchval(
                        "INSERT INTO players (discord_id) VALUES ($1) RETURNING playerid",
                        discord_id
                    )
                    return playerid    
                
    async def save_player_title_choice(self, discord_id, titleid):
        # Acquire a connection from the pool
        async with self.pool.acquire() as conn:
            # Fetch the player's id from the players table using discord_id
            player_id = await conn.fetchval("""
                SELECT playerid FROM players WHERE discord_id = $1
            """, discord_id)

            # Insert or update the player's title choice in player_titles table
            await conn.execute("""
                INSERT INTO player_titles (playerid, titleid, is_active)
                VALUES ($1, $2, true)
                ON CONFLICT (playerid, titleid) DO UPDATE
                SET is_active = EXCLUDED.is_active;
            """, player_id, titleid)

    # Part of the Database class
    async def set_initial_location(self, player_id, location_id=2):  # Default location_id for Tradewind City
        async with self.pool.acquire() as conn:
            # Update the player_data table instead of players
            await conn.execute("""
                UPDATE player_data
                SET current_location = $2
                WHERE playerid = $1;
            """, player_id, location_id)


    async def fetch_player_details(self, player_id):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT pd.health, pd.mana, pd.stamina, l.name
                FROM player_data pd
                JOIN locations l ON l.locationid = pd.current_location
                WHERE pd.playerid = $1;
            """, player_id)
            return dict(row) if row else None
        
    async def fetch_accessible_locations(self, current_location_id):
        async with self.pool.acquire() as conn:
            # Retrieve locations that are directly accessible from the current location
            rows = await conn.fetch("""
                SELECT 
                    loc.name, 
                    loc.description, 
                    loc.locationid
                FROM 
                    paths 
                JOIN 
                    locations loc ON loc.locationid = paths.to_location_id
                WHERE 
                    paths.from_location_id = $1;
            """, current_location_id)
            return rows
        
    # ... additional methods for other database interactions
async def main():
    # Replace with your actual DSN
    db = Database(dsn="postgresql://postgres:Oshirothegreat9@localhost:5432/BMOSRPG")
    await db.connect()
    # Example usage
    races = await db.fetch_races()
    print(races)
    await db.save_player_choice(discord_id, raceid)
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
    
    

# Use the Database class to connect and run a test query take out 3 quotes to run on each side
'''
try:
    db.connect()  # Use the connect method from your Database class
    # Run a test query
    db.cursor.execute('SELECT 1;')
    # Fetch the result of the query
    result = db.cursor.fetchone()
    # Check if the result is as expected
    if result and result[0] == 1:
        print("Connection to PostgreSQL database successful.")
    else:
        print("Error with the test query.")
    db.close()  # Use the close method from your Database class
except OperationalError as e:
    print("The connection couldn't be established. The error returned was:")
    print(e)
'''