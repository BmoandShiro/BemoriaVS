-- Update food items to have type 'Consumable' for easier filtering
-- This allows the use item system to work with all consumables (food, potions, etc.)

UPDATE items
SET type = 'Consumable'
WHERE name IN ('Chips', 'Smoked Fish Fillet', 'Fish and Chips', 'Fishball Stew');

