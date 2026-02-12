"""timescale trading core hardened migration"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_timescale_trading_core"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    op.execute('CREATE EXTENSION IF NOT EXISTS "timescaledb";')

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS broker_accounts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            broker_name TEXT NOT NULL,
            account_login TEXT NOT NULL,
            server TEXT NOT NULL,
            environment TEXT NOT NULL,
            encrypted_credentials BYTEA NOT NULL,
            credentials_nonce BYTEA NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (user_id, account_login, server)
        );
        """
    )

    tables = {
        "ticks": "time TIMESTAMPTZ NOT NULL, symbol TEXT NOT NULL, bid DOUBLE PRECISION NOT NULL, ask DOUBLE PRECISION NOT NULL, volume BIGINT NOT NULL DEFAULT 0, provider TEXT NOT NULL",
        "ohlcv": "time TIMESTAMPTZ NOT NULL, symbol TEXT NOT NULL, timeframe TEXT NOT NULL, open DOUBLE PRECISION NOT NULL, high DOUBLE PRECISION NOT NULL, low DOUBLE PRECISION NOT NULL, close DOUBLE PRECISION NOT NULL, volume BIGINT NOT NULL DEFAULT 0, provider TEXT NOT NULL",
        "trades": "time TIMESTAMPTZ NOT NULL, id UUID PRIMARY KEY DEFAULT gen_random_uuid(), account_id UUID REFERENCES broker_accounts(id) ON DELETE CASCADE, symbol TEXT NOT NULL, side TEXT NOT NULL, volume DOUBLE PRECISION NOT NULL, price DOUBLE PRECISION NOT NULL, profit DOUBLE PRECISION NOT NULL DEFAULT 0",
        "economic_events": "time TIMESTAMPTZ NOT NULL, event_id TEXT NOT NULL, provider TEXT NOT NULL, country TEXT NOT NULL, impact TEXT NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb",
        "news_articles": "time TIMESTAMPTZ NOT NULL, article_id TEXT NOT NULL, provider TEXT NOT NULL, headline TEXT NOT NULL, sentiment DOUBLE PRECISION NOT NULL DEFAULT 0, payload JSONB NOT NULL DEFAULT '{}'::jsonb",
        "models": "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name TEXT NOT NULL, version INTEGER NOT NULL, stage TEXT NOT NULL, metrics JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(name,version)",
        "backtest_results": "created_at TIMESTAMPTZ NOT NULL, id UUID PRIMARY KEY DEFAULT gen_random_uuid(), strategy_id UUID, metrics JSONB NOT NULL, equity_curve JSONB NOT NULL",
        "strategies": "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, name TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, dsl JSONB NOT NULL, status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(user_id,name,version)",
        "orders": "opened_at TIMESTAMPTZ NOT NULL, id UUID PRIMARY KEY DEFAULT gen_random_uuid(), client_order_id TEXT UNIQUE, account_id UUID REFERENCES broker_accounts(id) ON DELETE CASCADE, strategy_id UUID REFERENCES strategies(id) ON DELETE SET NULL, model_id UUID REFERENCES models(id) ON DELETE SET NULL, symbol TEXT NOT NULL, side TEXT NOT NULL, order_type TEXT NOT NULL, quantity DOUBLE PRECISION NOT NULL, filled_quantity DOUBLE PRECISION NOT NULL DEFAULT 0, status TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "positions": "opened_at TIMESTAMPTZ NOT NULL, id UUID PRIMARY KEY DEFAULT gen_random_uuid(), account_id UUID REFERENCES broker_accounts(id) ON DELETE CASCADE, symbol TEXT NOT NULL, side TEXT NOT NULL, quantity DOUBLE PRECISION NOT NULL, entry_price DOUBLE PRECISION NOT NULL, price_current DOUBLE PRECISION, profit DOUBLE PRECISION NOT NULL DEFAULT 0, closed_at TIMESTAMPTZ, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "risk_incidents": "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), rule_type TEXT NOT NULL, parameters JSONB NOT NULL, actual_values JSONB NOT NULL, order_id TEXT, account_id TEXT, action_taken TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    }

    for t, ddl in tables.items():
        op.execute(f"CREATE TABLE IF NOT EXISTS {t} ({ddl});")

    hypertables = [
        ("ticks", "time", "7 days"),
        ("ohlcv", "time", "30 days"),
        ("trades", "time", "30 days"),
        ("economic_events", "time", "30 days"),
        ("news_articles", "time", "7 days"),
        ("backtest_results", "created_at", "30 days"),
        ("orders", "opened_at", "30 days"),
        ("positions", "opened_at", "30 days"),
    ]
    for name, col, chunk in hypertables:
        op.execute(
            f"SELECT create_hypertable('{name}','{col}',if_not_exists=>TRUE,chunk_time_interval=>INTERVAL '{chunk}');"
        )

    op.execute("ALTER TABLE ticks SET (timescaledb.compress, timescaledb.compress_segmentby='symbol,provider');")
    op.execute("ALTER TABLE ohlcv SET (timescaledb.compress, timescaledb.compress_segmentby='symbol,timeframe');")
    op.execute("ALTER TABLE trades SET (timescaledb.compress, timescaledb.compress_segmentby='account_id,symbol');")
    op.execute("SELECT add_compression_policy('ticks', INTERVAL '1 day', if_not_exists=>TRUE);")
    op.execute("SELECT add_compression_policy('ohlcv', INTERVAL '7 days', if_not_exists=>TRUE);")
    op.execute("SELECT add_compression_policy('trades', INTERVAL '30 days', if_not_exists=>TRUE);")

    op.execute("SELECT add_drop_chunks_policy('ticks', INTERVAL '7 days', if_not_exists=>TRUE);")
    op.execute("SELECT add_drop_chunks_policy('ohlcv', INTERVAL '2 years', if_not_exists=>TRUE);")
    op.execute("SELECT add_drop_chunks_policy('news_articles', INTERVAL '90 days', if_not_exists=>TRUE);")

    index_sql = [
        "CREATE INDEX IF NOT EXISTS ix_broker_accounts_user_id ON broker_accounts(user_id);",
        "CREATE INDEX IF NOT EXISTS ix_ticks_symbol_time ON ticks(symbol,time DESC);",
        "CREATE INDEX IF NOT EXISTS ix_ohlcv_symbol_tf_time ON ohlcv(symbol,timeframe,time DESC);",
        "CREATE INDEX IF NOT EXISTS ix_trades_account_time ON trades(account_id,time DESC);",
        "CREATE INDEX IF NOT EXISTS ix_trades_symbol_time ON trades(symbol,time DESC);",
        "CREATE INDEX IF NOT EXISTS ix_events_country_impact_time ON economic_events(country,impact,time DESC);",
        "CREATE INDEX IF NOT EXISTS ix_news_provider_time ON news_articles(provider,time DESC);",
        "CREATE INDEX IF NOT EXISTS ix_orders_account_status_opened ON orders(account_id,status,opened_at DESC);",
        "CREATE INDEX IF NOT EXISTS ix_positions_account_symbol_opened ON positions(account_id,symbol,opened_at DESC);",
        "CREATE INDEX IF NOT EXISTS ix_backtest_created ON backtest_results(created_at DESC);",
    ]
    for sql in index_sql:
        op.execute(sql)


def downgrade() -> None:
    drop_order = [
        "risk_incidents",
        "positions",
        "orders",
        "backtest_results",
        "news_articles",
        "economic_events",
        "trades",
        "ohlcv",
        "ticks",
        "models",
        "strategies",
        "broker_accounts",
    ]
    for t in drop_order:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE;")
