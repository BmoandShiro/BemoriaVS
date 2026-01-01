# Hybrid Combat System Plan
## Combining Elden Ring + OSRS + D&D Mechanics

---

## System Overview

### Core Concept:
- **Dice Rolls** (D&D): Each damage type rolls its own dice
- **Stat Multipliers** (OSRS): Stats scale damage multiplicatively
- **Multiple Damage Types** (Elden Ring): Weapons can deal multiple damage types simultaneously

---

## Damage Type System

### Physical Damage Types:
1. **Piercing** → Scales with **Dexterity**
2. **Crushing** → Scales with **Strength**
3. **Slashing** → Scales with **(Strength + Dexterity) / 2**

### Magic Damage Types:
- **Fire, Ice, Lightning, Water, Earth, Air, Light, Dark, Magic**
- All scale with **Intelligence**

---

## Weapon Damage Format

### Current System:
- Weapons have: `slashing_damage`, `piercing_damage`, `crushing_damage`, `dark_damage`
- These are flat numbers (e.g., 6 slashing damage)

### New System:
- Weapons will have dice notation for each damage type
- Format: `"1d6"`, `"2d4"`, `"1d8+2"`, etc.
- Example weapon: `1/5/6` means:
  - **Piercing**: `1d1` (1 damage, no variability)
  - **Crushing**: `1d5` (1-5 damage)
  - **Slashing**: `1d6` (1-6 damage)

### Database Schema Changes:
```sql
-- Add dice columns to items table
ALTER TABLE items
ADD COLUMN piercing_dice VARCHAR(10) DEFAULT NULL,  -- e.g., "1d6", "2d4+2"
ADD COLUMN crushing_dice VARCHAR(10) DEFAULT NULL,
ADD COLUMN slashing_dice VARCHAR(10) DEFAULT NULL,
ADD COLUMN fire_dice VARCHAR(10) DEFAULT NULL,
ADD COLUMN ice_dice VARCHAR(10) DEFAULT NULL,
ADD COLUMN lightning_dice VARCHAR(10) DEFAULT NULL,
ADD COLUMN water_dice VARCHAR(10) DEFAULT NULL,
ADD COLUMN earth_dice VARCHAR(10) DEFAULT NULL,
ADD COLUMN air_dice VARCHAR(10) DEFAULT NULL,
ADD COLUMN light_dice VARCHAR(10) DEFAULT NULL,
ADD COLUMN dark_dice VARCHAR(10) DEFAULT NULL,
ADD COLUMN magic_dice VARCHAR(10) DEFAULT NULL;

-- Keep old columns for migration/backwards compatibility
-- Or migrate: convert old damage values to dice notation
```

---

## Stat Multiplier System

### Multiplier Calculation:
```python
def calculate_stat_multiplier(stat_value):
    """
    Calculate damage multiplier based on stat.
    Formula: 1.0 + (stat / 100) * multiplier_rate
    
    Examples:
    - Strength 20: 1.0 + (20/100) * 1.0 = 1.2x (20% bonus)
    - Strength 50: 1.0 + (50/100) * 1.0 = 1.5x (50% bonus)
    """
    multiplier_rate = 1.0  # Can be tuned (0.5 = weaker, 1.5 = stronger)
    return 1.0 + (stat_value / 100.0) * multiplier_rate
```

### Damage Type → Stat Mapping:
- **Piercing**: `Dexterity` multiplier
- **Crushing**: `Strength` multiplier
- **Slashing**: `(Strength + Dexterity) / 2` multiplier
- **All Magic Types**: `Intelligence` multiplier

### Example:
- Weapon: `1/5/6` (1 piercing, 5 crushing, 6 slashing)
- Player Stats: Strength 20, Dexterity 15, Intelligence 10
- Multipliers:
  - Piercing: 1.0 + (15/100) = **1.15x**
  - Crushing: 1.0 + (20/100) = **1.20x**
  - Slashing: 1.0 + ((20+15)/2 / 100) = 1.0 + (17.5/100) = **1.175x**

---

## Damage Calculation Flow

### Step-by-Step Process:

```
1. ATTACK ROLL & HIT CHECKS
   ├─ Attack Roll (d20 + Dexterity)
   ├─ Dodge Check (5% + Agility × 0.5%)
   ├─ Block Check (10% + Dexterity × 0.5%)
   └─ Hit Success (Attack Roll > 10 + Defender Agility)

2. IF HIT SUCCEEDS → DAMAGE CALCULATION

3. DICE ROLLS (Before Multipliers)
   ├─ For each damage type the weapon has:
   │  ├─ Parse dice notation (e.g., "1d6" → roll 1 die, 6 sides)
   │  └─ Roll and sum: roll_dice(6) = 4
   │
   └─ Example: 1/5/6 weapon
      ├─ Piercing: roll 1d1 = 1
      ├─ Crushing: roll 1d5 = 3
      └─ Slashing: roll 1d6 = 4

4. APPLY STAT MULTIPLIERS
   ├─ Piercing: 1 × 1.15 (Dex) = 1.15
   ├─ Crushing: 3 × 1.20 (Str) = 3.60
   └─ Slashing: 4 × 1.175 (Str+Dex/2) = 4.70
   
   Total Base Damage: 1.15 + 3.60 + 4.70 = 9.45

5. APPLY CRITICAL HIT (if critical)
   ├─ Critical Multiplier: 1.5 + (Luck × 0.01)
   └─ Damage: 9.45 × 1.7 = 16.07

6. APPLY RESISTANCES (per damage type)
   ├─ Piercing: 1.15 × (1 - piercing_resistance/100)
   ├─ Crushing: 3.60 × (1 - crushing_resistance/100)
   └─ Slashing: 4.70 × (1 - slashing_resistance/100)
   
   Example (enemy has 20% physical resistance):
   ├─ Piercing: 1.15 × 0.8 = 0.92
   ├─ Crushing: 3.60 × 0.8 = 2.88
   └─ Slashing: 4.70 × 0.8 = 3.76
   
   Total After Resistance: 0.92 + 2.88 + 3.76 = 7.56

7. APPLY STATUS EFFECTS
   └─ Damage bonuses/reductions from buffs/debuffs

8. FINAL DAMAGE
   └─ Round down, minimum 1 (unless 100%+ resistance)
```

---

## Implementation Details

### 1. Dice Parsing Function
```python
def parse_dice(dice_string):
    """
    Parse dice notation like "1d6", "2d4+2", "1d8-1"
    Returns: (num_dice, sides, modifier)
    """
    if not dice_string:
        return (0, 0, 0)
    
    # Remove whitespace
    dice_string = dice_string.strip()
    
    # Handle modifiers
    modifier = 0
    if '+' in dice_string:
        parts = dice_string.split('+')
        dice_string = parts[0]
        modifier = int(parts[1])
    elif '-' in dice_string:
        parts = dice_string.split('-')
        dice_string = parts[0]
        modifier = -int(parts[1])
    
    # Parse dice part (e.g., "1d6")
    if 'd' in dice_string:
        num_dice, sides = map(int, dice_string.split('d'))
    else:
        # Just a number (e.g., "5" = 5 damage, no roll)
        return (0, 0, int(dice_string))
    
    return (num_dice, sides, modifier)

def roll_dice_notation(dice_string):
    """
    Roll dice based on notation.
    Returns total rolled value.
    """
    num_dice, sides, modifier = parse_dice(dice_string)
    
    if num_dice == 0 and sides == 0:
        # Just a flat modifier
        return modifier
    
    total = 0
    for _ in range(num_dice):
        total += random.randint(1, sides)
    
    return total + modifier
```

### 2. Stat Multiplier Function
```python
def get_damage_type_multiplier(damage_type, attacker_stats):
    """
    Get multiplier for a specific damage type based on attacker stats.
    """
    if damage_type == 'piercing':
        dex = attacker_stats.get('total_dexterity', attacker_stats.get('dexterity', 0))
        return 1.0 + (dex / 100.0)
    
    elif damage_type == 'crushing':
        str_stat = attacker_stats.get('total_strength', attacker_stats.get('strength', 0))
        return 1.0 + (str_stat / 100.0)
    
    elif damage_type == 'slashing':
        str_stat = attacker_stats.get('total_strength', attacker_stats.get('strength', 0))
        dex = attacker_stats.get('total_dexterity', attacker_stats.get('dexterity', 0))
        avg_stat = (str_stat + dex) / 2.0
        return 1.0 + (avg_stat / 100.0)
    
    elif damage_type in ['fire', 'ice', 'lightning', 'water', 'earth', 'air', 'light', 'dark', 'magic']:
        int_stat = attacker_stats.get('total_intelligence', attacker_stats.get('intelligence', 0))
        return 1.0 + (int_stat / 100.0)
    
    else:
        return 1.0  # No multiplier for unknown types
```

### 3. Updated Damage Calculation
```python
async def calculate_damage_with_dice(self, attacker_stats: dict, defender_stats: dict,
                                     weapon_dice: dict, is_critical: bool) -> dict:
    """
    Calculate damage with dice rolls and stat multipliers.
    
    Args:
        weapon_dice: Dict of {damage_type: dice_string}
        Example: {'piercing': '1d1', 'crushing': '1d5', 'slashing': '1d6'}
    
    Returns:
        Dict of {damage_type: final_damage}
    """
    damage_by_type = {}
    
    # Step 1: Roll dice for each damage type
    for damage_type, dice_string in weapon_dice.items():
        if not dice_string:
            continue
        
        # Roll the dice
        base_roll = self.roll_dice_notation(dice_string)
        
        # Step 2: Apply stat multiplier
        multiplier = self.get_damage_type_multiplier(damage_type, attacker_stats)
        damage = base_roll * multiplier
        
        # Step 3: Apply critical hit multiplier (if critical)
        if is_critical:
            attacker_luck = attacker_stats.get('total_luck', attacker_stats.get('luck', 0))
            critical_multiplier = 1.5 + (attacker_luck * 0.01)
            damage *= critical_multiplier
        
        # Step 4: Apply resistance
        resistance_key = f"{damage_type}_resistance"
        total_resistance_key = f"total_{resistance_key}"
        resistance = defender_stats.get(total_resistance_key, defender_stats.get(resistance_key, 0))
        resistance_modifier = 1 - (resistance / 100)
        damage *= resistance_modifier
        
        # Step 5: Apply status effects
        if 'playerid' in attacker_stats:
            status_effects = await self.get_active_effects(attacker_stats['playerid'])
            for effect in status_effects:
                if effect['attribute'].startswith('damage_bonus_'):
                    damage *= (1 + effect['modifier_value'] / 100)
                elif effect['attribute'].startswith('damage_reduction_'):
                    damage *= (1 - effect['modifier_value'] / 100)
        
        # Store damage by type
        damage_by_type[damage_type] = max(0, int(damage)) if resistance < 100 else 0
    
    return damage_by_type
```

---

## Migration Strategy

### Phase 1: Add Dice Columns
1. Add dice columns to `items` table
2. Keep old damage columns for backwards compatibility

### Phase 2: Convert Existing Weapons
```sql
-- Example migration: Convert flat damage to dice
-- Iron Sword: 8 slashing → "1d8" slashing
-- Iron Dagger: 3 piercing → "1d3" piercing

UPDATE items
SET slashing_dice = CASE
    WHEN slashing_damage > 0 THEN CONCAT('1d', slashing_damage)
    ELSE NULL
END,
piercing_dice = CASE
    WHEN piercing_damage > 0 THEN CONCAT('1d', piercing_damage)
    ELSE NULL
END,
crushing_dice = CASE
    WHEN crushing_damage > 0 THEN CONCAT('1d', crushing_damage)
    ELSE NULL
END
WHERE type = 'Weapon';
```

### Phase 3: Update Combat System
1. Modify `get_equipped_weapon_damage()` to return dice notation
2. Update `calculate_damage()` to use new system
3. Update attack/ability handlers

### Phase 4: Test & Tune
1. Test with various weapons
2. Balance stat multipliers
3. Adjust dice ranges if needed

---

## Example Weapon Configurations

### Simple Weapon (Iron Dagger):
```json
{
  "name": "Iron Dagger",
  "piercing_dice": "1d6",
  "slashing_dice": "1d2"
}
```
- Rolls: 1d6 piercing + 1d2 slashing
- Scales with: Dex (piercing), (Str+Dex)/2 (slashing)

### Complex Weapon (Iron Greatsword):
```json
{
  "name": "Iron Greatsword",
  "slashing_dice": "2d8",
  "crushing_dice": "1d4"
}
```
- Rolls: 2d8 slashing + 1d4 crushing
- Scales with: (Str+Dex)/2 (slashing), Str (crushing)

### Magic Weapon (Fire Sword):
```json
{
  "name": "Flaming Sword",
  "slashing_dice": "1d8",
  "fire_dice": "1d6"
}
```
- Rolls: 1d8 slashing + 1d6 fire
- Scales with: (Str+Dex)/2 (slashing), Int (fire)

---

## Questions & Clarifications

### 1. Dice Notation for "1/5/6":
- **Question**: You mentioned `1/5/6` means `1d1` piercing, `1d5` crushing, `1d6` slashing
- **Clarification**: `1d1` always rolls 1 (no variability). Did you mean:
  - `1d1` = flat 1 damage (no roll)?
  - Or should it be `1d2` or `1d3` for some variability?

### 2. Stat Multiplier Rate:
- **Question**: What should the multiplier rate be?
- **Options**:
  - `1.0` = 20 Strength = 1.2x (20% bonus)
  - `0.5` = 20 Strength = 1.1x (10% bonus) - weaker scaling
  - `1.5` = 20 Strength = 1.3x (30% bonus) - stronger scaling

### 3. Minimum Dice:
- **Question**: Should all weapons have at least `1d1` for each type, or can they have `0` (no damage of that type)?

### 4. Ability Damage:
- **Question**: Should abilities also use dice notation, or keep current system?
- **Suggestion**: Abilities could have dice like `"2d6+5"` for fire damage

### 5. Display Format:
- **Question**: How should damage be displayed in combat messages?
- **Options**:
  - "You deal 15 damage (8 slashing, 4 crushing, 3 piercing)!"
  - "You deal 15 total damage!"
  - Show dice rolls: "Rolled 6+4+3 = 13, ×1.2 = 15 damage!"

---

## Recommended Starting Point

### Phase 1: Basic Implementation
1. Add dice columns to `items` table
2. Implement dice parsing and rolling
3. Implement stat multipliers
4. Update damage calculation for physical attacks
5. Test with simple weapons (1 damage type)

### Phase 2: Multi-Type Damage
1. Support multiple damage types per weapon
2. Apply resistances per type
3. Sum total damage
4. Test with complex weapons

### Phase 3: Magic Integration
1. Add magic dice support
2. Intelligence multipliers
3. Test with magic weapons

### Phase 4: Abilities
1. Convert abilities to dice system (optional)
2. Or keep abilities separate with current system

---

## Code Structure Preview

```python
# New method in Battle_System.py
async def get_weapon_dice(self, player_id):
    """
    Get dice notation for all equipped weapons.
    Returns: Dict of {damage_type: dice_string}
    """
    weapons = await self.db.fetch("""
        SELECT 
            COALESCE(i.piercing_dice, '') as piercing_dice,
            COALESCE(i.crushing_dice, '') as crushing_dice,
            COALESCE(i.slashing_dice, '') as slashing_dice,
            COALESCE(i.fire_dice, '') as fire_dice,
            -- ... other magic types
        FROM inventory inv
        JOIN items i ON inv.itemid = i.itemid
        WHERE inv.playerid = $1 
        AND inv.isequipped = true
        AND inv.slot IN ('1H_weapon', '2H_weapon', 'left_hand')
        AND i.type = 'Weapon'
    """, player_id)
    
    # Combine dice from all weapons
    combined_dice = {}
    for weapon in weapons:
        for damage_type in ['piercing', 'crushing', 'slashing', 'fire', ...]:
            dice = weapon.get(f'{damage_type}_dice')
            if dice:
                # If multiple weapons have same type, combine dice
                # e.g., "1d6" + "1d4" = "2d6+1d4" or sum them
                if damage_type in combined_dice:
                    combined_dice[damage_type] = self.combine_dice(
                        combined_dice[damage_type], dice
                    )
                else:
                    combined_dice[damage_type] = dice
    
    return combined_dice
```

---

## Next Steps

1. **Review this plan** - Does it match your vision?
2. **Answer clarification questions** - Especially about `1d1` and multiplier rates
3. **Decide on migration** - Convert existing weapons or start fresh?
4. **Implement Phase 1** - Basic dice system
5. **Test and iterate** - Balance multipliers and dice ranges

---

## Benefits of This System

✅ **Variability**: Every attack feels different due to dice rolls
✅ **Stat Investment**: Higher stats = more damage (multiplicative scaling)
✅ **Weapon Variety**: Different weapons feel different (dice ranges)
✅ **Tactical Depth**: Players can optimize for specific damage types
✅ **Familiar**: Combines best of D&D, OSRS, and Elden Ring
✅ **Scalable**: Easy to add new damage types or weapons

