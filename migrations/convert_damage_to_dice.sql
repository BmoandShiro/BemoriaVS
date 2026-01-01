-- Convert existing damage values to dice notation
-- This converts flat damage values to "1dX" format (0-X rolls)

-- Convert weapon damage columns to dice notation
UPDATE items
SET 
    -- Physical damage types
    piercing_dice = CASE 
        WHEN piercing_damage > 0 THEN CONCAT('1d', piercing_damage)
        ELSE NULL
    END,
    crushing_dice = CASE 
        WHEN crushing_damage > 0 THEN CONCAT('1d', crushing_damage)
        ELSE NULL
    END,
    slashing_dice = CASE 
        WHEN slashing_damage > 0 THEN CONCAT('1d', slashing_damage)
        ELSE NULL
    END,
    -- Magic damage types (all scale with Intelligence)
    fire_dice = CASE 
        WHEN fire_damage > 0 THEN CONCAT('1d', fire_damage)
        ELSE NULL
    END,
    ice_dice = CASE 
        WHEN ice_damage > 0 THEN CONCAT('1d', ice_damage)
        ELSE NULL
    END,
    lightning_dice = CASE 
        WHEN lightning_damage > 0 THEN CONCAT('1d', lightning_damage)
        ELSE NULL
    END,
    water_dice = CASE 
        WHEN water_damage > 0 THEN CONCAT('1d', water_damage)
        ELSE NULL
    END,
    earth_dice = CASE 
        WHEN earth_damage > 0 THEN CONCAT('1d', earth_damage)
        ELSE NULL
    END,
    air_dice = CASE 
        WHEN air_damage > 0 THEN CONCAT('1d', air_damage)
        ELSE NULL
    END,
    light_dice = CASE 
        WHEN light_damage > 0 THEN CONCAT('1d', light_damage)
        ELSE NULL
    END,
    dark_dice = CASE 
        WHEN dark_damage > 0 THEN CONCAT('1d', dark_damage)
        ELSE NULL
    END,
    magic_dice = CASE 
        WHEN magic_damage > 0 THEN CONCAT('1d', magic_damage)
        ELSE NULL
    END,
    poison_dice = CASE 
        WHEN poison_damage > 0 THEN CONCAT('1d', poison_damage)
        ELSE NULL
    END
WHERE type = 'Weapon';

-- Convert ability damage columns to dice notation
-- Note: Abilities may not have all physical damage columns, so we only update what exists
UPDATE abilities
SET 
    -- Magic damage types (all scale with Intelligence)
    fire_dice = CASE 
        WHEN fire_damage > 0 THEN CONCAT('1d', fire_damage)
        ELSE NULL
    END,
    ice_dice = CASE 
        WHEN ice_damage > 0 THEN CONCAT('1d', ice_damage)
        ELSE NULL
    END,
    lightning_dice = CASE 
        WHEN lightning_damage > 0 THEN CONCAT('1d', lightning_damage)
        ELSE NULL
    END,
    water_dice = CASE 
        WHEN water_damage > 0 THEN CONCAT('1d', water_damage)
        ELSE NULL
    END,
    earth_dice = CASE 
        WHEN earth_damage > 0 THEN CONCAT('1d', earth_damage)
        ELSE NULL
    END,
    air_dice = CASE 
        WHEN air_damage > 0 THEN CONCAT('1d', air_damage)
        ELSE NULL
    END,
    light_dice = CASE 
        WHEN light_damage > 0 THEN CONCAT('1d', light_damage)
        ELSE NULL
    END,
    dark_dice = CASE 
        WHEN dark_damage > 0 THEN CONCAT('1d', dark_damage)
        ELSE NULL
    END,
    magic_dice = CASE 
        WHEN magic_damage > 0 THEN CONCAT('1d', magic_damage)
        ELSE NULL
    END,
    poison_dice = CASE 
        WHEN poison_damage > 0 THEN CONCAT('1d', poison_damage)
        ELSE NULL
    END;

-- Note: This converts flat damage values to dice notation
-- Example: slashing_damage = 6 becomes slashing_dice = '1d6' (rolls 0-6)
-- Example: fire_damage = 3 becomes fire_dice = '1d3' (rolls 0-3)

