"""Add audit_log table for compliance trail

Revision ID: 003
Revises: 002
Create Date: 2024-06-02 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("actor_id",    sa.String(60),  nullable=False),          # analyst/admin user_id
        sa.Column("actor_role",  sa.String(20),  nullable=False),
        sa.Column("action",      sa.String(80),  nullable=False),          # e.g. "ALERT_UPDATED", "SAR_FILED"
        sa.Column("entity_type", sa.String(30),  nullable=True),           # "alert" | "transaction" | "user"
        sa.Column("entity_id",   sa.String(30),  nullable=True),
        sa.Column("old_value",   JSONB,          nullable=True),
        sa.Column("new_value",   JSONB,          nullable=True),
        sa.Column("ip_address",  sa.String(45),  nullable=True),
        sa.Column("user_agent",  sa.String(255), nullable=True),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    op.create_index("idx_audit_actor",      "audit_log", ["actor_id"])
    op.create_index("idx_audit_entity",     "audit_log", ["entity_type", "entity_id"])
    op.create_index("idx_audit_created_at", "audit_log", ["created_at"])
    op.create_index("idx_audit_action",     "audit_log", ["action"])

    # Add model_version column to risk_scores if not present
    op.add_column(
        "risk_scores",
        sa.Column("feature_version", sa.String(20), nullable=True, server_default="v1"),
    )


def downgrade() -> None:
    op.drop_column("risk_scores", "feature_version")
    op.drop_index("idx_audit_action",     table_name="audit_log")
    op.drop_index("idx_audit_created_at", table_name="audit_log")
    op.drop_index("idx_audit_entity",     table_name="audit_log")
    op.drop_index("idx_audit_actor",      table_name="audit_log")
    op.drop_table("audit_log")
