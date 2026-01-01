# Damage Variability Improvement Plan

## Current System Analysis

### Current Damage Flow:
1. **Base Damage** = Fixed (Strength + Weapon Damage OR Ability Base + Intelligence*0.5)
2. **Resistance Modifier** = Fixed multiplier (1 - resistance/100)
3. **Critical Multiplier** = Fixed (1.5 + Luck*0.01) - only if critical
4. **Status Effects** = Fixed multipliers
5. **Final Damage** = Rounded down integer

### Problem:
- **No randomness in damage calculation** - same base damage always produces same result
- Only variability comes from:
  - Hit/Miss (random)
  - Critical hits (random chance, but fixed multiplier)
- Players see predictable damage numbers, reducing excitement

---

## Proposed Solutions

### Option 1: Percentage-Based Variance (Simplest)
**Concept:** Add random variance to base damage before modifiers

**Formula:**
```
Variance Range = ±(Variance_Percentage / 100)
Random Multiplier = 1.0 + random.uniform(-Variance_Range, +Variance_Range)
Base Damage = (Strength + Weapon Damage) × Random Multiplier
```

**Example:**
- Base Damage: 25
- Variance: ±20%
- Random Multiplier: 0.85 to 1.15
- Result: 21.25 to 28.75 damage (before other modifiers)

**Pros:**
- Simple to implement
- Easy to tune (just change percentage)
- Predictable range
- Works for all damage types

**Cons:**
- Can feel arbitrary
- Doesn't account for skill/weapon differences
- Same variance for all attacks

**Implementation:**
- Add `damage_variance` parameter (default 15-20%)
- Apply to base damage before resistance/critical

---

### Option 2: Dice Roll System (D&D Style)
**Concept:** Roll dice and add to base damage

**Formula:**
```
Damage Dice = Weapon/Ability determines dice (e.g., 1d6, 2d4, 1d8+2)
Base Damage = Strength + Weapon Damage
Dice Roll = roll_dice(sides) × number_of_dice + modifier
Final Base = Base Damage + Dice Roll
```

**Example:**
- Base: 15 Strength + 10 Weapon = 25
- Weapon has "1d6" damage roll
- Roll: 4
- Final Base: 25 + 4 = 29

**Pros:**
- Familiar to D&D players
- Can vary by weapon/ability
- More tactical (players know range)
- Can show dice roll in messages

**Cons:**
- More complex to implement
- Need to add dice data to weapons/abilities
- Requires database changes

**Implementation:**
- Add `damage_dice` column to `items` table (e.g., "1d6", "2d4", "1d8+2")
- Add `damage_dice` to abilities table
- Parse and roll dice in damage calculation

---

### Option 3: Skill-Based Variance (Most Realistic)
**Concept:** Higher skill = more consistent damage (lower variance)

**Formula:**
```
Skill Level = Relevant stat (Strength for physical, Intelligence for magic)
Variance = Base_Variance × (1 - (Skill_Level / Max_Skill_Level) × 0.5)
Random Multiplier = 1.0 + random.uniform(-Variance, +Variance)
```

**Example:**
- Base Variance: 25%
- Strength: 20 (out of assumed max ~50)
- Variance Reduction: 0.5 × (20/50) = 0.2
- Final Variance: 25% × (1 - 0.2) = 20%
- High skill players: ±15% variance
- Low skill players: ±25% variance

**Pros:**
- Rewards skill investment
- More realistic (skilled fighters are more consistent)
- Encourages stat building
- Can combine with other options

**Cons:**
- More complex
- Need to define "max skill level"
- May make low-level players feel weak

**Implementation:**
- Calculate variance based on relevant stat
- Combine with Option 1 or 2

---

### Option 4: Weapon-Type Variance (Most Thematic)
**Concept:** Different weapon types have different variance patterns

**Weapon Types:**
- **Precision Weapons** (daggers, rapiers): Low variance (±10%), consistent
- **Heavy Weapons** (greatswords, hammers): High variance (±30%), swingy
- **Balanced Weapons** (swords, axes): Medium variance (±20%)
- **Magic Abilities**: Medium-high variance (±25%), unpredictable

**Formula:**
```
Weapon Variance = Lookup based on weapon type
Random Multiplier = 1.0 + random.uniform(-Weapon_Variance, +Weapon_Variance)
```

**Pros:**
- Thematic and immersive
- Adds weapon choice strategy
- Players can choose playstyle
- Makes different weapons feel different

**Cons:**
- Need to categorize all weapons
- May need database changes
- More complex balance

**Implementation:**
- Add `variance_type` or `weapon_category` to items
- Or calculate based on weapon damage types (slashing/piercing/crushing)

---

### Option 5: Hybrid Approach (Recommended)
**Concept:** Combine multiple methods for best results

**Formula:**
```
1. Base Damage = Strength + Weapon Damage
2. Weapon Dice Roll = Roll weapon's damage dice (if exists)
3. Skill Variance = Calculate variance based on skill level
4. Random Multiplier = 1.0 + random.uniform(-Skill_Variance, +Skill_Variance)
5. Final Base = (Base Damage + Weapon Dice) × Random Multiplier
6. Apply resistance, critical, status effects as normal
```

**Example:**
- Base: 15 Strength + 10 Weapon = 25
- Weapon Dice: 1d6 = 4
- Skill Variance: ±18% (based on Strength 20)
- Random Multiplier: 0.91
- Final Base: (25 + 4) × 0.91 = 26.39
- After resistance (30%): 26.39 × 0.7 = 18.47
- Final: 18 damage

**Pros:**
- Most flexible and interesting
- Combines best aspects of all systems
- Highly customizable
- Can tune each component separately

**Cons:**
- Most complex to implement
- Requires careful balancing
- More calculations per attack

---

## Recommended Implementation Plan

### Phase 1: Simple Variance (Quick Win)
**Goal:** Add immediate variability with minimal changes

1. Add `damage_variance` parameter to `calculate_damage()` method
   - Default: 15% variance
   - Configurable per damage type if needed

2. Apply variance to base damage:
   ```python
   variance = 0.15  # ±15%
   random_multiplier = 1.0 + random.uniform(-variance, variance)
   base_damage = base_damage * random_multiplier
   ```

3. Update damage messages to show range:
   - "You deal 18-22 damage" → "You deal 20 damage (18-22 range)"

**Time:** ~30 minutes
**Impact:** Immediate variability improvement

---

### Phase 2: Skill-Based Variance (Medium Term)
**Goal:** Make skill matter for consistency

1. Calculate variance based on relevant stat:
   - Physical attacks: Based on Strength
   - Magic attacks: Based on Intelligence
   - Formula: `variance = base_variance × (1 - (stat / 100) × 0.3)`

2. Example:
   - Base variance: 20%
   - Strength 30: 20% × (1 - 0.09) = 18.2% variance
   - Strength 10: 20% × (1 - 0.03) = 19.4% variance

**Time:** ~1 hour
**Impact:** Rewards stat investment, more realistic

---

### Phase 3: Weapon Dice System (Long Term)
**Goal:** Add weapon-specific damage rolls

1. Add `damage_dice` column to `items` table:
   - Format: "1d6", "2d4", "1d8+2", etc.
   - Default: "1d4" for weapons without dice

2. Parse dice notation and roll:
   ```python
   def parse_dice(dice_string):
       # "1d6" -> (1, 6, 0)
       # "2d4+2" -> (2, 4, 2)
       # Returns: (num_dice, sides, modifier)
   ```

3. Add dice roll to base damage before variance

**Time:** ~2-3 hours
**Impact:** More tactical, weapon variety

---

## Configuration Options

### Variance Settings (Recommended Defaults):
```python
DAMAGE_VARIANCE_CONFIG = {
    'physical': 0.15,      # ±15% for physical attacks
    'magic': 0.20,         # ±20% for magic (more unpredictable)
    'ability': 0.18,       # ±18% for abilities
    'base_variance': 0.20, # Base variance before skill reduction
    'skill_reduction': 0.3 # How much skill reduces variance (30% max)
}
```

### Weapon Type Variance (Optional):
```python
WEAPON_VARIANCE = {
    'precision': 0.10,     # Daggers, rapiers
    'balanced': 0.15,      # Swords, axes
    'heavy': 0.25,         # Greatswords, hammers
    'ranged': 0.20,        # Bows, crossbows
    'magic': 0.25          # Staves, wands
}
```

---

## User Experience Improvements

### Damage Display Options:

1. **Show Range in Messages:**
   ```
   "You deal 20 damage (18-22 range)!"
   ```

2. **Show Variance Indicator:**
   ```
   "You deal 20 damage! (High roll! 🎲)"
   "You deal 15 damage. (Low roll 😞)"
   ```

3. **Show Skill Impact:**
   ```
   "Your skill allows for consistent damage: 19-21 range"
   ```

---

## Testing Considerations

### Test Cases:
1. **Low Strength Player** (5): Should see high variance
2. **High Strength Player** (30): Should see lower variance
3. **Different Weapons**: Should feel different if using weapon variance
4. **Critical Hits**: Variance should apply before or after critical?
5. **Edge Cases**: Minimum damage (1) should still apply

### Balance Testing:
- Average damage over 100 attacks should equal current system
- Variance shouldn't make combat feel unfair
- High variance weapons should have higher average damage to compensate

---

## Questions to Decide:

1. **Variance Range**: ±15%, ±20%, or ±25%?
2. **Skill Impact**: Should high skill reduce variance significantly (30-50%) or slightly (10-20%)?
3. **Weapon Dice**: Do we want to add dice to all weapons, or just use variance?
4. **Critical Hits**: Should variance apply before or after critical multiplier?
5. **Display**: Show damage range in messages, or keep it hidden?
6. **Minimum/Maximum**: Should we cap variance to prevent extreme outliers?

---

## Recommended Starting Point:

**Phase 1 (Simple Variance):**
- ±18% variance for all damage types
- Apply to base damage before resistance/critical
- Show variance in damage messages (optional)
- Test and tune based on feedback

**Then iterate based on player feedback:**
- If too predictable → Add skill-based variance
- If weapons feel same → Add weapon-type variance
- If want more tactical → Add dice system

---

## Code Structure Preview:

```python
async def calculate_damage(self, attacker_stats: dict, defender_stats: dict, 
                         damage_type: str, base_damage: int, is_critical: bool,
                         variance: float = 0.18) -> int:
    """
    Calculate final damage with variability.
    
    Args:
        variance: Damage variance percentage (0.18 = ±18%)
    """
    # Apply variance to base damage
    variance_multiplier = 1.0 + random.uniform(-variance, variance)
    base_damage = base_damage * variance_multiplier
    
    # Rest of calculation (resistance, critical, status effects)...
    # ...
    
    return final_damage
```

---

## Next Steps:

1. **Review this plan** - Decide on approach
2. **Choose variance percentage** - Start with 15-20%
3. **Implement Phase 1** - Simple variance first
4. **Test and iterate** - Get player feedback
5. **Add complexity** - If needed, add skill/weapon variance

