import psycopg2
import select
import json
import asyncio
from interactions import Extension, Embed, listen
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
import os
from dotenv import load_dotenv

# Setup logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Logs to console
    ]
)

import os
from dotenv import load_dotenv

load_dotenv()

# Configurations loaded from environment variables
DATABASE_CONFIG = {
    "dbname": os.getenv('DB_NAME', 'BMOSRPG'),
    "user": os.getenv('DB_USER', 'postgres'),
    "password": os.getenv('DB_PASSWORD'),
    "host": os.getenv('DB_HOST', 'localhost'),
    "port": os.getenv('DB_PORT', '5432')
}

if not DATABASE_CONFIG["password"]:
    raise ValueError("DB_PASSWORD environment variable is not set")

class ListenerExtension(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.executor = ThreadPoolExecutor(max_workers=1)  # ThreadPool to run blocking listener code
        self.loop = asyncio.get_event_loop()

    @listen()
    async def on_startup(self, event):
        await asyncio.sleep(1)  # Delay to ensure bot is fully ready
        # Run the listener in a background thread to prevent blocking the event loop
        self.loop.run_in_executor(self.executor, self.listen_for_notifications)

    # Function to send notification to a player through Discord
    async def send_discord_notification(self, player_id, quest_id, status, progress):
        try:
            # Step 1: Get the Discord ID from the players table using player_id
            logging.info(f"[STEP 1] Fetching Discord user ID for player ID: {player_id}")
            query = """
                SELECT discord_id FROM players
                WHERE playerid = %s
            """
            discord_id_result = await self.bot.db.fetch_one(query, (player_id,))

            if discord_id_result is None:
                logging.error(f"[STEP 1] No Discord user found for player ID {player_id}. Aborting notification.")
                return

            discord_id = discord_id_result['discord_id']
            logging.info(f"[STEP 1] Discord user ID for player ID {player_id}: {discord_id}")
        
        except Exception as e:
            logging.error(f"[ERROR] Error fetching Discord user ID from the database for player ID {player_id}: {e}")
            return

        # Step 2: Fetch the Discord user by discord_id
        try:
            logging.info(f"[STEP 2] Fetching Discord user for discord ID: {discord_id}")
            user = await self.bot.fetch_user(discord_id)
            if user is None:
                logging.error(f"[STEP 2] No Discord user found for discord ID {discord_id}. Aborting notification.")
                return
            logging.info(f"[STEP 2] Successfully fetched Discord user for discord ID: {discord_id}")
        
        except Exception as e:
            logging.error(f"[ERROR] Error fetching Discord user for discord ID {discord_id}: {e}")
            return

        # Step 3: Prepare the notification embed message
        try:
            title, color, description = "", 0, ""
            if status == "in_progress":
                title = "New Quest Acquired!"
                color = 0xFFD700  # Gold color for quest acquired
                description = "Dave Fishery\nDave has heard tales of legendary fish from his days as an angler, but he can no longer fish himself."
            elif status == "completed":
                title = "Quest Completed!"
                color = 0x00FF00  # Green color for quest completed
                description = f"Quest ID: {quest_id} has been completed!"
            else:
                title = "Quest Progress Updated!"
                color = 0x00BFFF  # Blue color for quest progress update
                description = f"Progress: {progress}"

            logging.info(f"[STEP 3] Preparing embed message for user {discord_id} regarding quest ID {quest_id}")

            embed = Embed(
                title=title,
                description=description,
                color=color
            )

            # Set footer to have similar effect to the screenshot with a yellow line
            embed.set_footer(text="Dave Fishery", icon_url="https://path/to/icon.png")  # Adjust the icon URL as necessary
        
        except Exception as e:
            logging.error(f"[ERROR] Error preparing the embed for player ID {player_id}: {e}")
            return

        # Step 4: Send the embed notification to the user
        try:
            logging.info(f"[STEP 4] Sending embed notification to user {discord_id} for quest ID {quest_id}")
            await user.send(embeds=[embed])
            logging.info(f"[SUCCESS] Notification successfully sent to player ID {player_id} with discord ID {discord_id}")
        
        except Exception as e:
            logging.error(f"[ERROR] Error sending embed to player ID {player_id} with discord ID {discord_id}: {e}")

    # Listener function to wait for PostgreSQL notifications (blocking code)
    def listen_for_notifications(self):
        try:
            conn = psycopg2.connect(**DATABASE_CONFIG)
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            # Listening on the 'quest_update' channel
            cursor.execute("LISTEN quest_update;")
            print("Waiting for notifications on channel 'quest_update'...")

            while True:
                select.select([conn], [], [])
                conn.poll()
                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    data = json.loads(notify.payload)

                    # Debug print to verify notification data
                    print(f"Received notification: {data}")

                    # Extract data from the payload
                    player_id = data.get('player_id')
                    quest_id = data.get('quest_id')
                    status = data.get('status')
                    progress = data.get('progress')

                    # Use asyncio to run the notification in the main event loop
                    self.loop.call_soon_threadsafe(
                        asyncio.create_task,
                        self.send_discord_notification(player_id, quest_id, status, progress)
                    )
        except Exception as e:
            logging.error(f"[ERROR] Listener encountered an error: {e}")
            traceback.print_exc()

# Setup function to be called by the bot to load the extension
def setup(bot):
    ListenerExtension(bot)
