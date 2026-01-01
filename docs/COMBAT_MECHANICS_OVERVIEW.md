# Combat Mechanics Overview

## Turn Order & Initiative

### Who Goes First?
- **Party Battles**: Turn order is determined by **Agility** (highest agility goes first)
  - Players are sorted by `total_agility` (includes equipment bonuses) in descending order
  - If agility is tied, player ID is used as a tiebreaker
  - Turn order is stored in `battle_instances.turn_order` as an array of player IDs
  - First player in the array gets the first turn

- **Solo Battles**: Player always goes first, then enemy

### Turn Flow
1. **Player Turn Phase**: All players take their turns in agility order
2. **Enemy Turn Phase**: All enemies attack after all players have acted
3. **Repeat**: Cycle continues until battle ends

### Turn Advancement
- After a player acts, the system moves to the next player in `turn_order`
- Dead players are automatically skipped
- When the last player in the array acts, it wraps back to the first player (new round)
- `turn_number` increments each full round

---

## Attack Roll & Accuracy

### Attack Roll Calculation
```
Attack Roll = d20 (1-20) + Attacker's Dexterity
```

### Hit Success Check
```
Hit Success = Attack Roll > (10 + Defender's Agility)
```

**Example:**
- Attacker rolls d20 = 15, has 8 Dexterity → Attack Roll = 23
- Defender has 5 Agility → Hit Threshold = 15
- 23 > 15 → **Hit!**

---

## Dodge, Block, and Hit Resolution

The system checks in this order:

### 1. **Dodge Check** (Happens First)
```
Dodge Chance = 5% base + (Defender's Agility × 0.5%)
```
- If dodge succeeds → **Attack misses completely** (no damage, no block check)
- If dodge fails → Continue to block check

**Example:**
- Defender has 10 Agility → Dodge Chance = 5% + (10 × 0.5%) = 10%
- Roll 1-10 on d100 → Dodge succeeds, attack misses

### 2. **Block Check** (If Dodge Failed)
```
Block Chance = 10% base + (Defender's Dexterity × 0.5%)
```
- If block succeeds → **Attack is blocked** (reduces damage, but still counts as a hit)
- Blocked attacks still deal damage, but typically at reduced rate (implementation may vary)

**Example:**
- Defender has 12 Dexterity → Block Chance = 10% + (12 × 0.5%) = 16%
- Roll 1-16 on d100 → Block succeeds

### 3. **Hit Success** (If Dodge Failed)
- Uses the Attack Roll vs Hit Threshold calculation above
- If hit succeeds → Damage is calculated
- If hit fails → Attack misses

---

## Critical Hits

### Critical Hit Chance
```
Critical Chance = 5% base + (Attacker's Luck × 0.5%)
```

### Critical Hit Multiplier
```
Critical Multiplier = 1.5 + (Attacker's Luck × 0.01)
```

**Example:**
- Attacker has 20 Luck
- Critical Chance = 5% + (20 × 0.5%) = 15%
- If critical → Multiplier = 1.5 + (20 × 0.01) = 1.7x damage

---

## Damage Calculation

### Base Damage (Physical Attacks)
```
Base Damage = Attacker's Total Strength + Equipped Weapon Damage
```

**Weapon Damage:**
- Sums damage from all equipped weapons in combat slots:
  - `1H_weapon` slot
  - `2H_weapon` slot  
  - `left_hand` slot
- **Excludes** tool belt slots (tools don't add combat damage)
- Adds: `slashing_damage + piercing_damage + crushing_damage + dark_damage`

**Example:**
- Player has 15 Strength
- Equipped Iron Sword: 8 slashing, 2 piercing
- Base Damage = 15 + (8 + 2) = **25**

### Base Damage (Ability Attacks)
```
Base Damage = Ability's Base Damage + (Intelligence × 0.5) [for magic abilities]
```

### Final Damage Calculation
```
1. Apply Resistance Modifier:
   Damage = Base Damage × (1 - (Resistance / 100))
   
2. Apply Critical Multiplier (if critical):
   Damage = Damage × Critical Multiplier
   
3. Apply Status Effect Modifiers:
   - Damage bonuses from buffs
   - Damage reductions from debuffs
   
4. Minimum Damage:
   - If resistance < 100%: Minimum 1 damage
   - If resistance ≥ 100%: 0 damage (immunity)
```

**Resistance Formula:**
- **Positive resistance** (e.g., 25%) → Reduces damage by 25%
- **Negative resistance** (e.g., -10%) → Increases damage by 10%
- **100% or higher** → Complete immunity (0 damage)

**Example:**
- Base Damage = 50
- Defender has 30% physical resistance
- Resistance Modifier = 1 - (30/100) = 0.7
- Damage = 50 × 0.7 = **35**
- If critical (1.7x): 35 × 1.7 = **59.5** → **59** (rounded down)

---

## Ability Hit Calculation

For abilities (spells, special attacks), the system uses a similar but separate calculation:

```
Hit Roll = d20 + Attacker's Relevant Stat
```

The "relevant stat" depends on ability type:
- **Magic abilities** (fire, ice, lightning, etc.) → Intelligence
- **Physical abilities** → Strength
- **Other types** → Appropriate stat based on ability

---

## Flee Mechanics

### Flee Success Check
```
Player Roll = d20 + Agility Modifier (minimum +0)
Enemy Roll = d20 + Enemy Agility Modifier (minimum +0)
```

- If **Player Roll > Enemy Roll** → Flee succeeds
- If **Player Roll ≤ Enemy Roll** → Flee fails, player remains in combat

**On Successful Flee:**
- Player is removed from `battle_participants`
- Player is removed from `turn_order` (if in party battle)
- If party leader flees → Party is disbanded
- If party member flees → Removed from party
- Battle continues for remaining participants

---

## Status Effects & Modifiers

### Active Effects
- Status effects from `temporary_effects` table are applied during damage calculation
- Effects can modify:
  - Damage bonuses (`damage_bonus_*`)
  - Damage reductions (`damage_reduction_*`)
  - Other attributes

### Effect Application
- Effects are checked during `calculate_damage()`
- Multiple effects can stack
- Effects have duration and expire automatically

---

## Summary Flow

### Attack Sequence:
1. **Check Turn** → Is it this player's turn? (party battles only)
2. **Calculate Attack Roll** → d20 + Dexterity
3. **Check Dodge** → 5% + (Agility × 0.5%)
4. **Check Block** → 10% + (Dexterity × 0.5%) [if dodge failed]
5. **Check Hit** → Attack Roll > (10 + Defender Agility)
6. **Check Critical** → 5% + (Luck × 0.5%)
7. **Calculate Base Damage** → Strength + Weapon Damage
8. **Apply Resistance** → Damage × (1 - Resistance/100)
9. **Apply Critical** → Damage × Critical Multiplier [if critical]
10. **Apply Status Effects** → Modify damage based on active effects
11. **Apply Damage** → Update health, check for death
12. **Advance Turn** → Move to next player or enemy phase

---

## Key Stats & Their Roles

| Stat | Combat Role |
|------|-------------|
| **Strength** | Adds to base physical damage |
| **Dexterity** | Adds to attack roll, increases block chance |
| **Agility** | Determines turn order, increases dodge chance, affects hit threshold |
| **Intelligence** | Adds to magic ability damage |
| **Luck** | Increases critical hit chance and critical multiplier |
| **Endurance** | Increases health pool |
| **Resistances** | Reduces damage of specific types (physical, fire, ice, etc.) |

---

## Notes

- **Weapon Damage**: Only weapons in combat slots count. Tools in tool belt don't add damage.
- **Minimum Damage**: Unless immune (100%+ resistance), attacks always deal at least 1 damage.
- **Turn Skipping**: Dead players are automatically skipped in turn order.
- **Party Battles**: All players act before any enemies act.
- **Solo Battles**: Player → Enemy → Player → Enemy (alternating).

