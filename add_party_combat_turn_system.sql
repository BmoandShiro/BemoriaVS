-- Add turn tracking columns to battle_instances table
ALTER TABLE battle_instances 
ADD COLUMN IF NOT EXISTS current_turn_player_id INTEGER REFERENCES players(playerid),
ADD COLUMN IF NOT EXISTS turn_order INTEGER[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS turn_number INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS phase VARCHAR(20) DEFAULT 'player_turn' CHECK (phase IN ('player_turn', 'enemy_turn', 'ended'));

-- Create index for faster turn lookups
CREATE INDEX IF NOT EXISTS idx_battle_instances_current_turn ON battle_instances(instance_id, current_turn_player_id) WHERE is_active = true;

