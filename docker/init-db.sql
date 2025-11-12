-- Initialize EcoTrainer Studio database
-- This script runs when the PostgreSQL container first starts

-- Set timezone to UTC
SET timezone = 'UTC';

-- Create database (if not exists - handled by POSTGRES_DB env var)
-- Additional database setup can be added here

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'EcoTrainer Studio database initialized successfully';
END $$;
