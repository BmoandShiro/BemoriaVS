import psycopg2
from psycopg2 import OperationalError  # Import the error class

class Database:
    def __init__(self, dsn):
        self.dsn = dsn  # Data Source Name contains all the database parameters

    def connect(self):
        self.connection = psycopg2.connect(self.dsn)
        self.cursor = self.connection.cursor()

    def close(self):
        self.cursor.close()
        self.connection.close()

    def get_player_by_id(self, playerid):
        self.cursor.execute("SELECT * FROM players WHERE id = %s", (playerid,))
        return self.cursor.fetchone()
    
    async def fetch_races(self):
        query = "SELECT id, name, description FROM races"  # Adjust the table and column names as necessary
        try:
            self.cursor.execute(query)
            races = self.cursor.fetchall()
            return [{'id': race[0], 'name': race[1], 'description': race[2]} for race in races]
        except Exception as e:
            print(f"Error fetching races: {e}")
            return []

    # ... additional methods for other database interactions

# Initialize your Database instance with the correct DSN
db = Database(dsn="dbname='BMOSRPG' user='postgres' host='localhost' password='Oshirothegreat9' port='5432'")

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