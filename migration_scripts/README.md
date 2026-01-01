# Migration Scripts

This folder contains Python scripts used to run database migrations.

## Scripts

- **`run_migration.py`** - Runs specific hardcoded migrations (party combat turn system, battle channel columns)
- **`run_dice_migrations.py`** - Runs dice system migrations (adds dice columns, converts damage to dice)
- **`run_use_existing_columns.py`** - Converts damage columns to use existing columns instead of new _dice columns

## Usage

Run from the project root directory:

```bash
python migration_scripts/run_migration.py
python migration_scripts/run_dice_migrations.py
python migration_scripts/run_use_existing_columns.py
```

## Note

All SQL migration files are located in the `migrations/` folder. The scripts automatically reference this folder.

