"""
DailyIQ Backtesting Bench — Supabase Auth Schema Setup

This script connects to the Supabase PostgreSQL database and creates
the auth-only tables needed for the DailyIQ desktop app. Supabase is
used EXCLUSIVELY for authentication — all other data stays local.

Usage:
    cd init/
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python setup_supabase.py
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

# Load .env from project root
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)

DB_URL = os.getenv("SUPABASE_DB_URL")

if not DB_URL:
    print("ERROR: SUPABASE_DB_URL not found in .env")
    sys.exit(1)


def get_connection():
    """Connect to Supabase PostgreSQL."""
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        print("Connected to Supabase PostgreSQL.")
        return conn
    except psycopg2.OperationalError as e:
        print(f"ERROR: Could not connect to database.\n{e}")
        sys.exit(1)


SCHEMA_SQL = """
-- DailyIQ Backtesting Bench: Auth-only schema
-- This schema extends Supabase Auth with app-specific user metadata.
-- No OHLCV, strategy, or operational data belongs here.

CREATE SCHEMA IF NOT EXISTS dailyiq;

-- User profiles linked to Supabase auth.users
CREATE TABLE IF NOT EXISTS dailyiq.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT,
    tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Optional: Pro-tier backtest result summaries synced from desktop
-- Only lightweight metrics JSON — no raw OHLCV ever uploaded
CREATE TABLE IF NOT EXISTS dailyiq.backtest_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT,
    date_range_start DATE,
    date_range_end DATE,
    metrics JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_backtest_summaries_user
    ON dailyiq.backtest_summaries(user_id);

-- Row-level security: users can only access their own data
ALTER TABLE dailyiq.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE dailyiq.backtest_summaries ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'user_profiles' AND schemaname = 'dailyiq'
        AND policyname = 'users_own_profile'
    ) THEN
        CREATE POLICY users_own_profile ON dailyiq.user_profiles
            FOR ALL USING (id = auth.uid());
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'backtest_summaries' AND schemaname = 'dailyiq'
        AND policyname = 'users_own_summaries'
    ) THEN
        CREATE POLICY users_own_summaries ON dailyiq.backtest_summaries
            FOR ALL USING (user_id = auth.uid());
    END IF;
END $$;

-- Auto-update updated_at on user_profiles
CREATE OR REPLACE FUNCTION dailyiq.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_profiles_updated_at ON dailyiq.user_profiles;
CREATE TRIGGER trg_user_profiles_updated_at
    BEFORE UPDATE ON dailyiq.user_profiles
    FOR EACH ROW EXECUTE FUNCTION dailyiq.update_updated_at();

-- Auto-create user_profiles row on new user signup (email or OAuth)
CREATE OR REPLACE FUNCTION dailyiq.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO dailyiq.user_profiles (id, display_name)
    VALUES (
        NEW.id,
        COALESCE(
            NEW.raw_user_meta_data->>'full_name',
            NEW.raw_user_meta_data->>'name',
            split_part(NEW.email, '@', 1)
        )
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_on_auth_user_created ON auth.users;
CREATE TRIGGER trg_on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION dailyiq.handle_new_user();
"""


def main():
    conn = get_connection()
    cur = conn.cursor()

    print("Running auth schema setup...")
    try:
        cur.execute(SCHEMA_SQL)
        print("Schema created successfully.")
    except psycopg2.Error as e:
        print(f"ERROR executing schema SQL:\n{e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()
        print("Connection closed.")

    print("\nDone. Supabase auth schema is ready.")
    print("Tables created in 'dailyiq' schema:")
    print("  - dailyiq.user_profiles (linked to auth.users)")
    print("  - dailyiq.backtest_summaries (Pro-tier cloud sync)")


if __name__ == "__main__":
    main()
