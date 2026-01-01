# Hybrid Combat System Implementation

## Clarifications Confirmed:

1. **Dice Rolls**: 0-X (not 1-X)
   - `1d6` = 0-6 (inclusive)
   - `1d1` = 0-1 (coin flip)

2. **Stat Multipliers**: 
   - Formula: `1.0 + (stat / 100)`
   - At 100 stat = 2.0x
   - At 50 stat = 1.5x
   - At -10 stat = 0.9x (negative stats reduce damage)
   - Scales per level (0.01x per stat point)

3. **Abilities**: Use dice rolls based on elemental damage types

4. **Display**: Show damage per type after resistances

## Implementation Steps:

1. Create SQL migration for dice columns
2. Update dice rolling function (0-X instead of 1-X)
3. Create stat multiplier functions
4. Update weapon damage calculation
5. Update ability damage calculation
6. Update damage display messages
7. Test and balance

