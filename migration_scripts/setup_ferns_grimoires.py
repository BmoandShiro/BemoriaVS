"""
Setup script for Fern's Grimoires location.
This script:
1. Creates the Player Locatinator grimoire item
2. Creates Fern NPC
3. Creates shop for Fern's Grimoires
4. Adds Player Locatinator to the shop
5. Adds 3 location buttons: Shop (PRIMARY/gold-like), Fern (PRIMARY/blue), Open Player Locatinator (SUCCESS/green)
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def setup_ferns_grimoires():
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
        # Step 1: Find Ferns Grimoires location
        print("Step 1: Finding Ferns Grimoires location...")
        ferns_location_id = await conn.fetchval("""
            SELECT locationid FROM locations WHERE name ILIKE '%ferns grimoires%' OR name ILIKE '%fern%grimoire%'
        """)
        
        if not ferns_location_id:
            print("Error: Ferns Grimoires location not found")
            return False
        
        print(f"[SUCCESS] Found Ferns Grimoires: ID {ferns_location_id}")
        
        # Step 2: Create Player Locatinator item
        print("\nStep 2: Creating Player Locatinator grimoire...")
        max_item_id = await conn.fetchval("SELECT MAX(itemid) FROM items")
        locatinator_id = (max_item_id or 0) + 1
        
        # Check if item already exists
        existing_item = await conn.fetchval("""
            SELECT itemid FROM items WHERE name = 'Player Locatinator'
        """)
        
        if existing_item:
            locatinator_id = existing_item
            print(f"[INFO] Player Locatinator already exists: ID {locatinator_id}")
        else:
            await conn.execute("""
                INSERT INTO items (itemid, name, description, type)
                VALUES ($1, 'Player Locatinator', 'A mystical grimoire that allows you to see the location and status of all players in the server.', 'Grimoire')
            """, locatinator_id)
            print(f"[SUCCESS] Created Player Locatinator: ID {locatinator_id}")
        
        # Step 3: Create Fern NPC
        print("\nStep 3: Creating Fern NPC...")
        # Get next NPC ID
        max_npc_id = await conn.fetchval("SELECT MAX(dynamic_npc_id) FROM dynamic_npcs")
        fern_npc_id = (max_npc_id or 0) + 1
        
        # Check if Fern already exists
        existing_npc = await conn.fetchval("""
            SELECT dynamic_npc_id FROM dynamic_npcs WHERE LOWER(name) = 'fern'
        """)
        
        if existing_npc:
            fern_npc_id = existing_npc
            # Update location if needed
            await conn.execute("""
                UPDATE dynamic_npcs
                SET locationid = $1
                WHERE dynamic_npc_id = $2
            """, ferns_location_id, fern_npc_id)
            print(f"[INFO] Fern NPC already exists: ID {fern_npc_id}")
        else:
            await conn.execute("""
                INSERT INTO dynamic_npcs (dynamic_npc_id, name, description, locationid)
                VALUES ($1, 'Fern', 'A mysterious shopkeeper who deals in magical grimoires and knowledge.', $2)
            """, fern_npc_id, ferns_location_id)
            print(f"[SUCCESS] Created Fern NPC: ID {fern_npc_id}")
        
        # Step 4: Create shop config for Fern's shop
        print("\nStep 4: Creating shop for Fern's Grimoires...")
        # Get next shop ID - check if shop_id is integer or text
        max_shop_id = await conn.fetchval("SELECT MAX(shop_id::text) FROM shop_config")
        if max_shop_id:
            try:
                fern_shop_id = int(max_shop_id) + 1
            except:
                # If it's text, find the highest numeric value
                all_shops = await conn.fetch("SELECT shop_id FROM shop_config")
                numeric_ids = [int(s['shop_id']) for s in all_shops if str(s['shop_id']).isdigit()]
                fern_shop_id = max(numeric_ids) + 1 if numeric_ids else 11
        else:
            fern_shop_id = 11  # Start at 11 since we saw shop_id 10 used
        
        # Check if shop already exists (check by description since shop_id might be text)
        existing_shop = await conn.fetchval("""
            SELECT shop_id FROM shop_config 
            WHERE description IS NOT NULL AND description ILIKE '%fern%'
        """)
        
        if existing_shop:
            fern_shop_id = str(existing_shop)  # Convert to string
            print(f"[INFO] Fern's shop already exists: ID {fern_shop_id}")
        else:
            fern_shop_id = str(fern_shop_id)  # Convert to string
            await conn.execute("""
                INSERT INTO shop_config (shop_id, description)
                VALUES ($1, 'A shop specializing in magical grimoires and mystical knowledge.')
            """, fern_shop_id)
            print(f"[SUCCESS] Created shop: ID {fern_shop_id}")
        
        # Step 5: Link shop to location (shop_id needs to be integer for locations table)
        await conn.execute("""
            UPDATE locations
            SET shop_id = $1::integer
            WHERE locationid = $2
        """, int(fern_shop_id), ferns_location_id)
        print("[SUCCESS] Linked shop to Ferns Grimoires location")
        
        # Step 6: Add Player Locatinator to shop
        print("\nStep 6: Adding Player Locatinator to shop...")
        # Check if already in shop (shop_id might be text or integer)
        shop_item_exists = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM shop_items
                WHERE shop_id::text = $1::text AND itemid = $2 AND is_player_sold = FALSE
            )
        """, fern_shop_id, locatinator_id)
        
        if not shop_item_exists:
            await conn.execute("""
                INSERT INTO shop_items (shop_id, locationid, itemid, price, quantity, is_player_sold)
                VALUES ($1::integer, $2, $3, 5000, 999, FALSE)
            """, int(fern_shop_id), ferns_location_id, locatinator_id)
            print("[SUCCESS] Added Player Locatinator to shop (price: 5000 gold)")
        else:
            # Update price if exists
            await conn.execute("""
                UPDATE shop_items
                SET price = 5000, quantity = 999
                WHERE shop_id::text = $1::text AND itemid = $2 AND is_player_sold = FALSE
            """, fern_shop_id, locatinator_id)
            print("[INFO] Updated Player Locatinator in shop")
        
        # Step 7: Add location commands (buttons)
        print("\nStep 7: Adding location buttons...")
        
        buttons = [
            {
                'command_name': 'shop',
                'button_label': 'Shop',
                'custom_id': 'shop',
                'button_color': 'PRIMARY'  # Using PRIMARY as gold-like (most prominent)
            },
            {
                'command_name': 'talk_to_fern',
                'button_label': 'Fern',
                'custom_id': 'talk_to_fern',
                'button_color': 'PRIMARY'  # Default blue
            },
            {
                'command_name': 'open_player_locatinator',
                'button_label': 'Open Player Locatinator',
                'custom_id': 'open_player_locatinator',
                'button_color': 'SUCCESS'  # Green
            }
        ]
        
        for button in buttons:
            await conn.execute("""
                INSERT INTO location_commands 
                (locationid, command_name, button_label, custom_id, button_color)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (locationid, command_name) 
                DO UPDATE SET 
                    button_label = EXCLUDED.button_label,
                    custom_id = EXCLUDED.custom_id,
                    button_color = EXCLUDED.button_color
            """, ferns_location_id, button['command_name'], button['button_label'], 
                button['custom_id'], button['button_color'])
            print(f"  [OK] Added/Updated: {button['button_label']} ({button['button_color']})")
        
        print("\n" + "=" * 50)
        print("[SUCCESS] Fern's Grimoires setup complete!")
        print("=" * 50)
        print(f"  - Location: Ferns Grimoires (ID: {ferns_location_id})")
        print(f"  - Item: Player Locatinator (ID: {locatinator_id})")
        print(f"  - NPC: Fern (ID: {fern_npc_id})")
        print(f"  - Shop: Fern's Grimoires (ID: {fern_shop_id})")
        print(f"  - Buttons: Shop, Fern, Open Player Locatinator")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"[ERROR] Error setting up Fern's Grimoires: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(setup_ferns_grimoires())

