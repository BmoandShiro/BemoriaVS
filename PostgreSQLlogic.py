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
            raceid
)
    async def save_player_choice(self, discord_id, raceid):
        async with self.pool.acquire() as conn:
            # Check if the player exists
            player_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM players WHERE discord_id = $1)",
                discord_id
            )
        
            # If the player doesn't exist, insert them into the players table
            if not player_exists:
                await conn.execute(
                    "INSERT INTO players (discord_id) VALUES ($1)",
                    discord_id
                )
        
            # Update or insert the player's race selection
            await conn.execute(
                """
                INSERT INTO player_data (discord_id, raceid) VALUES ($1, $2)
                ON CONFLICT (discord_id) DO UPDATE SET raceid = EXCLUDED.raceid
                """,
                discord_id, raceid
            )


            
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
                player_id = await conn.fetchval(
                    "INSERT INTO players (discord_id) VALUES ($1) RETURNING playerid",
                    discord_id
                )
                return player_id    

    # ... additional methods for other database interactions
async def main():
    # Replace with your actual DSN
    db = Database(dsn="postgresql://postgres:Oshirothegreat9@localhost:5432/BMOSRPG")
    await db.connect()
    # Example usage
    races = await db.fetch_races()
    print(races)
    await db.save_player_choice(discord_id, race_id)
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