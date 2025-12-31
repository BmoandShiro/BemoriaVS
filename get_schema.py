import asyncpg
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def get_schema():
    # Load database credentials from environment variables
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = int(os.getenv('DB_PORT', '5432'))
    db_name = os.getenv('DB_NAME', 'BMOSRPG')
    
    if not db_password:
        raise ValueError("DB_PASSWORD environment variable is not set")
    
    conn = await asyncpg.connect(
        user=db_user,
        password=db_password,
        database=db_name,
        host=db_host,
        port=db_port
    )
    
    # Get all tables
    tables = await conn.fetch("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    
    print("\nDatabase Tables:")
    for table in tables:
        print(f"\nTable: {table['table_name']}")
        # Get columns for each table
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = $1
        """, table['table_name'])
        
        print("Columns:")
        for col in columns:
            print(f"  - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(get_schema()) 