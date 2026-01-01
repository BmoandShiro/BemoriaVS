-- Critical Indexes for Performance Optimization
-- Run this script to add essential indexes for inventory, quests, and NPCs

-- ============================================
-- INVENTORY INDEXES (Highest Priority)
-- ============================================

-- Index for checking if item exists in inventory (used in add_item, remove_item)
CREATE INDEX IF NOT EXISTS idx_inventory_playerid_itemid 
    ON inventory(playerid, itemid);

-- Index for counting inventory items (used in capacity checks)
CREATE INDEX IF NOT EXISTS idx_inventory_playerid_equipped_bank 
    ON inventory(playerid, isequipped, in_bank) 
    WHERE isequipped = FALSE AND in_bank = FALSE;

-- Index for slot-based equipment queries
CREATE INDEX IF NOT EXISTS idx_inventory_playerid_slot_equipped 
    ON inventory(playerid, slot, isequipped) 
    WHERE isequipped = TRUE;

-- Index for bank transfers
CREATE INDEX IF NOT EXISTS idx_inventory_playerid_bank 
    ON inventory(playerid, in_bank);

-- ============================================
-- QUEST INDEXES (High Priority)
-- ============================================

-- Index for checking quest status (used frequently in quest handlers)
CREATE INDEX IF NOT EXISTS idx_player_quests_player_status 
    ON player_quests(player_id, status);

-- Index for quest turn-in lookups
CREATE INDEX IF NOT EXISTS idx_player_quests_turnin 
    ON player_quests(player_id, quest_id, status) 
    WHERE status = 'in_progress';

-- Index for checking available quests
CREATE INDEX IF NOT EXISTS idx_quests_turnin_npc 
    ON quests(turn_in_npc_id) 
    WHERE turn_in_npc_id IS NOT NULL;

-- ============================================
-- NPC INDEXES (Medium Priority)
-- ============================================

-- Index for location-based NPC lookups
CREATE INDEX IF NOT EXISTS idx_dynamic_npcs_location 
    ON dynamic_npcs(locationid);

-- Index for case-insensitive NPC name lookups
CREATE INDEX IF NOT EXISTS idx_dynamic_npcs_name_lower 
    ON dynamic_npcs(LOWER(name));

-- Index for dialog tree navigation
CREATE INDEX IF NOT EXISTS idx_dynamic_dialogs_followup 
    ON dynamic_dialogs(follow_up_dialog_id) 
    WHERE follow_up_dialog_id IS NOT NULL;

-- ============================================
-- PLAYER INDEXES (High Priority)
-- ============================================

-- Index for Discord ID lookups (used in get_or_create_player)
CREATE INDEX IF NOT EXISTS idx_players_discord_id 
    ON players(discord_id);

-- Index for player data lookups
CREATE INDEX IF NOT EXISTS idx_player_data_playerid 
    ON player_data(playerid);

-- ============================================
-- LOCATION INDEXES (Medium Priority)
-- ============================================

-- Index for location type queries
CREATE INDEX IF NOT EXISTS idx_locations_type 
    ON locations(type);

-- Index for path lookups (travel system)
CREATE INDEX IF NOT EXISTS idx_paths_from_location 
    ON paths(from_location_id);

CREATE INDEX IF NOT EXISTS idx_paths_to_location 
    ON paths(to_location_id);

-- ============================================
-- SHOP INDEXES (Medium Priority)
-- ============================================

-- Index for shop item lookups
CREATE INDEX IF NOT EXISTS idx_shop_items_shop_id 
    ON shop_items(shop_id);

-- Index for shop transactions
CREATE INDEX IF NOT EXISTS idx_shop_transactions_player_time 
    ON shop_transactions(player_id, transaction_time DESC);

-- ============================================
-- ITEM INDEXES (Low Priority, but helpful)
-- ============================================

-- Index for item type queries
CREATE INDEX IF NOT EXISTS idx_items_type 
    ON items(type);

-- Index for item rarity queries
CREATE INDEX IF NOT EXISTS idx_items_rarity 
    ON items(rarity);

-- ============================================
-- LOCATION COMMANDS INDEXES
-- ============================================

-- Index for location-based command lookups
CREATE INDEX IF NOT EXISTS idx_location_commands_locationid 
    ON location_commands(locationid);

-- ============================================
-- ANALYZE TABLES AFTER INDEX CREATION
-- ============================================

-- Update statistics for query planner
ANALYZE inventory;
ANALYZE player_quests;
ANALYZE quests;
ANALYZE dynamic_npcs;
ANALYZE players;
ANALYZE player_data;
ANALYZE locations;
ANALYZE paths;
ANALYZE shop_items;
ANALYZE shop_transactions;
ANALYZE items;

