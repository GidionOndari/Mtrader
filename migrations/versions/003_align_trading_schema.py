"""align trading schema with repository expectations

Revision ID: 003_align_trading_schema
Revises: 002_timescale_trading_core
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_align_trading_schema"
down_revision = "002_timescale_trading_core"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {col["name"] for col in inspector.get_columns(table)}


def _constraint_exists(table: str, constraint: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fks = {fk["name"] for fk in inspector.get_foreign_keys(table)}
    uniques = {uq["name"] for uq in inspector.get_unique_constraints(table)}
    return constraint in fks or constraint in uniques


def _index_exists(table: str, index: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index in {idx["name"] for idx in inspector.get_indexes(table)}


def upgrade() -> None:
    if not _column_exists("orders", "client_order_id"):
        op.add_column("orders", sa.Column("client_order_id", sa.Text(), nullable=False, server_default=""))
    if not _column_exists("orders", "version"):
        op.add_column("orders", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    if not _column_exists("orders", "idempotency_key"):
        op.add_column("orders", sa.Column("idempotency_key", sa.Text(), nullable=True))
    if not _column_exists("orders", "parent_order_id"):
        op.add_column("orders", sa.Column("parent_order_id", postgresql.UUID(as_uuid=True), nullable=True))

    if not _constraint_exists("orders", "fk_orders_parent_order"):
        op.create_foreign_key("fk_orders_parent_order", "orders", "orders", ["parent_order_id"], ["id"])

    if not _column_exists("positions", "version"):
        op.add_column("positions", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    if not _column_exists("positions", "unrealized_pnl"):
        op.add_column("positions", sa.Column("unrealized_pnl", sa.Numeric(10, 2), nullable=True))
    if not _column_exists("positions", "realized_pnl"):
        op.add_column("positions", sa.Column("realized_pnl", sa.Numeric(10, 2), nullable=True))

    if not _constraint_exists("orders", "uq_orders_idempotency_key"):
        op.create_unique_constraint("uq_orders_idempotency_key", "orders", ["idempotency_key"])
    if not _index_exists("orders", "orders_client_order_id_idx"):
        op.create_index("orders_client_order_id_idx", "orders", ["client_order_id"], unique=False)
    if not _index_exists("orders", "orders_idempotency_key_idx"):
        op.create_index("orders_idempotency_key_idx", "orders", ["idempotency_key"], unique=True)
    if not _index_exists("positions", "positions_version_idx"):
        op.create_index("positions_version_idx", "positions", ["version"], unique=False)

    op.execute("ALTER TABLE orders SET (timescaledb.compress_segmentby='account_id,symbol,status,version');")
    op.execute("ALTER TABLE positions SET (timescaledb.compress_segmentby='account_id,symbol,version');")


def downgrade() -> None:
    op.execute("ALTER TABLE orders SET (timescaledb.compress_segmentby='account_id,symbol');")
    op.execute("ALTER TABLE positions SET (timescaledb.compress_segmentby='account_id,symbol');")

    if _index_exists("positions", "positions_version_idx"):
        op.drop_index("positions_version_idx", table_name="positions")
    if _index_exists("orders", "orders_idempotency_key_idx"):
        op.drop_index("orders_idempotency_key_idx", table_name="orders")
    if _index_exists("orders", "orders_client_order_id_idx"):
        op.drop_index("orders_client_order_id_idx", table_name="orders")
    if _constraint_exists("orders", "uq_orders_idempotency_key"):
        op.drop_constraint("uq_orders_idempotency_key", "orders", type_="unique")
    if _constraint_exists("orders", "fk_orders_parent_order"):
        op.drop_constraint("fk_orders_parent_order", "orders", type_="foreignkey")

    if _column_exists("positions", "realized_pnl"):
        op.drop_column("positions", "realized_pnl")
    if _column_exists("positions", "unrealized_pnl"):
        op.drop_column("positions", "unrealized_pnl")
    if _column_exists("positions", "version"):
        op.drop_column("positions", "version")

    if _column_exists("orders", "parent_order_id"):
        op.drop_column("orders", "parent_order_id")
    if _column_exists("orders", "idempotency_key"):
        op.drop_column("orders", "idempotency_key")
    if _column_exists("orders", "version"):
        op.drop_column("orders", "version")
    if _column_exists("orders", "client_order_id"):
        op.drop_column("orders", "client_order_id")
