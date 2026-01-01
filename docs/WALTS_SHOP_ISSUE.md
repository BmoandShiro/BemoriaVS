# Walt's Weapons Shop Setup Issue

## Problem
The `shop_items` table has a PRIMARY KEY constraint on only `shop_id`, which prevents multiple items from being stored for the same shop. This is a database schema issue that needs to be fixed.

## Current Status
- ✅ Shop handler created (`Walts_Weapons.py`)
- ✅ Location commands added (Shop and Talk to Walt buttons)
- ✅ Shop config entry created
- ❌ Shop items cannot be inserted due to PRIMARY KEY constraint

## Solution Needed
The `shop_items` table PRIMARY KEY should be a composite key, likely:
- `(shop_id, locationid, itemid, is_player_sold)` OR
- `(itemid, shop_id, is_player_sold)`

## Temporary Workaround
For now, the shop buttons are set up and the handler is ready. You can:
1. Manually insert items into `shop_items` table one at a time (deleting previous entries)
2. Fix the PRIMARY KEY constraint on `shop_items` table
3. Then run the migration script again

## Items to Add
- Bronze Dagger (71) - 600 gold
- Bronze Hatchet (73) - 1400 gold
- Bronze Short Sword (74) - 1600 gold
- Bronze Long Sword (75) - 2400 gold
- Bronze Spear (78) - 1800 gold
- Iron Dagger (79) - 1800 gold
- Iron Hatchet (81) - 4200 gold
- Iron Short Sword (82) - 4800 gold
- Iron Long Sword (83) - 7600 gold
- Iron Spear (86) - 5200 gold

All with: `shop_id = 10`, `locationid = 11`, `quantity = 999`, `is_player_sold = false`

