-- Add required_quest_id column to locations table if it doesn't exist
-- This allows locations to require completion of a specific quest

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'locations' AND column_name = 'required_quest_id'
    ) THEN
        ALTER TABLE locations 
        ADD COLUMN required_quest_id INTEGER REFERENCES quests(quest_id);
        
        COMMENT ON COLUMN locations.required_quest_id IS 'Quest that must be completed to access this location';
    END IF;
END $$;

