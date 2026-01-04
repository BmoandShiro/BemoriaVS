"""
Update food items to have type 'Consumable'.
This makes it easier to add future consumables like potions.
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def set_food_to_consumable():
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
        print("Updating food items to type 'Consumable'...")
        
        food_items = ['Chips', 'Smoked Fish Fillet', 'Fish and Chips', 'Fishball Stew']
        
        updated_count = 0
        for food_name in food_items:
            result = await conn.execute("""
                UPDATE items
                SET type = 'Consumable'
                WHERE name = $1
            """, food_name)
            
            # Check if any rows were updated
            if 'UPDATE' in result and int(result.split()[-1]) > 0:
                print(f"  [OK] Updated {food_name} to type 'Consumable'")
                updated_count += 1
            else:
                # Check if item exists
                exists = await conn.fetchval("""
                    SELECT EXISTS(SELECT 1 FROM items WHERE name = $1)
                """, food_name)
                if exists:
                    print(f"  [INFO] {food_name} already has type 'Consumable'")
                else:
                    print(f"  [WARNING] {food_name} not found in items table")
        
        print("\n" + "=" * 50)
        print(f"[SUCCESS] Updated {updated_count} food item(s) to type 'Consumable'")
        print("=" * 50)
        print("All food items and future consumables (potions, etc.) will now")
        print("appear in the 'Use Item' menu automatically.")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"[ERROR] Error updating food items: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(set_food_to_consumable())

