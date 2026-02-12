"""trading_service_persistence_tables

Revision ID: 004_trading_service_persistence_tables
Revises: 003_align_trading_schema
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004_trading_service_persistence_tables"
down_revision = "003_align_trading_schema"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return table in set(insp.get_table_names())


def _index_exists(table: str, idx: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return idx in {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    if not _table_exists("risk_incidents"):
        op.create_table(
            "risk_incidents",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("rule_type", sa.Text(), nullable=False),
            sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("actual_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("action_taken", sa.Text(), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        )

    if not _table_exists("trade_audit_log"):
        op.create_table(
            "trade_audit_log",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("event_type", sa.Text(), nullable=False),
            sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        )

    if _table_exists("risk_incidents") and not _index_exists("risk_incidents", "ix_risk_incidents_order_id"):
        op.create_index("ix_risk_incidents_order_id", "risk_incidents", ["order_id"], unique=False)
    if _table_exists("risk_incidents") and not _index_exists("risk_incidents", "ix_risk_incidents_account_id"):
        op.create_index("ix_risk_incidents_account_id", "risk_incidents", ["account_id"], unique=False)
    if _table_exists("trade_audit_log") and not _index_exists("trade_audit_log", "ix_trade_audit_log_order_id"):
        op.create_index("ix_trade_audit_log_order_id", "trade_audit_log", ["order_id"], unique=False)

    if _table_exists("trade_audit_log"):
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')
                   AND NOT EXISTS (
                       SELECT 1
                       FROM timescaledb_information.hypertables
                       WHERE hypertable_schema = current_schema()
                         AND hypertable_name = 'trade_audit_log'
                   ) THEN
                    PERFORM create_hypertable('trade_audit_log', 'created_at', if_not_exists => TRUE);
                END IF;
            END
            $$;
            """
        )
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM timescaledb_information.hypertables
                    WHERE hypertable_schema = current_schema()
                      AND hypertable_name = 'trade_audit_log'
                ) THEN
                    ALTER TABLE trade_audit_log
                        SET (timescaledb.compress = true, timescaledb.compress_segmentby='order_id,event_type');
                END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    if _table_exists("trade_audit_log") and _index_exists("trade_audit_log", "ix_trade_audit_log_order_id"):
        op.drop_index("ix_trade_audit_log_order_id", table_name="trade_audit_log")
    if _table_exists("risk_incidents") and _index_exists("risk_incidents", "ix_risk_incidents_account_id"):
        op.drop_index("ix_risk_incidents_account_id", table_name="risk_incidents")
    if _table_exists("risk_incidents") and _index_exists("risk_incidents", "ix_risk_incidents_order_id"):
        op.drop_index("ix_risk_incidents_order_id", table_name="risk_incidents")

    if _table_exists("trade_audit_log"):
        op.drop_table("trade_audit_log")
    if _table_exists("risk_incidents"):
        op.drop_table("risk_incidents")
