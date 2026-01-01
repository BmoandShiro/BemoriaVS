-- Modify the inventory unique constraint to allow multiple equipped entries of the same item
-- This enables dual-wielding the same weapon type

-- Drop the existing unique constraint
ALTER TABLE inventory DROP CONSTRAINT IF EXISTS unique_player_item;

-- Create a new partial unique constraint that only applies to unequipped items
-- This allows multiple equipped entries of the same item (for dual-wielding)
CREATE UNIQUE INDEX unique_player_item_unequipped 
ON inventory(playerid, itemid) 
WHERE isequipped = false AND (in_bank = false OR in_bank IS NULL);

-- Note: This allows:
-- - Only ONE unequipped entry per (playerid, itemid) in main inventory
-- - Multiple equipped entries of the same item (for dual-wielding)
-- - Items can be equipped in different slots (right hand, left hand, etc.)

