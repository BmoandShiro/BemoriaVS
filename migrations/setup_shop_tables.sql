-- Add base_value column to items table if it doesn't exist
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'items' 
        AND column_name = 'base_value'
    ) THEN
        ALTER TABLE items 
        ADD COLUMN base_value INTEGER NOT NULL DEFAULT 50;
    END IF;
END $$;

-- Add shop_id column to locations if it doesn't exist
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'locations' 
        AND column_name = 'shop_id'
    ) THEN
        ALTER TABLE locations 
        ADD COLUMN shop_id INTEGER REFERENCES shop_config(shop_id);
    END IF;
END $$;

-- Create shop configuration table
CREATE TABLE IF NOT EXISTS shop_config (
    shop_id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    shop_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert shop configurations
INSERT INTO shop_config (shop_id, name, description, shop_type) VALUES
(1, 'Blacksmith', 'A forge for crafting and purchasing weapons and armor', 'blacksmith'),
(2, 'General Store', 'A store that sells various goods and supplies', 'general'),
(3, 'Magic Shop', 'A mystical shop selling magical items and reagents', 'magic'),
(4, 'Adventurer''s Guild Shop', 'Special equipment for guild members', 'guild')
ON CONFLICT (shop_id) DO NOTHING;

-- Create shop items table
CREATE TABLE IF NOT EXISTS shop_items (
    itemid INTEGER REFERENCES items(itemid),
    shop_id INTEGER REFERENCES shop_config(shop_id),
    price INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    is_player_sold BOOLEAN DEFAULT false,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (itemid, shop_id, is_player_sold)
);

-- Create shop transactions table
CREATE TABLE IF NOT EXISTS shop_transactions (
    transaction_id SERIAL PRIMARY KEY,
    shop_id INTEGER REFERENCES shop_config(shop_id),
    player_id BIGINT REFERENCES players(player_id),
    itemid INTEGER REFERENCES items(itemid),
    quantity INTEGER NOT NULL,
    total_price INTEGER NOT NULL,
    transaction_type VARCHAR(10) CHECK (transaction_type IN ('buy', 'sell')),
    transaction_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create shop_item_rules table if it doesn't exist
CREATE TABLE IF NOT EXISTS shop_item_rules (
    shop_id INTEGER,
    itemid INTEGER,
    custom_buy_price INTEGER,              -- Fixed buying price, overrides dynamic pricing
    custom_sell_price INTEGER,             -- Fixed selling price, overrides dynamic pricing
    markup_rate DECIMAL(5,2),              -- Custom markup rate for this item
    sell_rate DECIMAL(5,2),                -- Custom sell rate for this item
    min_price INTEGER,                     -- Minimum allowed price
    max_price INTEGER,                     -- Maximum allowed price
    quantity_affects_price BOOLEAN DEFAULT true,
    PRIMARY KEY (shop_id, itemid),
    FOREIGN KEY (shop_id) REFERENCES shop_config(shop_id),
    FOREIGN KEY (itemid) REFERENCES items(itemid)
);

-- Insert general store configuration
INSERT INTO shop_config (shop_id, default_markup_rate, default_sell_rate, description) 
VALUES (2, 0.20, 0.75, 'General Store')
ON CONFLICT (shop_id) DO NOTHING;

-- Update Merchants Square location to have the general store
UPDATE locations 
SET shop_id = 2
WHERE name = 'Merchants Square';

-- Insert items into general store using base_value from items table
INSERT INTO shop_items (shop_id, itemid, quantity, is_player_sold)
SELECT 
    'general_store',
    itemid,
    50,  -- Default quantity
    false
FROM items
WHERE itemid IN (
    -- Add specific itemids for the general store
    -- Example: SELECT itemid FROM items WHERE type IN ('tool', 'resource', 'consumable')
    -- For now, you'll need to specify the actual itemids you want
)
ON CONFLICT (shop_id, itemid, is_player_sold) DO NOTHING;

-- Example: Set up specific rules for certain items in Dave's Fishery
INSERT INTO shop_item_rules (shop_id, itemid, markup_rate, min_price) 
SELECT 
    'daves_fishery',
    itemid,
    0.40,  -- 40% markup on fish
    100    -- Minimum price of 100 gold
FROM items 
WHERE itemid IN (
    -- Add specific itemids for fish items
    -- Example: SELECT itemid FROM items WHERE type = 'fish'
    -- For now, you'll need to specify the actual itemids you want
)
ON CONFLICT (shop_id, itemid) DO NOTHING; 