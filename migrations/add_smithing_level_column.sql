-- Add smithing_level column to players table if it doesn't exist
ALTER TABLE players
ADD COLUMN IF NOT EXISTS smithing_level INTEGER DEFAULT 1;

-- Create index for faster smithing level lookups
CREATE INDEX IF NOT EXISTS idx_players_smithing_level ON players(smithing_level);

