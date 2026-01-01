-- Setup shop for Walts Weapons location
-- Location: Walts Weapons (locationid: 11)

-- Create shop config entry for Walt's Weapons Shop (using shop_id '10')
INSERT INTO shop_config (shop_id, description, default_markup_rate, default_sell_rate)
VALUES ('10', 'A weapons shop run by Walt, specializing in bronze and iron weapons', 0.0, 0.75)
ON CONFLICT (shop_id) DO NOTHING;

-- Update location to have shop_id (as integer)
UPDATE locations
SET shop_id = 10
WHERE locationid = 11 AND name = 'Walts Weapons';

-- Clear existing items for this shop/location first
-- Delete any existing entries for this shop
DELETE FROM shop_items WHERE shop_id = 10;

-- Add shop items for Bronze weapons (excluding Greatsword, Battle Axe, Polearm)
-- Bronze Dagger (71) - 600 gold
INSERT INTO shop_items (shop_id, locationid, itemid, price, quantity, is_player_sold)
VALUES (10, 11, 71, 600, 999, false);

-- Bronze Hatchet (73) - 1400 gold
INSERT INTO shop_items (shop_id, locationid, itemid, price, quantity, is_player_sold)
VALUES (10, 11, 73, 1400, 999, false);

-- Bronze Short Sword (74) - 1600 gold
INSERT INTO shop_items (shop_id, locationid, itemid, price, quantity, is_player_sold)
VALUES (10, 11, 74, 1600, 999, false);

-- Bronze Long Sword (75) - 2400 gold
INSERT INTO shop_items (shop_id, locationid, itemid, price, quantity, is_player_sold)
VALUES (10, 11, 75, 2400, 999, false);

-- Bronze Spear (78) - 1800 gold
INSERT INTO shop_items (shop_id, locationid, itemid, price, quantity, is_player_sold)
VALUES (10, 11, 78, 1800, 999, false);

-- Add shop items for Iron weapons (excluding Greatsword, Battle Axe, Polearm)
-- Iron Dagger (79) - 1800 gold
INSERT INTO shop_items (shop_id, locationid, itemid, price, quantity, is_player_sold)
VALUES (10, 11, 79, 1800, 999, false);

-- Iron Hatchet (81) - 4200 gold
INSERT INTO shop_items (shop_id, locationid, itemid, price, quantity, is_player_sold)
VALUES (10, 11, 81, 4200, 999, false);

-- Iron Short Sword (82) - 4800 gold
INSERT INTO shop_items (shop_id, locationid, itemid, price, quantity, is_player_sold)
VALUES (10, 11, 82, 4800, 999, false);

-- Iron Long Sword (83) - 7600 gold
INSERT INTO shop_items (shop_id, locationid, itemid, price, quantity, is_player_sold)
VALUES (10, 11, 83, 7600, 999, false);

-- Iron Spear (86) - 5200 gold
INSERT INTO shop_items (shop_id, locationid, itemid, price, quantity, is_player_sold)
VALUES (10, 11, 86, 5200, 999, false);

-- Add location commands for Shop and Talk to Walt buttons
INSERT INTO location_commands (locationid, command_name, button_label, custom_id, button_color)
VALUES 
    (11, 'shop', 'Shop', 'walts_shop', 'PRIMARY'),
    (11, 'talk', 'Talk to Walt', 'talk_walt', 'SECONDARY')
ON CONFLICT (locationid, command_name) DO UPDATE
SET button_label = EXCLUDED.button_label, custom_id = EXCLUDED.custom_id, button_color = EXCLUDED.button_color;

