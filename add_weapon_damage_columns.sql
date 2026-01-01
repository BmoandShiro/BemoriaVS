-- Add slashing_damage column to items table if it doesn't exist
ALTER TABLE items
ADD COLUMN IF NOT EXISTS slashing_damage INTEGER DEFAULT 0;

-- Update iron weapons with their damage values
-- Format: Slashing / Piercing / Crushing

-- Iron Dagger (itemid: 79)
-- 1 / 3 / 0
UPDATE items
SET slashing_damage = 1, piercing_damage = 3, crushing_damage = 0
WHERE itemid = 79 AND name = 'Iron Dagger';

-- Iron Battle Axe (itemid: 80)
-- 4 / 1 / 2
UPDATE items
SET slashing_damage = 4, piercing_damage = 1, crushing_damage = 2
WHERE itemid = 80 AND name = 'Iron Battle Axe';

-- Iron Hatchet (itemid: 81)
-- 3 / 1 / 1
UPDATE items
SET slashing_damage = 3, piercing_damage = 1, crushing_damage = 1
WHERE itemid = 81 AND name = 'Iron Hatchet';

-- Iron Short Sword (itemid: 82)
-- 2 / 2 / 0
UPDATE items
SET slashing_damage = 2, piercing_damage = 2, crushing_damage = 0
WHERE itemid = 82 AND name = 'Iron Short Sword';

-- Iron Long Sword (itemid: 83)
-- 3 / 2 / 0
UPDATE items
SET slashing_damage = 3, piercing_damage = 2, crushing_damage = 0
WHERE itemid = 83 AND name = 'Iron Long Sword';

-- Iron Greatsword (itemid: 84)
-- 4 / 1 / 2
UPDATE items
SET slashing_damage = 4, piercing_damage = 1, crushing_damage = 2
WHERE itemid = 84 AND name = 'Iron Greatsword';

-- Iron Polearm (itemid: 85)
-- 2 / 3 / 1
UPDATE items
SET slashing_damage = 2, piercing_damage = 3, crushing_damage = 1
WHERE itemid = 85 AND name = 'Iron Polearm';

-- Iron Spear (itemid: 86)
-- 1 / 4 / 0
UPDATE items
SET slashing_damage = 1, piercing_damage = 4, crushing_damage = 0
WHERE itemid = 86 AND name = 'Iron Spear';

