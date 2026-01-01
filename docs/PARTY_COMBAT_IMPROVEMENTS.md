# Party Combat System Analysis & Recommendations

## Current State

### ✅ What's Working:
1. Party detection - detects if player is in party
2. Party battle instances - creates party battle type
3. All members added - adds all party members to battle
4. Enemy scaling - spawns enemies based on party size
5. Enemy targeting - enemies attack random party members
6. Victory rewards - attempts to reward all participants

### ❌ Issues Found:

1. **Turn System Problems:**
   - Lines 602-637: Tries to prompt ALL party members at once after one action
   - No turn order tracking
   - No sequential turn system
   - Players can act simultaneously (race conditions)

2. **Loot Distribution Problems:**
   - Line 574: Calls `handle_enemy_defeat` for EACH participant
   - This means EVERYONE gets the FULL loot (not split)
   - No loot distribution system (equal split, need/greed, etc.)
   - No loot sharing/party loot table

3. **Encounter Handling:**
   - Only first player gets initial prompt
   - Other members don't get notified battle started
   - No turn indicator/whose turn it is

---

## Recommended Solutions

### 1. Turn-Based System

**Add to `battle_instances` table:**
```sql
ALTER TABLE battle_instances 
ADD COLUMN current_turn_player_id INTEGER REFERENCES players(playerid),
ADD COLUMN turn_order INTEGER[] DEFAULT '{}',
ADD COLUMN turn_number INTEGER DEFAULT 0;
```

**Turn Flow:**
1. Initialize turn order (random or by agility)
2. Track current turn player
3. Only that player can act
4. After action, move to next player
5. After all players act, enemies act
6. Repeat until battle ends

### 2. Loot Distribution Options

**Option A: Equal Split (Simplest)**
- Divide all loot equally among party members
- Round down quantities
- Remaining items go to party leader

**Option B: Need/Greed System**
- Roll for each item
- Need = class/role appropriate
- Greed = anyone can use
- Highest roll wins

**Option C: Party Loot Table**
- All loot goes to shared party inventory
- Leader distributes after battle
- Or auto-distribute based on rules

**Option D: Individual Rolls (Current - but fixed)**
- Each player rolls separately
- But only ONE instance of loot drops total
- Winner takes all, or highest roll gets first pick

### 3. Encounter Handling

**Battle Start:**
- Notify ALL party members battle started
- Show turn order
- Prompt first player in turn order

**Turn Management:**
- Track whose turn it is
- Only that player can act
- Show "Waiting for [Player]'s turn..." to others
- Auto-skip dead/unconscious players

---

## Implementation Plan

### Phase 1: Turn System (Priority 1)
1. Add turn tracking to database
2. Initialize turn order on battle start
3. Implement sequential turn flow
4. Add turn indicators

### Phase 2: Loot Distribution (Priority 2)
1. Choose loot system (recommend: Equal Split or Need/Greed)
2. Implement loot pooling
3. Distribute after battle ends
4. Handle inventory full scenarios

### Phase 3: Encounter Improvements (Priority 3)
1. Notify all members on battle start
2. Show battle status to all members
3. Add turn timer (optional)
4. Better battle UI

---

## Recommended Loot System: **Equal Split with Leader Bonus**

**Logic:**
1. Collect all dropped items
2. Split quantities equally (round down)
3. Remaining items go to party leader
4. If someone's inventory is full, their share goes to next person
5. Gold is split equally

**Example:**
- Enemy drops: 10 gold, 3 potions, 1 sword
- Party: 3 members
- Result: Each gets 3 gold, 1 potion, leader gets sword + 1 extra gold

