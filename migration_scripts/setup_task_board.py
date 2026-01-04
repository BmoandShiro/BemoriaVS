"""
Setup script for Task Board location at The Twisted Toad.
This script:
1. Adds required_quest_id column to locations if it doesn't exist
2. Creates the Task Board location
3. Creates a path from The Twisted Toad to Task Board
4. Sets Task Board to require completion of "Build Tavern Task Board" quest
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def setup_task_board():
    # Get database connection string
    dsn = os.getenv('DATABASE_DSN')
    if not dsn:
        print("Error: DATABASE_DSN not found in .env file")
        return False
    
    # Parse DSN or use individual components
    if dsn.startswith('postgresql://'):
        conn = await asyncpg.connect(dsn=dsn)
    else:
        # Fallback to individual components
        db_user = os.getenv('DB_USER', 'postgres')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = int(os.getenv('DB_PORT', '5432'))
        db_name = os.getenv('DB_NAME', 'BMOSRPG')
        
        if not db_password:
            print("Error: DB_PASSWORD not found in .env file")
            return False
        
        conn = await asyncpg.connect(
            user=db_user,
            password=db_password,
            database=db_name,
            host=db_host,
            port=db_port
        )
    
    try:
        # Step 1: Add required_quest_id column if it doesn't exist
        print("Step 1: Checking for required_quest_id column...")
        column_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'locations' AND column_name = 'required_quest_id'
            )
        """)
        
        if not column_exists:
            await conn.execute("""
                ALTER TABLE locations 
                ADD COLUMN required_quest_id INTEGER REFERENCES quests(quest_id)
            """)
            print("[SUCCESS] Added required_quest_id column to locations table")
        else:
            print("[INFO] required_quest_id column already exists")
        
        # Step 2: Find The Twisted Toad location
        print("\nStep 2: Finding The Twisted Toad location...")
        twisted_toad_id = await conn.fetchval("""
            SELECT locationid FROM locations WHERE name ILIKE '%twisted toad%'
        """)
        
        if not twisted_toad_id:
            print("Error: The Twisted Toad location not found")
            return False
        
        print(f"[SUCCESS] Found The Twisted Toad: ID {twisted_toad_id}")
        
        # Step 3: Find the "Build Tavern Task Board" quest
        print("\nStep 3: Finding 'Build Tavern Task Board' quest...")
        quest_id = await conn.fetchval("""
            SELECT quest_id FROM quests WHERE name = 'Build Tavern Task Board'
        """)
        
        if not quest_id:
            print("Error: 'Build Tavern Task Board' quest not found")
            return False
        
        print(f"[SUCCESS] Found quest: ID {quest_id}")
        
        # Step 4: Check if Task Board location already exists
        print("\nStep 4: Checking for Task Board location...")
        task_board_id = await conn.fetchval("""
            SELECT locationid FROM locations WHERE name = 'Task Board'
        """)
        
        if not task_board_id:
            # Get the next location ID
            max_location_id = await conn.fetchval("SELECT MAX(locationid) FROM locations")
            task_board_id = (max_location_id or 0) + 1
            
            # Create Task Board location
            await conn.execute("""
                INSERT INTO locations (locationid, name, description, required_quest_id)
                VALUES ($1, 'Task Board', 'A board displaying available tasks and quests for adventurers.', $2)
            """, task_board_id, quest_id)
            print(f"[SUCCESS] Created Task Board location: ID {task_board_id}")
        else:
            # Update existing location to require the quest
            await conn.execute("""
                UPDATE locations
                SET required_quest_id = $1
                WHERE locationid = $2
            """, quest_id, task_board_id)
            print(f"[SUCCESS] Task Board location already exists: ID {task_board_id}")
            print(f"[SUCCESS] Updated Task Board to require 'Build Tavern Task Board' quest")
        
        # Step 5: Create path from The Twisted Toad to Task Board
        print("\nStep 5: Creating path from The Twisted Toad to Task Board...")
        path_exists = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM paths 
                WHERE from_location_id = $1 AND to_location_id = $2
            )
        """, twisted_toad_id, task_board_id)
        
        if not path_exists:
            try:
                await conn.execute("""
                    INSERT INTO paths (from_location_id, to_location_id)
                    VALUES ($1, $2)
                """, twisted_toad_id, task_board_id)
                print("[SUCCESS] Created path from The Twisted Toad to Task Board")
            except Exception as e:
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    print("[INFO] Path from The Twisted Toad to Task Board already exists")
                else:
                    raise
        else:
            print("[INFO] Path from The Twisted Toad to Task Board already exists")
        
        # Step 6: Create return path from Task Board to The Twisted Toad
        print("\nStep 6: Creating return path from Task Board to The Twisted Toad...")
        return_path_exists = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM paths 
                WHERE from_location_id = $1 AND to_location_id = $2
            )
        """, task_board_id, twisted_toad_id)
        
        if not return_path_exists:
            try:
                await conn.execute("""
                    INSERT INTO paths (from_location_id, to_location_id)
                    VALUES ($1, $2)
                """, task_board_id, twisted_toad_id)
                print("[SUCCESS] Created return path from Task Board to The Twisted Toad")
            except Exception as e:
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    print("[INFO] Return path from Task Board to The Twisted Toad already exists")
                else:
                    raise
        else:
            print("[INFO] Return path from Task Board to The Twisted Toad already exists")
        
        print("\n" + "=" * 50)
        print("[SUCCESS] Task Board setup complete!")
        print("=" * 50)
        print(f"  - Location: Task Board (ID: {task_board_id})")
        print(f"  - Required Quest: Build Tavern Task Board (ID: {quest_id})")
        print(f"  - Accessible from: The Twisted Toad (ID: {twisted_toad_id})")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"[ERROR] Error setting up Task Board: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(setup_task_board())

