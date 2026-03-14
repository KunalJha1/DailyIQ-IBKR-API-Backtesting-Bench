"""
DailyIQ Backtesting Bench — Assign User Role

Assign a tier (admin, pro, free) to a user by email address.

Usage:
    python assign_role.py user@example.com           # defaults to admin
    python assign_role.py user@example.com pro        # assigns pro
    python assign_role.py user@example.com free       # downgrades to free
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

VALID_TIERS = ("free", "pro", "admin")


def main():
    if len(sys.argv) < 2:
        print("Usage: python assign_role.py <email> [tier]")
        print("  tier: admin (default), pro, free")
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    tier = sys.argv[2].strip().lower() if len(sys.argv) > 2 else "admin"

    if tier not in VALID_TIERS:
        print(f"ERROR: Invalid tier '{tier}'. Must be one of: {', '.join(VALID_TIERS)}")
        sys.exit(1)

    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
    except psycopg2.OperationalError as e:
        print(f"ERROR: Could not connect to database.\n{e}")
        sys.exit(1)

    cur = conn.cursor()

    # Look up user by email in auth.users
    cur.execute("SELECT id, email FROM auth.users WHERE email = %s", (email,))
    row = cur.fetchone()

    if not row:
        print(f"ERROR: No user found with email '{email}'")
        cur.close()
        conn.close()
        sys.exit(1)

    user_id = row[0]

    # Update tier in dailyiq.user_profiles (upsert in case profile doesn't exist yet)
    cur.execute(
        """
        INSERT INTO dailyiq.user_profiles (id, display_name, tier)
        VALUES (%s, split_part(%s, '@', 1), %s)
        ON CONFLICT (id) DO UPDATE SET tier = EXCLUDED.tier
        """,
        (user_id, email, tier),
    )

    print(f"Done. {email} -> {tier}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
