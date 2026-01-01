# Database Migrations

This folder contains all SQL migration files for the database schema.

## Migration Files

### Combat System
- `add_party_combat_turn_system.sql` - Adds turn order tracking for party battles
- `add_battle_channel_columns.sql` - Adds channel_id and message_id to battle_instances

### Damage System
- `add_dice_columns.sql` - Adds dice notation columns (deprecated - use existing columns instead)
- `convert_damage_to_dice.sql` - Converts flat damage values to dice notation
- `use_existing_damage_columns.sql` - Converts damage columns to VARCHAR and stores dice notation

### Weapons & Items
- `add_weapon_damage_columns.sql` - Adds slashing, piercing, crushing damage columns
- `update_weapon_damage_and_smithing.sql` - Updates weapon damage values and smithing requirements
- `add_armor_items.sql` - Adds armor items to the database

### Inventory
- `modify_inventory_constraint.sql` - Modifies inventory unique constraint for dual-wielding

### Shops
- `setup_shop_tables.sql` - Creates shop system tables
- `setup_general_store.sql` - Sets up general store shop
- `setup_blacksmith.sql` - Sets up blacksmith shop
- `setup_walts_weapons_shop.sql` - Sets up Walt's Weapons shop

### Other
- `add_critical_indexes.sql` - Adds performance indexes to critical tables
- `add_smithing_level_column.sql` - Adds smithing_level to players table

## Running Migrations

Use the scripts in the `migration_scripts/` folder to run these migrations.

