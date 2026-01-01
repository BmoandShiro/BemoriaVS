-- Update all weapon damage values and add smithing requirements
-- Format: itemid, name, slashing, piercing, crushing, dark_damage, bar_type, bars_required, smithing_level

-- Bronze Weapons (itemid 71-78)
UPDATE items SET slashing_damage = 1, piercing_damage = 1, crushing_damage = 0, dark_damage = 0 WHERE itemid = 71 AND name = 'Bronze Dagger';
UPDATE items SET slashing_damage = 2, piercing_damage = 0, crushing_damage = 1, dark_damage = 0 WHERE itemid = 72 AND name = 'Bronze Battle Axe';
UPDATE items SET slashing_damage = 2, piercing_damage = 0, crushing_damage = 1, dark_damage = 0 WHERE itemid = 73 AND name = 'Bronze Hatchet';
UPDATE items SET slashing_damage = 2, piercing_damage = 0, crushing_damage = 0, dark_damage = 0 WHERE itemid = 74 AND name = 'Bronze Short Sword';
UPDATE items SET slashing_damage = 2, piercing_damage = 1, crushing_damage = 0, dark_damage = 0 WHERE itemid = 75 AND name = 'Bronze Long Sword';
UPDATE items SET slashing_damage = 2, piercing_damage = 0, crushing_damage = 1, dark_damage = 0 WHERE itemid = 76 AND name = 'Bronze Greatsword';
UPDATE items SET slashing_damage = 1, piercing_damage = 1, crushing_damage = 1, dark_damage = 0 WHERE itemid = 77 AND name = 'Bronze Polearm';
UPDATE items SET slashing_damage = 0, piercing_damage = 2, crushing_damage = 0, dark_damage = 0 WHERE itemid = 78 AND name = 'Bronze Spear';

-- Iron Weapons (itemid 79-86) - Update from previous values
UPDATE items SET slashing_damage = 1, piercing_damage = 2, crushing_damage = 0, dark_damage = 0 WHERE itemid = 79 AND name = 'Iron Dagger';
UPDATE items SET slashing_damage = 3, piercing_damage = 0, crushing_damage = 2, dark_damage = 0 WHERE itemid = 80 AND name = 'Iron Battle Axe';
UPDATE items SET slashing_damage = 2, piercing_damage = 0, crushing_damage = 2, dark_damage = 0 WHERE itemid = 81 AND name = 'Iron Hatchet';
UPDATE items SET slashing_damage = 3, piercing_damage = 1, crushing_damage = 0, dark_damage = 0 WHERE itemid = 82 AND name = 'Iron Short Sword';
UPDATE items SET slashing_damage = 4, piercing_damage = 1, crushing_damage = 0, dark_damage = 0 WHERE itemid = 83 AND name = 'Iron Long Sword';
UPDATE items SET slashing_damage = 4, piercing_damage = 0, crushing_damage = 2, dark_damage = 0 WHERE itemid = 84 AND name = 'Iron Greatsword';
UPDATE items SET slashing_damage = 2, piercing_damage = 2, crushing_damage = 1, dark_damage = 0 WHERE itemid = 85 AND name = 'Iron Polearm';
UPDATE items SET slashing_damage = 1, piercing_damage = 3, crushing_damage = 0, dark_damage = 0 WHERE itemid = 86 AND name = 'Iron Spear';

-- Steel Weapons (itemid 87-94)
UPDATE items SET slashing_damage = 2, piercing_damage = 4, crushing_damage = 0, dark_damage = 0 WHERE itemid = 87 AND name = 'Steel Dagger';
UPDATE items SET slashing_damage = 5, piercing_damage = 0, crushing_damage = 4, dark_damage = 0 WHERE itemid = 88 AND name = 'Steel Battle Axe';
UPDATE items SET slashing_damage = 4, piercing_damage = 0, crushing_damage = 3, dark_damage = 0 WHERE itemid = 89 AND name = 'Steel Hatchet';
UPDATE items SET slashing_damage = 4, piercing_damage = 2, crushing_damage = 0, dark_damage = 0 WHERE itemid = 90 AND name = 'Steel Short Sword';
UPDATE items SET slashing_damage = 5, piercing_damage = 2, crushing_damage = 0, dark_damage = 0 WHERE itemid = 91 AND name = 'Steel Long Sword';
UPDATE items SET slashing_damage = 6, piercing_damage = 0, crushing_damage = 4, dark_damage = 0 WHERE itemid = 92 AND name = 'Steel Greatsword';
UPDATE items SET slashing_damage = 3, piercing_damage = 4, crushing_damage = 2, dark_damage = 0 WHERE itemid = 93 AND name = 'Steel Polearm';
UPDATE items SET slashing_damage = 2, piercing_damage = 5, crushing_damage = 0, dark_damage = 0 WHERE itemid = 94 AND name = 'Steel Spear';

-- Necrosteel Weapons (itemid 95-102)
UPDATE items SET slashing_damage = 3, piercing_damage = 6, crushing_damage = 0, dark_damage = 5 WHERE itemid = 95 AND name = 'Necrosteel Dagger';
UPDATE items SET slashing_damage = 8, piercing_damage = 0, crushing_damage = 6, dark_damage = 6 WHERE itemid = 96 AND name = 'Necrosteel Battle Axe';
UPDATE items SET slashing_damage = 7, piercing_damage = 0, crushing_damage = 5, dark_damage = 5 WHERE itemid = 97 AND name = 'Necrosteel Hatchet';
UPDATE items SET slashing_damage = 6, piercing_damage = 3, crushing_damage = 0, dark_damage = 5 WHERE itemid = 98 AND name = 'Necrosteel Short Sword';
UPDATE items SET slashing_damage = 7, piercing_damage = 3, crushing_damage = 0, dark_damage = 6 WHERE itemid = 99 AND name = 'Necrosteel Long Sword';
UPDATE items SET slashing_damage = 9, piercing_damage = 0, crushing_damage = 7, dark_damage = 7 WHERE itemid = 100 AND name = 'Necrosteel Greatsword';
UPDATE items SET slashing_damage = 5, piercing_damage = 6, crushing_damage = 4, dark_damage = 6 WHERE itemid = 101 AND name = 'Necrosteel Polearm';
UPDATE items SET slashing_damage = 3, piercing_damage = 8, crushing_damage = 0, dark_damage = 6 WHERE itemid = 102 AND name = 'Necrosteel Spear';

