"""
Setup script for Goblin Camp location and Goblin Amulet item.
This script:
1. Creates the Goblin Amulet item (can be equipped in neck or left_hand slot)
2. Creates the Goblin Camp location
3. Creates paths between Dank Caverns and Goblin Camp (bidirectional)
4. Sets Goblin Camp to require Goblin Amulet to be EQUIPPED
5. Adds Goblin Amulet as a drop from all goblin enemies
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def setup_goblin_camp():
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
        # Step 1: Add required_item_equipped column to locations if it doesn't exist
        print("Step 1: Checking for required_item_equipped column...")
        column_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'locations' AND column_name = 'required_item_equipped'
            )
        """)
        
        if not column_exists:
            await conn.execute("""
                ALTER TABLE locations 
                ADD COLUMN required_item_equipped BOOLEAN DEFAULT FALSE
            """)
            print("[SUCCESS] Added required_item_equipped column to locations table")
        else:
            print("[INFO] required_item_equipped column already exists")
        
        # Step 2: Find Dank Caverns location
        print("\nStep 2: Finding Dank Caverns location...")
        dank_caverns_id = await conn.fetchval("""
            SELECT locationid FROM locations WHERE name = 'Dank Caverns'
        """)
        
        if not dank_caverns_id:
            print("Error: Dank Caverns location not found")
            return False
        
        print(f"[SUCCESS] Found Dank Caverns: ID {dank_caverns_id}")
        
        # Step 3: Create Goblin Amulet item
        print("\nStep 3: Creating Goblin Amulet item...")
        # Get next available item ID
        max_item_id = await conn.fetchval("SELECT MAX(itemid) FROM items")
        goblin_amulet_id = (max_item_id or 0) + 1
        
        # Check if item already exists
        existing_item = await conn.fetchval("""
            SELECT itemid FROM items WHERE name = 'Goblin Amulet'
        """)
        
        if existing_item:
            goblin_amulet_id = existing_item
            print(f"[INFO] Goblin Amulet already exists: ID {goblin_amulet_id}")
        else:
            await conn.execute("""
                INSERT INTO items (itemid, name, description, type)
                VALUES ($1, 'Goblin Amulet', 'A mystical amulet that allows passage into Goblin territory. Can be equipped in neck slot or off hand.', 'Neck')
            """, goblin_amulet_id)
            print(f"[SUCCESS] Created Goblin Amulet: ID {goblin_amulet_id}")
        
        # Step 4: Create Goblin Camp location
        print("\nStep 4: Creating Goblin Camp location...")
        max_location_id = await conn.fetchval("SELECT MAX(locationid) FROM locations")
        goblin_camp_id = (max_location_id or 0) + 1
        
        # Check if location already exists
        existing_location = await conn.fetchval("""
            SELECT locationid FROM locations WHERE name = 'Goblin Camp'
        """)
        
        if existing_location:
            goblin_camp_id = existing_location
            # Update to require equipped amulet
            await conn.execute("""
                UPDATE locations
                SET required_item_id = $1, required_item_equipped = TRUE
                WHERE locationid = $2
            """, goblin_amulet_id, goblin_camp_id)
            print(f"[SUCCESS] Goblin Camp already exists: ID {goblin_camp_id}")
            print("[SUCCESS] Updated to require equipped Goblin Amulet")
        else:
            await conn.execute("""
                INSERT INTO locations (locationid, name, description, required_item_id, required_item_equipped)
                VALUES ($1, 'Goblin Camp', 'A hidden camp deep within the goblin territory. Only those bearing the Goblin Amulet may enter.', $2, TRUE)
            """, goblin_camp_id, goblin_amulet_id)
            print(f"[SUCCESS] Created Goblin Camp location: ID {goblin_camp_id}")
        
        # Step 5: Create paths (bidirectional)
        print("\nStep 5: Creating paths between Dank Caverns and Goblin Camp...")
        
        # Path from Dank Caverns to Goblin Camp
        path_exists = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM paths 
                WHERE from_location_id = $1 AND to_location_id = $2
            )
        """, dank_caverns_id, goblin_camp_id)
        
        if not path_exists:
            try:
                await conn.execute("""
                    INSERT INTO paths (from_location_id, to_location_id)
                    VALUES ($1, $2)
                """, dank_caverns_id, goblin_camp_id)
                print("[SUCCESS] Created path from Dank Caverns to Goblin Camp")
            except Exception as e:
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    print("[INFO] Path from Dank Caverns to Goblin Camp already exists")
                else:
                    raise
        else:
            print("[INFO] Path from Dank Caverns to Goblin Camp already exists")
        
        # Return path from Goblin Camp to Dank Caverns
        return_path_exists = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM paths 
                WHERE from_location_id = $1 AND to_location_id = $2
            )
        """, goblin_camp_id, dank_caverns_id)
        
        if not return_path_exists:
            try:
                await conn.execute("""
                    INSERT INTO paths (from_location_id, to_location_id)
                    VALUES ($1, $2)
                """, goblin_camp_id, dank_caverns_id)
                print("[SUCCESS] Created return path from Goblin Camp to Dank Caverns")
            except Exception as e:
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    print("[INFO] Return path from Goblin Camp to Dank Caverns already exists")
                else:
                    raise
        else:
            print("[INFO] Return path from Goblin Camp to Dank Caverns already exists")
        
        # Step 6: Add Goblin Amulet as drop from all goblin enemies
        print("\nStep 6: Adding Goblin Amulet as drop from goblin enemies...")
        
        # Find all goblin enemies (name contains "goblin" case-insensitive)
        goblin_enemies = await conn.fetch("""
            SELECT DISTINCT enemyid, name
            FROM enemies
            WHERE name ILIKE '%goblin%'
        """)
        
        if not goblin_enemies:
            print("[WARNING] No goblin enemies found")
        else:
            print(f"Found {len(goblin_enemies)} goblin enemy type(s):")
            loot_added = 0
            
            for enemy in goblin_enemies:
                # Check if loot entry already exists (cast itemid to match table type)
                loot_exists = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM enemyloot
                        WHERE enemyid = $1 AND itemid::text = $2::text
                    )
                """, enemy['enemyid'], str(goblin_amulet_id))
                
                if not loot_exists:
                    # Random drop rate - let's use 2% (2.0)
                    await conn.execute("""
                        INSERT INTO enemyloot (enemyid, itemid, droprate, quantity)
                        VALUES ($1, $2::integer, 2.0, 1)
                    """, enemy['enemyid'], goblin_amulet_id)
                    print(f"  [OK] Added amulet loot to: {enemy['name']} (ID: {enemy['enemyid']})")
                    loot_added += 1
                else:
                    # Update existing entry
                    await conn.execute("""
                        UPDATE enemyloot
                        SET droprate = 2.0, quantity = 1
                        WHERE enemyid = $1 AND itemid::text = $2::text
                    """, enemy['enemyid'], str(goblin_amulet_id))
                    print(f"  [OK] Updated amulet loot for: {enemy['name']} (ID: {enemy['enemyid']})")
                    loot_added += 1
            
            print(f"\n[SUCCESS] Added/updated Goblin Amulet loot for {loot_added} goblin enemy type(s)")
            print("  - Drop rate: 2%")
            print("  - Quantity: 1")
        
        print("\n" + "=" * 50)
        print("[SUCCESS] Goblin Camp setup complete!")
        print("=" * 50)
        print(f"  - Item: Goblin Amulet (ID: {goblin_amulet_id})")
        print(f"  - Location: Goblin Camp (ID: {goblin_camp_id})")
        print(f"  - Required: Goblin Amulet must be EQUIPPED")
        print(f"  - Accessible from: Dank Caverns (ID: {dank_caverns_id})")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"[ERROR] Error setting up Goblin Camp: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(setup_goblin_camp())

