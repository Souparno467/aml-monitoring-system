"""Add graph_nodes, graph_edges, and performance indexes

Revision ID: 002
Revises: 001
Create Date: 2024-06-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── graph_nodes ───────────────────────────────────────────────────────────
    op.create_table(
        "graph_nodes",
        sa.Column("user_id",                 sa.String(20),     primary_key=True),
        sa.Column("out_degree",              sa.Integer(),      nullable=True, server_default="0"),
        sa.Column("in_degree",               sa.Integer(),      nullable=True, server_default="0"),
        sa.Column("betweenness_centrality",  sa.Numeric(12, 8), nullable=True),
        sa.Column("pagerank",                sa.Numeric(14, 10),nullable=True),
        sa.Column("clustering_coefficient",  sa.Numeric(12, 8), nullable=True),
        sa.Column("is_hub",                  sa.Boolean(),      nullable=True, server_default="false"),
        sa.Column("computed_at",             sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
    )

    # ── graph_edges ───────────────────────────────────────────────────────────
    op.create_table(
        "graph_edges",
        sa.Column("id",                   sa.BigInteger(),   primary_key=True, autoincrement=True),
        sa.Column("source",               sa.String(20),     nullable=False),
        sa.Column("target",               sa.String(20),     nullable=False),
        sa.Column("txn_id",               sa.String(20),     nullable=True),
        sa.Column("weight",               sa.Numeric(18, 4), nullable=True),
        sa.Column("composite_risk_score", sa.Numeric(5, 4),  nullable=True),
        sa.Column("timestamp",            sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["target"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["txn_id"], ["transactions.txn_id"]),
    )

    # ── Additional performance indexes ────────────────────────────────────────
    op.create_index("idx_graph_edges_source",    "graph_edges", ["source"])
    op.create_index("idx_graph_edges_target",    "graph_edges", ["target"])
    op.create_index("idx_graph_edges_risk",      "graph_edges", ["composite_risk_score"])
    op.create_index("idx_txn_composite_risk",    "transactions", ["composite_risk_score"])
    op.create_index("idx_txn_is_sar",            "transactions", ["is_sar_filed"])
    op.create_index("idx_alerts_created_at",     "alerts",       ["alert_created_at"])
    op.create_index("idx_users_risk_tier",       "users",        ["risk_tier"])
    op.create_index("idx_users_country",         "users",        ["country"])


def downgrade() -> None:
    op.drop_index("idx_users_country",        table_name="users")
    op.drop_index("idx_users_risk_tier",      table_name="users")
    op.drop_index("idx_alerts_created_at",    table_name="alerts")
    op.drop_index("idx_txn_is_sar",           table_name="transactions")
    op.drop_index("idx_txn_composite_risk",   table_name="transactions")
    op.drop_index("idx_graph_edges_risk",     table_name="graph_edges")
    op.drop_index("idx_graph_edges_target",   table_name="graph_edges")
    op.drop_index("idx_graph_edges_source",   table_name="graph_edges")
    op.drop_table("graph_edges")
    op.drop_table("graph_nodes")
