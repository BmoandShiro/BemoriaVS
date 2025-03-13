import asyncpg
import asyncio

async def get_schema():
    conn = await asyncpg.connect(
        user='postgres',
        password='Oshirothegreat9!',
        database='BMOSRPG',
        host='localhost',
        port=5432
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