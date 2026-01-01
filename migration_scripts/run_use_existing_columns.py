import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def run_migration():
    # Get database connection string
    dsn = os.getenv('DATABASE_DSN')
    if not dsn:
        print("Error: DATABASE_DSN not found in .env file")
        return
    
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
            return
        
        conn = await asyncpg.connect(
            user=db_user,
            password=db_password,
            database=db_name,
            host=db_host,
            port=db_port
        )
    
    try:
        # Read and execute migration
        with open('migrations/use_existing_damage_columns.sql', 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        print("Converting damage columns to store dice notation...")
        print("-" * 50)
        
        # Execute the migration
        await conn.execute(migration_sql)
        
        print("[SUCCESS] Migration completed!")
        print("  - Converted damage columns from INTEGER to VARCHAR")
        print("  - Existing values converted to dice notation (e.g., 6 -> '1d6')")
        print("  - Dropped temporary _dice columns")
        print("  - Code now uses existing _damage columns for dice notation")
        
    except Exception as e:
        print(f"[ERROR] Error running migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_migration())

