"""Initial AML schema

Revision ID: 0001
Revises: None
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(20), primary_key=True),
        sa.Column("account_type", sa.String(20), nullable=False, server_default="Individual"),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("occupation", sa.String(60), nullable=True),
        sa.Column("kyc_level", sa.String(20), nullable=False, server_default="Partial"),
        sa.Column("is_pep", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("account_created_date", sa.Date(), nullable=True),
        sa.Column("last_active_date", sa.Date(), nullable=True),
        sa.Column("dormant_days_before_activation", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("avg_monthly_txn_volume_usd", sa.Numeric(18, 4), nullable=True),
        sa.Column("credit_score", sa.Integer(), nullable=True),
        sa.Column("num_linked_accounts", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("sanctions_hit", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("adverse_media_flag", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("industry", sa.String(80), nullable=True),
        sa.Column("risk_tier", sa.String(20), nullable=False, server_default="LOW"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "transactions",
        sa.Column("txn_id", sa.String(20), primary_key=True),
        sa.Column("sender_id", sa.String(20), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("receiver_id", sa.String(20), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("amount_usd", sa.Numeric(18, 4), nullable=False),
        sa.Column("amount_local", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("fx_rate_to_usd", sa.Numeric(14, 6), nullable=True, server_default="1"),
        sa.Column("payment_method", sa.String(20), nullable=True),
        sa.Column("txn_type", sa.String(30), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hour_of_day", sa.Integer(), nullable=True),
        sa.Column("day_of_week", sa.String(10), nullable=True),
        sa.Column("is_weekend", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("is_cross_border", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("sender_country", sa.String(2), nullable=True),
        sa.Column("receiver_country", sa.String(2), nullable=True),
        sa.Column("transaction_fee_usd", sa.Numeric(12, 4), nullable=True),
        sa.Column("flag_large_transaction", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("flag_high_risk_country", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("flag_pep_involved", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("flag_structuring", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("flag_dormant_account", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("flag_crypto", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("flag_night_transaction", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("flag_round_amount", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("rule_score", sa.Numeric(5, 4), nullable=True, server_default="0"),
        sa.Column("ml_score", sa.Numeric(5, 4), nullable=True, server_default="0"),
        sa.Column("graph_score", sa.Numeric(5, 4), nullable=True, server_default="0"),
        sa.Column("composite_risk_score", sa.Numeric(5, 4), nullable=True, server_default="0"),
        sa.Column("risk_label", sa.String(20), nullable=True, server_default="LOW"),
        sa.Column("pattern_type", sa.String(30), nullable=True, server_default="normal"),
        sa.Column("is_sar_filed", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("status", sa.String(20), nullable=True, server_default="Pending"),
        sa.Column("device_fingerprint", sa.String(32), nullable=True),
        sa.Column("ip_country", sa.String(2), nullable=True),
        sa.Column("channel", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "alerts",
        sa.Column("alert_id", sa.String(20), primary_key=True),
        sa.Column("txn_id", sa.String(20), sa.ForeignKey("transactions.txn_id"), nullable=True),
        sa.Column("user_id", sa.String(20), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("alert_rule", sa.String(60), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True, server_default="MEDIUM"),
        sa.Column("composite_risk_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("rule_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("ml_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("graph_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("alert_created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("alert_resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_time_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("assigned_analyst", sa.String(60), nullable=True),
        sa.Column("alert_status", sa.String(40), nullable=True, server_default="Open"),
        sa.Column("sar_filed", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("false_positive", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "risk_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", sa.String(20), nullable=False),
        sa.Column("rule_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("ml_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("graph_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("final_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("model_version", sa.String(20), nullable=True, server_default="v1"),
    )

    op.create_table(
        "pep_profiles",
        sa.Column("pep_id", sa.String(20), primary_key=True),
        sa.Column("user_id", sa.String(20), nullable=True),
        sa.Column("role", sa.String(80), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("designation_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("risk_weight_multiplier", sa.Numeric(4, 2), nullable=True, server_default="1.5"),
        sa.Column("source", sa.String(60), nullable=True),
        sa.Column("last_verified", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "country_risk",
        sa.Column("country_code", sa.String(2), primary_key=True),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("risk_score_0_100", sa.Numeric(5, 1), nullable=True),
        sa.Column("fatf_greylist", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("fatf_blacklist", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("ofac_sanctions", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("corruption_index", sa.Numeric(5, 1), nullable=True),
        sa.Column("aml_deficiency_flag", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("last_updated", sa.Date(), nullable=True),
    )

    op.create_table(
        "graph_nodes",
        sa.Column("user_id", sa.String(20), sa.ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("out_degree", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("in_degree", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("betweenness_centrality", sa.Numeric(12, 8), nullable=True),
        sa.Column("pagerank", sa.Numeric(14, 10), nullable=True),
        sa.Column("clustering_coefficient", sa.Numeric(12, 8), nullable=True),
        sa.Column("is_hub", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "graph_edges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(20), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("target", sa.String(20), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("txn_id", sa.String(20), sa.ForeignKey("transactions.txn_id"), nullable=True),
        sa.Column("weight", sa.Numeric(18, 4), nullable=True),
        sa.Column("composite_risk_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(60), nullable=False),
        sa.Column("actor_role", sa.String(20), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=True),
        sa.Column("entity_id", sa.String(30), nullable=True),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("graph_edges")
    op.drop_table("graph_nodes")
    op.drop_table("country_risk")
    op.drop_table("pep_profiles")
    op.drop_table("risk_scores")
    op.drop_table("alerts")
    op.drop_table("transactions")
    op.drop_table("users")

