# Mining Logic Documentation - Dank Caverns

## Overview
The mining system allows players to mine ores at specific locations (like Dank Caverns) using equipped pickaxes. The system handles ore selection, pickaxe tier validation, inventory management, and XP rewards.

## File Structure
- **Mining.py**: Main mining module with button handler and mining logic
- **Inventory.py**: Inventory management class that handles adding items

---

## Mining Flow

### 1. Button Handler (`mine_button_handler`)
**Location**: `Mining.py` lines 13-29

**Process**:
1. **Authorization Check**: 
   - Extracts user ID from button custom_id (`mine_{user_id}`)
   - Verifies the clicking user matches the button owner
   - Returns error if unauthorized

2. **Player Data Retrieval**:
   - Gets or creates player record
   - Fetches player details including current location
   - Defers response (ephemeral) to prevent timeout

3. **Mining Action**:
   - Calls `start_mining_action()` with player_id and location_id

---

### 2. Mining Action (`start_mining_action`)
**Location**: `Mining.py` lines 31-104

#### Step 1: Ore Selection (Lines 32-43)
```sql
SELECT o.*, mt.tier_level AS ore_tier
FROM ores o
JOIN material_tiers mt ON o.oretype = mt.material_name
WHERE o.locationid = $1
ORDER BY RANDOM() LIMIT 1
```

**Checks**:
- Queries `ores` table filtered by `locationid` (e.g., Dank Caverns)
- Joins with `material_tiers` to get ore tier level
- Randomly selects ONE ore deposit from available ores at location
- **Validation**: If no ore found → "No ore deposits to mine here."

**Database Tables Used**:
- `ores`: Contains ore deposits with columns:
  - `locationid`: Which location the ore appears at
  - `oretype`: Material name (e.g., "Iron", "Copper")
  - `itemid`: The item ID of the ore to add to inventory
  - `number_of_ores`: Quantity of ore to give
  - `xp_gained`: Experience points awarded
- `material_tiers`: Maps material names to tier levels

---

#### Step 2: Pickaxe Validation (Lines 45-55)
```sql
SELECT i.itemid, i.name, i.pickaxetype
FROM inventory inv
JOIN items i ON inv.itemid = i.itemid
WHERE inv.playerid = $1 
  AND inv.isequipped = TRUE 
  AND i.pickaxe = TRUE
```

**Checks**:
- Verifies player has an equipped pickaxe
- Must have `isequipped = TRUE` in inventory
- Item must have `pickaxe = TRUE` flag in items table
- **Validation**: If no pickaxe → "You need to equip a pickaxe to mine ores."

**Database Tables Used**:
- `inventory`: Player's inventory with equipped status
- `items`: Item definitions with pickaxe flag

---

#### Step 3: Pickaxe Tier Lookup (Lines 57-67)
```sql
SELECT tier_level
FROM material_tiers
WHERE material_name = $1
```

**Process**:
- Gets `pickaxetype` from equipped pickaxe (e.g., "Iron Pickaxe" → "Iron")
- Looks up tier level from `material_tiers` table
- **Validation**: If tier not found → "Error: Unable to determine the tier level of your pickaxe."

**Database Tables Used**:
- `material_tiers`: Maps material names to tier levels (e.g., "Iron" = tier 2, "Copper" = tier 1)

---

#### Step 4: Tier Comparison (Lines 69-75)
**Logic**:
```python
pickaxe_tier = pickaxe_tier_info['tier_level']
ore_tier = ore['ore_tier']

if pickaxe_tier < (ore_tier - 1):
    # Reject mining
```

**Rules**:
- Pickaxe can mine ores of **equal or higher tier**
- Pickaxe can mine ores **one tier lower** (e.g., tier 2 pickaxe can mine tier 1 ore)
- Pickaxe **cannot** mine ores more than one tier higher
- **Validation**: If insufficient tier → "Your pickaxe is not strong enough to mine this type of ore. You need a pickaxe of at least tier {ore_tier - 1}."

**Example**:
- Tier 1 pickaxe: Can mine tier 1 ore only
- Tier 2 pickaxe: Can mine tier 1 and tier 2 ores
- Tier 3 pickaxe: Can mine tier 2 and tier 3 ores

---

#### Step 5: Item Details Retrieval (Lines 77-88)
```sql
SELECT name FROM items WHERE itemid = $1
```

**Process**:
- Gets `itemid` and `number_of_ores` from selected ore
- Fetches item name for display message
- **Validation**: If item not found → "Error: Unable to retrieve item details."

**Database Tables Used**:
- `items`: Item definitions with names

---

#### Step 6: Inventory Addition (Lines 90-92)
```python
inventory = Inventory(self.db, player_id)
result_message = await inventory.add_item(item_id, number_of_ores)
```

**Inventory.add_item() Process** (`Inventory.py` lines 8-42):

1. **Capacity Check**:
   ```sql
   SELECT COUNT(*) FROM inventory WHERE playerid = $1
   ```
   - Gets current inventory slot count
   - Compares against `max_slots` (from `get_inventory_capacity()`)
   - **Validation**: If full → "Your inventory is full. You cannot add more items."

2. **Item Validation**:
   ```sql
   SELECT * FROM items WHERE itemid = $1
   ```
   - Verifies item exists
   - Gets `max_stack` to determine if stackable
   - **Validation**: If invalid → "Invalid item."

3. **Stacking Logic**:
   - **If stackable** (`max_stack > 1`):
     - Checks for existing item in inventory
     - If exists: Updates quantity (`quantity = quantity + new_quantity`)
     - If not exists: Creates new inventory entry
   - **If not stackable**:
     - Always creates new inventory entry

4. **Database Operations**:
   ```sql
   -- Update existing stackable item
   UPDATE inventory SET quantity = $1 WHERE inventoryid = $2
   
   -- Insert new item
   INSERT INTO inventory (playerid, itemid, quantity, isequipped, slot) 
   VALUES ($1, $2, $3, false, NULL)
   ```

**Database Tables Used**:
- `inventory`: Stores player items with quantity, equipped status, slot
- `items`: Item definitions with stackability info

---

#### Step 7: XP Update (Lines 94-100)
```sql
UPDATE player_skills_xp
SET mining_xp = mining_xp + $1
WHERE playerid = $2
```

**Process**:
- Gets `xp_gained` from ore record
- Adds XP to player's mining skill
- No validation needed (always succeeds)

**Database Tables Used**:
- `player_skills_xp`: Stores skill experience points

---

#### Step 8: Success Message (Lines 102-104)
```python
await ctx.send(f"Added {number_of_ores}x {item_name} to your inventory. You gained {xp_gained} XP in Mining.", ephemeral=True)
```

**Response**:
- Shows quantity and name of ore added
- Displays XP gained
- Sent as ephemeral message (only visible to player)

---

## Summary of Checks and Validations

| Check | Location | Error Message |
|-------|----------|--------------|
| Button authorization | `mine_button_handler` | "You are not authorized to interact with this button." |
| Ore exists at location | `start_mining_action` | "No ore deposits to mine here." |
| Pickaxe equipped | `start_mining_action` | "You need to equip a pickaxe to mine ores." |
| Pickaxe tier found | `start_mining_action` | "Error: Unable to determine the tier level of your pickaxe." |
| Pickaxe tier sufficient | `start_mining_action` | "Your pickaxe is not strong enough to mine this type of ore..." |
| Item details found | `start_mining_action` | "Error: Unable to retrieve item details." |
| Inventory not full | `Inventory.add_item()` | "Your inventory is full. You cannot add more items." |
| Item valid | `Inventory.add_item()` | "Invalid item." |

---

## Database Schema Requirements

### `ores` Table
- `locationid`: INTEGER (FK to locations)
- `oretype`: VARCHAR (material name, e.g., "Iron")
- `itemid`: INTEGER (FK to items)
- `number_of_ores`: INTEGER (quantity to give)
- `xp_gained`: INTEGER (XP reward)

### `material_tiers` Table
- `material_name`: VARCHAR (e.g., "Iron", "Copper")
- `tier_level`: INTEGER (1, 2, 3, etc.)

### `inventory` Table
- `playerid`: INTEGER (FK to players)
- `itemid`: INTEGER (FK to items)
- `quantity`: INTEGER
- `isequipped`: BOOLEAN
- `slot`: VARCHAR (nullable)

### `items` Table
- `itemid`: INTEGER (PK)
- `name`: VARCHAR
- `pickaxe`: BOOLEAN
- `pickaxetype`: VARCHAR (material name for tier lookup)
- `max_stack`: INTEGER

### `player_skills_xp` Table
- `playerid`: INTEGER (FK to players)
- `mining_xp`: INTEGER

---

## Key Features

1. **Location-Based**: Ores are tied to specific locations (Dank Caverns has its own ore set)
2. **Random Selection**: One random ore is selected per mining action
3. **Tier System**: Pickaxe tier must be sufficient for ore tier
4. **Stacking**: Stackable ores combine in inventory, non-stackable create separate entries
5. **Capacity Management**: Checks inventory capacity before adding
6. **XP Rewards**: Mining grants XP to mining skill
7. **Authorization**: Buttons are user-specific to prevent abuse

---

## Potential Issues/Improvements

1. **No Stamina/Energy Cost**: Mining doesn't consume stamina or energy
2. **No Cooldown**: Players can spam mine button
3. **No Failure Chance**: Mining always succeeds if tier requirements met
4. **No Durability**: Pickaxes don't degrade
5. **Inventory Capacity**: Uses slot count, not weight-based system
6. **No Location Validation**: Doesn't verify player is actually at the location (similar to cauldron/rest issue)

