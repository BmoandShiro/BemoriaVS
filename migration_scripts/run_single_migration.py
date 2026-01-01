"""
Generic migration runner - can run any SQL migration file from the migrations folder.

Usage:
    python migration_scripts/run_single_migration.py migrations/filename.sql
    python migration_scripts/run_single_migration.py filename.sql (will look in migrations/)
"""
import asyncio
import asyncpg
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

async def run_migration_file(migration_path):
    """Run a single migration file."""
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
        # Handle path - if it doesn't start with migrations/, add it
        if not migration_path.startswith('migrations/'):
            migration_path = f'migrations/{migration_path}'
        
        # Check if file exists
        if not os.path.exists(migration_path):
            print(f"Error: Migration file not found: {migration_path}")
            return False
        
        # Read and execute migration
        with open(migration_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        print(f"Running migration: {migration_path}")
        print("-" * 50)
        
        # Execute the migration
        await conn.execute(migration_sql)
        
        print(f"[SUCCESS] Migration '{migration_path}' completed successfully!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error running migration '{migration_path}': {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python migration_scripts/run_single_migration.py <migration_file>")
        print("Example: python migration_scripts/run_single_migration.py add_dice_columns.sql")
        print("         python migration_scripts/run_single_migration.py migrations/add_dice_columns.sql")
        sys.exit(1)
    
    migration_file = sys.argv[1]
    success = await run_migration_file(migration_file)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

