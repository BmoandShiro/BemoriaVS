-- Update location to use numeric shop_id
UPDATE locations 
SET shop_id = 1 
WHERE name = 'Blacksmith''s Workshop';

-- Insert blacksmith items
INSERT INTO shop_items (itemid, shop_id, price, quantity) 
SELECT 
    i.itemid,
    1 as shop_id,
    CASE 
        WHEN i.type = 'weapon' THEN i.base_price * 2
        WHEN i.type = 'armor' THEN i.base_price * 1.8
        ELSE i.base_price * 1.5
    END as price,
    10 as quantity
FROM items i
WHERE i.type IN ('weapon', 'armor', 'material')
    AND i.rarity IN ('common', 'uncommon')
ON CONFLICT (itemid, shop_id, is_player_sold) DO UPDATE
SET price = EXCLUDED.price,
    quantity = EXCLUDED.quantity;

-- Setup blacksmith quest
INSERT INTO quests (quest_id, title, description, required_level, reward_gold, reward_xp)
VALUES (
    'blacksmith_intro',
    'The Blacksmith''s Request',
    'Help the local blacksmith gather materials for a special order.',
    1,
    100,
    50
) ON CONFLICT (quest_id) DO NOTHING;

-- Setup quest requirements
INSERT INTO quest_requirements (quest_id, requirement_type, requirement_id, quantity)
VALUES 
    ('blacksmith_intro', 'visit_shop', '1', 1),
    ('blacksmith_intro', 'item', 'iron_ore', 5)
ON CONFLICT (quest_id, requirement_type, requirement_id) DO NOTHING; 