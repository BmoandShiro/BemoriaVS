
-- Add armor column if it doesn't exist
ALTER TABLE items ADD COLUMN IF NOT EXISTS armor INTEGER DEFAULT 0;

-- Update armor values for Bronze Armor (IDs 1-5)
UPDATE items SET armor = CASE
    WHEN itemid = 1 THEN 3  -- Bronze Helmet
    WHEN itemid = 2 THEN 7  -- Bronze Chestplate
    WHEN itemid = 3 THEN 2  -- Bronze Gauntlets
    WHEN itemid = 4 THEN 5  -- Bronze Leggings
    WHEN itemid = 5 THEN 2  -- Bronze Boots
END WHERE itemid BETWEEN 1 AND 5;

-- Update armor values for Iron Armor (IDs 6-10)
UPDATE items SET armor = CASE
    WHEN itemid = 6 THEN 5   -- Iron Helmet
    WHEN itemid = 7 THEN 10  -- Iron Chestplate
    WHEN itemid = 8 THEN 3   -- Iron Gauntlets
    WHEN itemid = 9 THEN 7   -- Iron Leggings
    WHEN itemid = 10 THEN 3  -- Iron Boots
END WHERE itemid BETWEEN 6 AND 10;

-- Update armor values for Steel Armor (IDs 11-15)
UPDATE items SET armor = CASE
    WHEN itemid = 11 THEN 7   -- Steel Helmet
    WHEN itemid = 12 THEN 13  -- Steel Chestplate
    WHEN itemid = 13 THEN 4   -- Steel Gauntlets
    WHEN itemid = 14 THEN 9   -- Steel Leggings
    WHEN itemid = 15 THEN 4   -- Steel Boots
END WHERE itemid BETWEEN 11 AND 15; 