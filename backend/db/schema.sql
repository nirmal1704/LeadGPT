-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Users (mirror of Supabase Auth)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Scraping Jobs
CREATE TABLE IF NOT EXISTS scraping_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    objective TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    current_stage TEXT NOT NULL DEFAULT 'queued',
    leads_found_so_far INT NOT NULL DEFAULT 0,
    leads_requested INT NOT NULL DEFAULT 0,
    celery_task_id TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Job Logs
CREATE TABLE IF NOT EXISTS job_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES scraping_jobs(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Businesses
CREATE TABLE IF NOT EXISTS businesses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    address TEXT,
    phone TEXT,
    website_url TEXT,
    source_url TEXT,
    domain TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (name, address)
);

CREATE UNIQUE INDEX IF NOT EXISTS businesses_domain_idx
    ON businesses (domain)
    WHERE domain IS NOT NULL;

-- Leads
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES scraping_jobs(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    opportunity_category TEXT,
    opportunity_score INTEGER,
    pitch_angle TEXT,
    is_contacted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Contacts
CREATE TABLE IF NOT EXISTS contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    platform TEXT,
    profile_url TEXT,
    email TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- NOTE: seo_reports and competitor_reports have been moved to
-- SEOGPT/backend/db/schema.sql as of 2026-06-30.
-- They are no longer part of LeadGPT's database schema.

-- Exports
CREATE TABLE IF NOT EXISTS exports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES scraping_jobs(id) ON DELETE CASCADE,
    file_name TEXT,
    file_type TEXT,
    storage_path TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Knowledge Base (semantic memory)
CREATE TABLE IF NOT EXISTS knowledge_base (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content TEXT NOT NULL,
    embedding vector(384),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS knowledge_base_embedding_idx
    ON knowledge_base
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Row Level Security
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraping_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE exports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_own_projects" ON projects
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "users_own_jobs" ON scraping_jobs
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "users_own_job_logs" ON job_logs
    FOR ALL USING (
        job_id IN (SELECT id FROM scraping_jobs WHERE user_id = auth.uid())
    );

CREATE POLICY "users_own_leads" ON leads
    FOR ALL USING (
        job_id IN (SELECT id FROM scraping_jobs WHERE user_id = auth.uid())
    );

CREATE POLICY "users_own_exports" ON exports
    FOR ALL USING (
        job_id IN (SELECT id FROM scraping_jobs WHERE user_id = auth.uid())
    );

-- Semantic memory search function
CREATE OR REPLACE FUNCTION match_knowledge_base(
    query_embedding vector(384),
    similarity_threshold float,
    match_count int,
    max_age_days int
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    metadata JSONB,
    similarity float
)
LANGUAGE sql STABLE
AS $$
    SELECT
        kb.id,
        kb.content,
        kb.metadata,
        1 - (kb.embedding <=> query_embedding) AS similarity
    FROM knowledge_base kb
    WHERE
        kb.created_at >= NOW() - (max_age_days || ' days')::INTERVAL
        AND 1 - (kb.embedding <=> query_embedding) >= similarity_threshold
    ORDER BY kb.embedding <=> query_embedding
    LIMIT match_count;
$$;
