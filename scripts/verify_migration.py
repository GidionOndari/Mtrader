#!/usr/bin/env python3
import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--environment', default='development')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    dsn = os.getenv('MIGRATION_TEST_DSN') or os.getenv('DATABASE_URL')
    if args.dry_run:
        print('dry-run ok')
        return 0

    import psycopg2 as psycopg

    if not dsn:
        print('Missing DSN')
        return 1

    required_tables = {'ticks','ohlcv','trades','orders','positions','economic_events'}
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            tables = {r[0] for r in cur.fetchall()}
            missing = required_tables - tables
            if missing:
                print('Missing tables:', ','.join(sorted(missing)))
                return 1
            cur.execute("SELECT hypertable_name FROM timescaledb_information.hypertables")
            hypertables = {r[0] for r in cur.fetchall()}
            if not {'ticks','ohlcv','trades','orders','positions'}.issubset(hypertables):
                print('Missing hypertables')
                return 1
    print('migration verification ok')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
