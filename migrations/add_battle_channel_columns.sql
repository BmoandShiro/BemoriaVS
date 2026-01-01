-- Add channel tracking columns to battle_instances table
ALTER TABLE battle_instances 
ADD COLUMN IF NOT EXISTS channel_id BIGINT,
ADD COLUMN IF NOT EXISTS message_id BIGINT;

