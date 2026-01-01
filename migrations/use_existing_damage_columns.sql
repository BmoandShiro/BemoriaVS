-- Convert existing damage columns to store dice notation instead of integers
-- This reuses the existing columns instead of creating new _dice columns

-- First, convert the existing damage columns from INTEGER to VARCHAR
-- We'll preserve the data by converting it to dice notation first

-- For items table
ALTER TABLE items
ALTER COLUMN piercing_damage TYPE VARCHAR(10) USING 
    CASE 
        WHEN piercing_damage::text IS NOT NULL AND piercing_damage > 0 
        THEN CONCAT('1d', piercing_damage::text)
        ELSE NULL
    END,
ALTER COLUMN crushing_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN crushing_damage::text IS NOT NULL AND crushing_damage > 0 
        THEN CONCAT('1d', crushing_damage::text)
        ELSE NULL
    END,
ALTER COLUMN slashing_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN slashing_damage::text IS NOT NULL AND slashing_damage > 0 
        THEN CONCAT('1d', slashing_damage::text)
        ELSE NULL
    END,
ALTER COLUMN fire_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN fire_damage::text IS NOT NULL AND fire_damage > 0 
        THEN CONCAT('1d', fire_damage::text)
        ELSE NULL
    END,
ALTER COLUMN ice_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN ice_damage::text IS NOT NULL AND ice_damage > 0 
        THEN CONCAT('1d', ice_damage::text)
        ELSE NULL
    END,
ALTER COLUMN lightning_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN lightning_damage::text IS NOT NULL AND lightning_damage > 0 
        THEN CONCAT('1d', lightning_damage::text)
        ELSE NULL
    END,
ALTER COLUMN water_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN water_damage::text IS NOT NULL AND water_damage > 0 
        THEN CONCAT('1d', water_damage::text)
        ELSE NULL
    END,
ALTER COLUMN earth_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN earth_damage::text IS NOT NULL AND earth_damage > 0 
        THEN CONCAT('1d', earth_damage::text)
        ELSE NULL
    END,
ALTER COLUMN air_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN air_damage::text IS NOT NULL AND air_damage > 0 
        THEN CONCAT('1d', air_damage::text)
        ELSE NULL
    END,
ALTER COLUMN light_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN light_damage::text IS NOT NULL AND light_damage > 0 
        THEN CONCAT('1d', light_damage::text)
        ELSE NULL
    END,
ALTER COLUMN dark_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN dark_damage::text IS NOT NULL AND dark_damage > 0 
        THEN CONCAT('1d', dark_damage::text)
        ELSE NULL
    END,
ALTER COLUMN magic_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN magic_damage::text IS NOT NULL AND magic_damage > 0 
        THEN CONCAT('1d', magic_damage::text)
        ELSE NULL
    END,
ALTER COLUMN poison_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN poison_damage::text IS NOT NULL AND poison_damage > 0 
        THEN CONCAT('1d', poison_damage::text)
        ELSE NULL
    END;

-- If we already have _dice columns with data, copy them to _damage columns
UPDATE items
SET 
    piercing_damage = COALESCE(piercing_dice, piercing_damage),
    crushing_damage = COALESCE(crushing_dice, crushing_damage),
    slashing_damage = COALESCE(slashing_dice, slashing_damage),
    fire_damage = COALESCE(fire_dice, fire_damage),
    ice_damage = COALESCE(ice_dice, ice_damage),
    lightning_damage = COALESCE(lightning_dice, lightning_damage),
    water_damage = COALESCE(water_dice, water_damage),
    earth_damage = COALESCE(earth_dice, earth_damage),
    air_damage = COALESCE(air_dice, air_damage),
    light_damage = COALESCE(light_dice, light_damage),
    dark_damage = COALESCE(dark_dice, dark_damage),
    magic_damage = COALESCE(magic_dice, magic_damage),
    poison_damage = COALESCE(poison_dice, poison_damage)
WHERE EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'items' AND column_name = 'piercing_dice');

-- Drop the _dice columns we created (they're no longer needed)
ALTER TABLE items
DROP COLUMN IF EXISTS piercing_dice,
DROP COLUMN IF EXISTS crushing_dice,
DROP COLUMN IF EXISTS slashing_dice,
DROP COLUMN IF EXISTS fire_dice,
DROP COLUMN IF EXISTS ice_dice,
DROP COLUMN IF EXISTS lightning_dice,
DROP COLUMN IF EXISTS water_dice,
DROP COLUMN IF EXISTS earth_dice,
DROP COLUMN IF EXISTS air_dice,
DROP COLUMN IF EXISTS light_dice,
DROP COLUMN IF EXISTS dark_dice,
DROP COLUMN IF EXISTS magic_dice,
DROP COLUMN IF EXISTS poison_dice;

-- For abilities table (only magic damage types)
ALTER TABLE abilities
ALTER COLUMN fire_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN fire_damage::text IS NOT NULL AND fire_damage > 0 
        THEN CONCAT('1d', fire_damage::text)
        ELSE NULL
    END,
ALTER COLUMN ice_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN ice_damage::text IS NOT NULL AND ice_damage > 0 
        THEN CONCAT('1d', ice_damage::text)
        ELSE NULL
    END,
ALTER COLUMN lightning_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN lightning_damage::text IS NOT NULL AND lightning_damage > 0 
        THEN CONCAT('1d', lightning_damage::text)
        ELSE NULL
    END,
ALTER COLUMN water_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN water_damage::text IS NOT NULL AND water_damage > 0 
        THEN CONCAT('1d', water_damage::text)
        ELSE NULL
    END,
ALTER COLUMN earth_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN earth_damage::text IS NOT NULL AND earth_damage > 0 
        THEN CONCAT('1d', earth_damage::text)
        ELSE NULL
    END,
ALTER COLUMN air_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN air_damage::text IS NOT NULL AND air_damage > 0 
        THEN CONCAT('1d', air_damage::text)
        ELSE NULL
    END,
ALTER COLUMN light_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN light_damage::text IS NOT NULL AND light_damage > 0 
        THEN CONCAT('1d', light_damage::text)
        ELSE NULL
    END,
ALTER COLUMN dark_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN dark_damage::text IS NOT NULL AND dark_damage > 0 
        THEN CONCAT('1d', dark_damage::text)
        ELSE NULL
    END,
ALTER COLUMN magic_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN magic_damage::text IS NOT NULL AND magic_damage > 0 
        THEN CONCAT('1d', magic_damage::text)
        ELSE NULL
    END,
ALTER COLUMN poison_damage TYPE VARCHAR(10) USING
    CASE 
        WHEN poison_damage::text IS NOT NULL AND poison_damage > 0 
        THEN CONCAT('1d', poison_damage::text)
        ELSE NULL
    END;

-- Copy from _dice columns if they exist
UPDATE abilities
SET 
    fire_damage = COALESCE(fire_dice, fire_damage),
    ice_damage = COALESCE(ice_dice, ice_damage),
    lightning_damage = COALESCE(lightning_dice, lightning_damage),
    water_damage = COALESCE(water_dice, water_damage),
    earth_damage = COALESCE(earth_dice, earth_damage),
    air_damage = COALESCE(air_dice, air_damage),
    light_damage = COALESCE(light_dice, light_damage),
    dark_damage = COALESCE(dark_dice, dark_damage),
    magic_damage = COALESCE(magic_dice, magic_damage),
    poison_damage = COALESCE(poison_dice, poison_damage)
WHERE EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'abilities' AND column_name = 'fire_dice');

-- Drop the _dice columns from abilities
ALTER TABLE abilities
DROP COLUMN IF EXISTS fire_dice,
DROP COLUMN IF EXISTS ice_dice,
DROP COLUMN IF EXISTS lightning_dice,
DROP COLUMN IF EXISTS water_dice,
DROP COLUMN IF EXISTS earth_dice,
DROP COLUMN IF EXISTS air_dice,
DROP COLUMN IF EXISTS light_dice,
DROP COLUMN IF EXISTS dark_dice,
DROP COLUMN IF EXISTS magic_dice,
DROP COLUMN IF EXISTS poison_dice,
DROP COLUMN IF EXISTS piercing_dice,
DROP COLUMN IF EXISTS crushing_dice,
DROP COLUMN IF EXISTS slashing_dice;

