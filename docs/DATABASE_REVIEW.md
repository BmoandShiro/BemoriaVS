# Database Structure Review & Recommendations

## Overall Rating: 7/10

**Strengths:**
- Good use of asyncpg with connection pooling
- Flexible JSON-based quest system
- Separation of concerns (inventory, quests, NPCs)
- Support for both static and dynamic NPCs

**Areas for Improvement:**
- Missing indexes on frequently queried columns
- JSON fields may cause performance issues at scale
- Connection pool size is excessive
- Some normalization opportunities

---

## 1. INVENTORY SYSTEM

### Current Structure
- **Table:** `inventory`
- **Key Columns:** `inventoryid`, `playerid`, `itemid`, `quantity`, `isequipped`, `slot`, `in_bank`, `caught_fish_id`
- **Related:** `items` table, `player_data.inventory_slots`, `caught_fish` table

### Issues Identified

#### 🔴 **Critical: Missing Indexes**
```sql
-- These queries are run frequently but likely lack indexes:
SELECT * FROM inventory WHERE playerid = $1 AND itemid = $2  -- Line 24-27 in Inventory.py
SELECT COUNT(*) FROM inventory WHERE playerid = $1 AND isequipped = FALSE AND in_bank = FALSE  -- Line 238-245 in PostgreSQLlogic.py
SELECT * FROM inventory WHERE playerid = $1 AND slot = $2 AND isequipped = true  -- Line 172-174 in Inventory.py
```

**Recommendation:**
```sql
CREATE INDEX idx_inventory_playerid_itemid ON inventory(playerid, itemid);
CREATE INDEX idx_inventory_playerid_equipped_bank ON inventory(playerid, isequipped, in_bank);
CREATE INDEX idx_inventory_playerid_slot_equipped ON inventory(playerid, slot, isequipped) WHERE isequipped = true;
CREATE INDEX idx_inventory_playerid_bank ON inventory(playerid, in_bank);
```

#### 🟡 **Moderate: Stacking Logic Issue**
**Location:** `Inventory.py` lines 29-34

The current stacking logic checks if an item exists, but doesn't handle the case where:
- Item exists but is equipped (shouldn't stack with equipped items)
- Item exists in bank (shouldn't stack with bank items)

**Recommendation:**
```python
existing_item = await self.db.fetchrow(
    "SELECT * FROM inventory WHERE playerid = $1 AND itemid = $2 AND isequipped = FALSE AND in_bank = FALSE",
    self.player_id, item_id
)
```

#### 🟡 **Moderate: Capacity Check Race Condition**
**Location:** `PostgreSQLlogic.py` lines 248-252

The capacity check uses two separate queries, which can lead to race conditions if multiple items are added simultaneously.

**Recommendation:** Use a single atomic query:
```python
async def can_add_to_inventory(self, player_id, items_to_add=1):
    result = await self.fetchval("""
        SELECT (COUNT(*) + $2) <= inventory_slots
        FROM player_data pd
        LEFT JOIN inventory inv ON inv.playerid = pd.playerid 
            AND inv.isequipped = FALSE 
            AND inv.in_bank = FALSE
        WHERE pd.playerid = $1
        GROUP BY pd.inventory_slots
    """, player_id, items_to_add)
    return result
```

#### 🟢 **Minor: Inventory Capacity Storage**
Storing `inventory_slots` in `player_data` is good, but consider:
- Adding a `max_inventory_slots` cap to prevent unlimited expansion
- Tracking inventory upgrades in a separate `inventory_upgrades` table for analytics

---

## 2. QUEST SYSTEM

### Current Structure
- **Tables:** `quests`, `player_quests`
- **Key Columns:** 
  - `quests`: `quest_id`, `name`, `description`, `objective` (JSON), `requirements` (JSON), `reward_items` (JSON), `turn_in_npc_id`, `is_dynamic`
  - `player_quests`: `player_id`, `quest_id`, `status`, `current_step`, `progress` (JSON), `is_dynamic`

### Issues Identified

#### 🔴 **Critical: JSON Performance at Scale**
**Location:** `DynamicNPCModule.py` lines 59, 88, 294

JSON fields are parsed on every query, which will become slow as quest data grows.

**Recommendation:** Consider normalized tables for common quest types:
```sql
-- For collect quests (most common)
CREATE TABLE quest_objectives_collect (
    quest_id INTEGER REFERENCES quests(quest_id),
    item_id INTEGER REFERENCES items(itemid),
    quantity INTEGER NOT NULL,
    PRIMARY KEY (quest_id, item_id)
);

-- For quest rewards
CREATE TABLE quest_rewards (
    quest_id INTEGER REFERENCES quests(quest_id),
    reward_type VARCHAR(20) NOT NULL, -- 'gold', 'item', 'xp'
    reward_value INTEGER,
    item_id INTEGER REFERENCES items(itemid),
    quantity INTEGER,
    PRIMARY KEY (quest_id, reward_type, COALESCE(item_id, 0))
);
```

Keep JSON for truly dynamic/complex quests, but normalize common patterns.

#### 🟡 **Moderate: Missing Quest Status Index**
**Location:** `DynamicNPCModule.py` lines 49-54, 144-152

Frequent queries filter by `status = 'in_progress'` but likely lack an index.

**Recommendation:**
```sql
CREATE INDEX idx_player_quests_status ON player_quests(player_id, status);
CREATE INDEX idx_player_quests_npc_turnin ON player_quests(player_id, quest_id, status) 
    WHERE status = 'in_progress';
```

#### 🟡 **Moderate: Quest Progress Tracking**
**Location:** `DynamicNPCModule.py` lines 384-405

The `progress` JSON field is updated but there's no clear structure. Consider:
- Adding a `progress_updated_at` timestamp
- Creating a `quest_progress_log` table for analytics
- Adding quest completion rate tracking

**Recommendation:**
```sql
ALTER TABLE player_quests ADD COLUMN progress_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
CREATE INDEX idx_player_quests_updated ON player_quests(progress_updated_at) WHERE status = 'in_progress';
```

#### 🟢 **Minor: Quest Requirements Validation**
**Location:** `DynamicNPCModule.py` lines 291-317

The requirements check is good, but consider:
- Adding a `quest_prerequisites` table for quest chains
- Adding level requirements as a separate column (not just in JSON)
- Adding quest cooldowns/timers

---

## 3. NPC SYSTEM

### Current Structure
- **Tables:** `dynamic_npcs`, `dynamic_dialogs`
- **Key Columns:**
  - `dynamic_npcs`: `dynamic_npc_id`, `name`, `locationid`, `description`
  - `dynamic_dialogs`: `dialog_id`, `dynamic_npc_id`, `dialog_text`, `follow_up_dialog_id`

### Issues Identified

#### 🟡 **Moderate: Missing NPC Location Index**
**Location:** `NPC_Manager.py` line 20, `player_interface.py` line 138

NPCs are frequently queried by location.

**Recommendation:**
```sql
CREATE INDEX idx_dynamic_npcs_location ON dynamic_npcs(locationid);
CREATE INDEX idx_dynamic_npcs_name_lower ON dynamic_npcs(LOWER(name)); -- For case-insensitive lookups
```

#### 🟡 **Moderate: Dialog Tree Performance**
**Location:** `DynamicNPCModule.py` lines 203-208, 235-240

Dialog trees use `follow_up_dialog_id` which can cause N+1 query problems for deep trees.

**Recommendation:**
- Consider materialized paths for dialog trees
- Cache dialog trees in memory on bot startup
- Add `dialog_depth` column for optimization

#### 🟢 **Minor: NPC State Management**
Consider adding:
- `npc_state` table for tracking player-NPC interactions
- `npc_responses` table for storing player response history
- NPC reputation/favor system

---

## 4. DATABASE CONNECTION & PERFORMANCE

### Issues Identified

#### 🔴 **Critical: Excessive Connection Pool Size**
**Location:** `PostgreSQLlogic.py` line 23

```python
self.pool = await asyncpg.create_pool(self.dsn, max_size=99)  # Too high!
```

**Recommendation:**
- Default PostgreSQL `max_connections` is typically 100
- Your pool of 99 leaves only 1 connection for admin/maintenance
- Recommended: `max_size=20` for most Discord bots
- Formula: `(max_connections - 10) / expected_concurrent_operations`

```python
self.pool = await asyncpg.create_pool(
    self.dsn, 
    max_size=20,
    min_size=5,
    max_queries=50000,  # Prevent connection leaks
    max_inactive_connection_lifetime=300  # 5 minutes
)
```

#### 🟡 **Moderate: Missing Query Timeout**
No query timeouts set, which can lead to hanging connections.

**Recommendation:**
```python
async def fetch(self, query, *args, timeout=30.0):
    async with self.pool.acquire() as conn:
        return await conn.fetch(query, *args, timeout=timeout)
```

#### 🟡 **Moderate: No Connection Health Checks**
Add periodic health checks to detect stale connections.

**Recommendation:**
```python
async def health_check(self):
    try:
        await self.fetchval("SELECT 1", timeout=5.0)
        return True
    except:
        return False
```

---

## 5. GENERAL SCHEMA IMPROVEMENTS

### Missing Indexes (High Priority)
```sql
-- Player lookups
CREATE INDEX idx_players_discord_id ON players(discord_id);
CREATE INDEX idx_player_data_playerid ON player_data(playerid);

-- Location queries
CREATE INDEX idx_locations_type ON locations(type);
CREATE INDEX idx_paths_from_location ON paths(from_location_id);
CREATE INDEX idx_paths_to_location ON paths(to_location_id);

-- Shop queries
CREATE INDEX idx_shop_items_shop_id ON shop_items(shop_id);
CREATE INDEX idx_shop_transactions_player ON shop_transactions(player_id, transaction_time);

-- Items
CREATE INDEX idx_items_type ON items(type);
CREATE INDEX idx_items_rarity ON items(rarity);
```

### Normalization Opportunities

#### 🟡 **Player Data Table**
Consider splitting `player_data` into:
- `player_stats` (health, mana, stamina, etc.)
- `player_location` (current_location, last_location, etc.)
- `player_economy` (gold_balance, inventory_slots, etc.)

This allows for better indexing and reduces table bloat.

#### 🟡 **Items Table**
Consider adding:
- `item_categories` table for better organization
- `item_attributes` table for extensible attributes
- `item_effects` table for item effects/buffs

---

## 6. FUTURE BOTTLENECKS

### High-Risk Areas

1. **Inventory Queries at Scale**
   - **Risk:** As players accumulate items, `SELECT * FROM inventory WHERE playerid = $1` will slow down
   - **Mitigation:** Add pagination, limit inventory display to first 50 items, use virtual scrolling

2. **Quest JSON Parsing**
   - **Risk:** Parsing JSON on every quest check will become expensive
   - **Mitigation:** Normalize common quest types, cache parsed JSON in Redis/Memory

3. **NPC Dialog Trees**
   - **Risk:** Deep dialog trees with many branches will cause slow queries
   - **Mitigation:** Cache dialog trees, use materialized paths, limit tree depth

4. **Player Stats Views**
   - **Risk:** Complex views with many joins will slow down as data grows
   - **Mitigation:** Materialize views, add computed columns, use caching

5. **Shop Transactions**
   - **Risk:** `shop_transactions` table will grow unbounded
   - **Mitigation:** Archive old transactions, partition by date, add retention policy

### Scalability Recommendations

1. **Add Database Monitoring**
   - Track slow queries (>100ms)
   - Monitor connection pool usage
   - Track table sizes and growth rates

2. **Implement Caching Layer**
   - Cache frequently accessed data (items, NPCs, locations)
   - Use Redis for session data
   - Cache player stats for 30-60 seconds

3. **Add Read Replicas**
   - For read-heavy operations (inventory viewing, stats)
   - Use connection pool routing (read vs write)

4. **Partition Large Tables**
   - Partition `inventory` by `playerid` ranges
   - Partition `shop_transactions` by date
   - Partition `player_quests` by status

5. **Add Database Maintenance Jobs**
   - Vacuum and analyze weekly
   - Reindex monthly
   - Archive old data quarterly

---

## 7. SECURITY CONSIDERATIONS

### 🔴 **Critical: SQL Injection Risk**
**Location:** Multiple files

While using parameterized queries (`$1`, `$2`), ensure:
- No dynamic SQL construction with user input
- All user inputs are validated before queries
- Consider using an ORM or query builder for complex queries

### 🟡 **Moderate: Database Credentials**
**Location:** `main.py` line 46, `get_schema.py` lines 5-10

Database credentials are hardcoded. Move to `.env` file:
```python
DATABASE_DSN = os.getenv('DATABASE_DSN')
```

---

## 8. SUMMARY & PRIORITY ACTIONS

### Immediate (This Week)
1. ✅ Add indexes on `inventory` table (playerid, itemid, isequipped, in_bank)
2. ✅ Reduce connection pool size from 99 to 20
3. ✅ Add indexes on `player_quests` (player_id, status)
4. ✅ Move database credentials to `.env` file

### Short Term (This Month)
1. Add indexes on `dynamic_npcs` (locationid, name)
2. Fix inventory stacking logic to exclude equipped/bank items
3. Add query timeouts to database methods
4. Normalize common quest types (collect, kill, etc.)

### Medium Term (Next 3 Months)
1. Implement caching layer (Redis or in-memory)
2. Add database monitoring and slow query logging
3. Partition large tables (inventory, shop_transactions)
4. Create materialized views for player stats

### Long Term (6+ Months)
1. Consider read replicas for scaling
2. Implement quest prerequisite system
3. Add comprehensive analytics tables
4. Archive old transaction data

---

## 9. CODE QUALITY IMPROVEMENTS

### Database Query Patterns

**Current Issue:** Many queries fetch entire rows when only specific columns are needed.

**Recommendation:**
```python
# Instead of:
await self.db.fetchrow("SELECT * FROM inventory WHERE ...")

# Use:
await self.db.fetchrow("SELECT inventoryid, quantity, isequipped FROM inventory WHERE ...")
```

### Error Handling

**Current Issue:** Some database operations don't handle errors gracefully.

**Recommendation:** Add try-catch blocks and proper error messages:
```python
async def add_item(self, item_id, quantity=1):
    try:
        # ... existing code ...
    except asyncpg.UniqueViolationError:
        return "Item already exists in inventory."
    except asyncpg.ForeignKeyViolationError:
        return "Invalid item ID."
    except Exception as e:
        logging.error(f"Error adding item: {e}")
        return "An error occurred. Please try again later."
```

---

## 10. FINAL RATING BREAKDOWN

| Category | Rating | Notes |
|----------|--------|-------|
| **Schema Design** | 7/10 | Good normalization, but JSON overuse |
| **Indexing** | 4/10 | Critical indexes missing |
| **Connection Management** | 6/10 | Pool too large, no timeouts |
| **Scalability** | 6/10 | Will need optimization as data grows |
| **Security** | 7/10 | Parameterized queries good, credentials need work |
| **Performance** | 6/10 | Will degrade without indexes |
| **Maintainability** | 8/10 | Clean code structure, good separation |

**Overall: 7/10** - Solid foundation with room for optimization.

---

## Conclusion

Your database structure shows good planning and scalability thinking. The main issues are:
1. **Missing indexes** (will cause slowdowns as data grows)
2. **Excessive connection pool** (wasteful and risky)
3. **JSON overuse** (will need normalization for performance)

With the recommended improvements, this structure should scale well to thousands of players. Focus on indexes first, then connection pool, then consider normalizing JSON fields for common quest types.

