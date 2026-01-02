"""
Setup script for Old Mine Shaft location.
This script:
1. Creates a path from Dank Caverns to Old Mine Shaft
2. Sets Old Mine Shaft to require the Old Mine Shaft Key (item ID 234)
3. Adds the key as loot to all Dank Caverns enemies with 0.05% drop rate
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def setup_old_mine_shaft():
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
        # Get location IDs
        dank_caverns_id = await conn.fetchval("""
            SELECT locationid FROM locations WHERE name = 'Dank Caverns'
        """)
        
        old_mine_shaft_id = await conn.fetchval("""
            SELECT locationid FROM locations WHERE name = 'Old Mine Shaft'
        """)
        
        if not dank_caverns_id:
            print("Error: Dank Caverns location not found")
            return False
        
        if not old_mine_shaft_id:
            print("Error: Old Mine Shaft location not found")
            return False
        
        print(f"Found locations:")
        print(f"  - Dank Caverns: ID {dank_caverns_id}")
        print(f"  - Old Mine Shaft: ID {old_mine_shaft_id}")
        print()
        
        # Step 1: Create path from Dank Caverns to Old Mine Shaft (if it doesn't exist)
        path_exists = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM paths 
                WHERE from_location_id = $1 AND to_location_id = $2
            )
        """, dank_caverns_id, old_mine_shaft_id)
        
        if not path_exists:
            try:
                await conn.execute("""
                    INSERT INTO paths (from_location_id, to_location_id)
                    VALUES ($1, $2)
                """, dank_caverns_id, old_mine_shaft_id)
                print("[SUCCESS] Created path from Dank Caverns to Old Mine Shaft")
            except Exception as e:
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    print("[INFO] Path from Dank Caverns to Old Mine Shaft already exists")
                else:
                    raise
        else:
            print("[INFO] Path from Dank Caverns to Old Mine Shaft already exists")
        
        # Step 2: Set Old Mine Shaft to require the key (item ID 234)
        await conn.execute("""
            UPDATE locations
            SET required_item_id = 234
            WHERE locationid = $1
        """, old_mine_shaft_id)
        print("[SUCCESS] Set Old Mine Shaft to require Old Mine Shaft Key (item ID 234)")
        
        # Step 3: Get all enemies in Dank Caverns
        enemies = await conn.fetch("""
            SELECT DISTINCT enemyid, name
            FROM enemies
            WHERE locationid = $1
        """, dank_caverns_id)
        
        if not enemies:
            print("[WARNING] No enemies found in Dank Caverns")
        else:
            print(f"\nFound {len(enemies)} enemy type(s) in Dank Caverns:")
            loot_added = 0
            
            for enemy in enemies:
                # Check if loot entry already exists (cast itemid to match table type)
                loot_exists = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM enemyloot
                        WHERE enemyid = $1 AND itemid::text = $2::text
                    )
                """, enemy['enemyid'], '234')
                
                if not loot_exists:
                    await conn.execute("""
                        INSERT INTO enemyloot (enemyid, itemid, droprate, quantity)
                        VALUES ($1, $2::integer, 5.0, 1)
                    """, enemy['enemyid'], 234)
                    print(f"  - Added key loot to: {enemy['name']} (ID: {enemy['enemyid']})")
                    loot_added += 1
                else:
                    # Update existing entry
                    await conn.execute("""
                        UPDATE enemyloot
                        SET droprate = 5.0, quantity = 1
                        WHERE enemyid = $1 AND itemid::text = $2::text
                    """, enemy['enemyid'], '234')
                    print(f"  - Updated key loot for: {enemy['name']} (ID: {enemy['enemyid']})")
                    loot_added += 1
            
            print(f"\n[SUCCESS] Added/updated Old Mine Shaft Key loot for {loot_added} enemy type(s)")
            print("  - Drop rate: 5%")
            print("  - Quantity: 1")
        
        print("\n" + "=" * 50)
        print("[SUCCESS] Old Mine Shaft setup complete!")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"[ERROR] Error setting up Old Mine Shaft: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(setup_old_mine_shaft())

