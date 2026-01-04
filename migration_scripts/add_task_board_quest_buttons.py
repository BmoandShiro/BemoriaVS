"""
Add 3 quest buttons to the Task Board location.
These buttons will be placeholders for now - quest handlers can be added later.
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def add_task_board_buttons():
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
        # Find Task Board location
        task_board_id = await conn.fetchval("""
            SELECT locationid FROM locations WHERE name = 'Task Board'
        """)
        
        if not task_board_id:
            print("Error: Task Board location not found")
            return False
        
        print(f"Found Task Board location: ID {task_board_id}")
        
        # Add 3 quest buttons
        quest_buttons = [
            {
                'command_name': 'quest_1',
                'button_label': 'Quest 1',
                'custom_id': 'task_board_quest_1',
                'button_color': 'PRIMARY'
            },
            {
                'command_name': 'quest_2',
                'button_label': 'Quest 2',
                'custom_id': 'task_board_quest_2',
                'button_color': 'PRIMARY'
            },
            {
                'command_name': 'quest_3',
                'button_label': 'Quest 3',
                'custom_id': 'task_board_quest_3',
                'button_color': 'PRIMARY'
            }
        ]
        
        print("\nAdding quest buttons to Task Board...")
        for button in quest_buttons:
            try:
                await conn.execute("""
                    INSERT INTO location_commands 
                    (locationid, command_name, button_label, custom_id, button_color)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (locationid, command_name) 
                    DO UPDATE SET 
                        button_label = EXCLUDED.button_label,
                        custom_id = EXCLUDED.custom_id,
                        button_color = EXCLUDED.button_color
                """, task_board_id, button['command_name'], button['button_label'], 
                    button['custom_id'], button['button_color'])
                print(f"  [OK] Added/Updated: {button['button_label']} ({button['custom_id']})")
            except Exception as e:
                print(f"  [ERROR] Error adding {button['button_label']}: {e}")
        
        print("\n" + "=" * 50)
        print("[SUCCESS] Task Board quest buttons added!")
        print("=" * 50)
        print(f"  - Location: Task Board (ID: {task_board_id})")
        print(f"  - Buttons: 3 quest buttons added")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"[ERROR] Error adding Task Board buttons: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(add_task_board_buttons())

