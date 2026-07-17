-- =============================================================================
-- LeadGPT Database Migration
-- Run this in the Supabase SQL Editor for an EXISTING database.
-- Safe to run multiple times — every statement uses IF NOT EXISTS / IF EXISTS
-- guards or checks for the column before adding it.
-- For a FRESH database, run backend/db/schema.sql instead of this file.
-- =============================================================================


-- ─── 1. scraping_jobs — add progress-tracking columns ─────────────────────────
--
-- These were added in the Step 2 restructure (2026-06-30).
-- The backend writes current_stage and leads_found_so_far after every agent
-- completes, and leads_requested when the job is first created.

ALTER TABLE scraping_jobs
    ADD COLUMN IF NOT EXISTS current_stage TEXT NOT NULL DEFAULT 'queued';

ALTER TABLE scraping_jobs
    ADD COLUMN IF NOT EXISTS leads_found_so_far INT NOT NULL DEFAULT 0;

ALTER TABLE scraping_jobs
    ADD COLUMN IF NOT EXISTS leads_requested INT NOT NULL DEFAULT 0;


-- ─── 2. leads — rename issue_type → opportunity_category ──────────────────────
--
-- The original schema stored a hard-coded website-health enum in issue_type.
-- The Step 3 rebuild replaced this with a dynamic, per-job category system.
-- opportunity_category holds whatever code the planner assigned for this job
-- (e.g. "no_website", "no_social_presence", "slow_load", or any custom code).
--
-- Only run the RENAME if the old column still exists.
-- If you ran schema.sql fresh (which already has opportunity_category),
-- this block is a no-op because the DO block checks first.

DO $$
BEGIN
    -- Add new column if it doesn't exist yet
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'leads' AND column_name = 'opportunity_category'
    ) THEN
        ALTER TABLE leads ADD COLUMN opportunity_category TEXT;
    END IF;

    -- Copy data from old column if it still exists
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'leads' AND column_name = 'issue_type'
    ) THEN
        UPDATE leads SET opportunity_category = issue_type WHERE opportunity_category IS NULL;
        ALTER TABLE leads DROP COLUMN issue_type;
    END IF;
END $$;


-- ─── 3. Remove seo_reports and competitor_reports tables ──────────────────────
--
-- These were moved to SEOGPT/backend/db/schema.sql on 2026-06-30.
-- The DROP statements are safe — they do nothing if the tables don't exist.
-- If you still need this data, export it before running this migration.

DROP TABLE IF EXISTS competitor_reports CASCADE;
DROP TABLE IF EXISTS seo_reports CASCADE;


-- ─── 4. Verify the result ─────────────────────────────────────────────────────
--
-- After running this migration, the query below should show all expected columns.
-- Copy-paste it separately to confirm — it does not need to be run as part of
-- the migration itself.
--
-- SELECT column_name, data_type, column_default
-- FROM information_schema.columns
-- WHERE table_name IN ('scraping_jobs', 'leads')
-- ORDER BY table_name, ordinal_position;
