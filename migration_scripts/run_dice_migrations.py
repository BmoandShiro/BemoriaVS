import asyncio
import asyncpg
import os
import sys
from dotenv import load_dotenv

load_dotenv()

async def run_migration_file(filename):
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
        # Read and execute migration
        with open(filename, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        print(f"Running migration: {filename}")
        print("-" * 50)
        
        # Execute the migration
        await conn.execute(migration_sql)
        
        print(f"[SUCCESS] Migration '{filename}' completed successfully!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error running migration '{filename}': {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

async def main():
    migrations = [
        'migrations/add_dice_columns.sql',
        'migrations/convert_damage_to_dice.sql'
    ]
    
    print("=" * 50)
    print("Running Dice System Migrations")
    print("=" * 50)
    print()
    
    for migration in migrations:
        success = await run_migration_file(migration)
        if not success:
            print(f"\n[ERROR] Migration failed! Stopping.")
            sys.exit(1)
        print()
    
    print("=" * 50)
    print("[SUCCESS] All migrations completed successfully!")
    print("=" * 50)
    print("\nDice system is now active!")
    print("  - Added dice columns to items and abilities tables")
    print("  - Converted existing damage values to dice notation")
    print("  - Weapons will now use dice rolls + stat multipliers")

if __name__ == "__main__":
    asyncio.run(main())

