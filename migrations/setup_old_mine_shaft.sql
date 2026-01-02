-- Setup Old Mine Shaft location and key requirement
-- This script:
-- 1. Creates a path from Dank Caverns to Old Mine Shaft
-- 2. Sets Old Mine Shaft to require the Old Mine Shaft Key (item ID 234)
-- 3. Adds the key as loot to all Dank Caverns enemies with 0.05% drop rate

-- Step 1: Get location IDs (assuming we need to find them)
-- First, let's find Dank Caverns location ID
DO $$
DECLARE
    dank_caverns_id INTEGER;
    old_mine_shaft_id INTEGER;
    enemy_record RECORD;
BEGIN
    -- Get location IDs
    SELECT locationid INTO dank_caverns_id FROM locations WHERE name = 'Dank Caverns';
    SELECT locationid INTO old_mine_shaft_id FROM locations WHERE name = 'Old Mine Shaft';
    
    IF dank_caverns_id IS NULL THEN
        RAISE EXCEPTION 'Dank Caverns location not found';
    END IF;
    
    IF old_mine_shaft_id IS NULL THEN
        RAISE EXCEPTION 'Old Mine Shaft location not found';
    END IF;
    
    -- Step 2: Create path from Dank Caverns to Old Mine Shaft (if it doesn't exist)
    INSERT INTO paths (from_location_id, to_location_id)
    SELECT dank_caverns_id, old_mine_shaft_id
    WHERE NOT EXISTS (
        SELECT 1 FROM paths 
        WHERE from_location_id = dank_caverns_id 
        AND to_location_id = old_mine_shaft_id
    );
    
    -- Step 3: Set Old Mine Shaft to require the key (item ID 234)
    UPDATE locations
    SET required_item_id = 234
    WHERE locationid = old_mine_shaft_id;
    
    -- Step 4: Add Old Mine Shaft Key as loot to all enemies in Dank Caverns
    -- Find all enemies that spawn in Dank Caverns and add the key as loot
    FOR enemy_record IN 
        SELECT DISTINCT e.enemyid
        FROM enemies e
        WHERE e.locationid = dank_caverns_id
    LOOP
        -- Insert loot entry with 0.05% drop rate (0.0005 as decimal)
        INSERT INTO enemyloot (enemyid, itemid, droprate, quantity)
        VALUES (enemy_record.enemyid, 234, 0.0005, 1)
        ON CONFLICT (enemyid, itemid) DO UPDATE
        SET droprate = 0.0005, quantity = 1;
    END LOOP;
    
    RAISE NOTICE 'Setup complete:';
    RAISE NOTICE '  - Path created from Dank Caverns (ID: %) to Old Mine Shaft (ID: %)', dank_caverns_id, old_mine_shaft_id;
    RAISE NOTICE '  - Old Mine Shaft now requires Old Mine Shaft Key (item ID 234)';
    RAISE NOTICE '  - Key added as loot to Dank Caverns enemies with 0.05%% drop rate';
END $$;

