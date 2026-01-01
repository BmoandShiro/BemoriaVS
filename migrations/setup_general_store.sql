-- Add shop_id column to locations if it doesn't exist
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'locations' 
        AND column_name = 'shop_id'
    ) THEN
        ALTER TABLE locations 
        ADD COLUMN shop_id INTEGER REFERENCES shop_config(shop_id);
    END IF;
END $$;

-- Update Merchants Square location to have the general store
UPDATE locations 
SET shop_id = 2
WHERE name = 'Merchants Square';

-- Insert some basic items into the general store
INSERT INTO shop_items (itemid, shop_id, price, quantity, is_player_sold) 
SELECT 
    i.itemid,
    2,
    CASE 
        WHEN i.type = 'tool' THEN 100
        WHEN i.type = 'resource' THEN 50
        WHEN i.type = 'consumable' THEN 25
        ELSE 75
    END as price,
    50 as quantity,
    false as is_player_sold
FROM items i
WHERE i.type IN ('tool', 'resource', 'consumable')
ON CONFLICT (itemid, shop_id, is_player_sold) DO NOTHING;

-- Set up Ingrid's quest
INSERT INTO quests (quest_id, name, description, npc_id, objective)
VALUES (
    DEFAULT,
    'The General Store',
    'Help Ingrid by selling items worth 4500 gold to her store',
    'ingrid',
    '{"type": "sell_to_shop", "shop_id": 2, "target_value": 4500}'
)
ON CONFLICT (quest_id) DO NOTHING;

-- Add shop button to location commands for Merchants Square
INSERT INTO location_commands (locationid, command_name, button_label, custom_id, button_color)
SELECT 
    locationid,
    'shop',
    'Shop',
    'shop',
    'PRIMARY'
FROM locations 
WHERE name = 'Merchants Square'
ON CONFLICT (locationid, command_name) DO NOTHING; 