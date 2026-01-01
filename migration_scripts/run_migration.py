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
        # Read and execute first migration
        with open('migrations/add_party_combat_turn_system.sql', 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        print("Running migration: add_party_combat_turn_system.sql")
        print("-" * 50)
        
        # Execute the migration
        await conn.execute(migration_sql)
        
        print("Migration 1 completed!")
        
        # Read and execute second migration
        with open('migrations/add_battle_channel_columns.sql', 'r', encoding='utf-8') as f:
            migration_sql2 = f.read()
        
        print("\nRunning migration: add_battle_channel_columns.sql")
        print("-" * 50)
        
        # Execute the migration
        await conn.execute(migration_sql2)
        
        print("Migration 2 completed!")
        print("\nAll migrations completed successfully!")
        print("\nAdded columns to battle_instances table:")
        print("  - current_turn_player_id")
        print("  - turn_order")
        print("  - turn_number")
        print("  - phase")
        print("  - channel_id")
        print("  - message_id")
        print("\nCreated index:")
        print("  - idx_battle_instances_current_turn")
        
    except Exception as e:
        print(f"Error running migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_migration())

