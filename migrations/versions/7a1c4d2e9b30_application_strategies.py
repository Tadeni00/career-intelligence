"""application strategies (V2)

Revision ID: 7a1c4d2e9b30
Revises: 2bcb8c39e5e2
Create Date: 2026-10-07 00:00:00.000000

Persists the V2 Application Strategy: the deterministic interpretation of a
match result over a specific evidence state. Versioned and markable STALE so a
stale strategy is never silently reused.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "7a1c4d2e9b30"
down_revision = "2bcb8c39e5e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_strategies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("status", sa.String(length=16), nullable=True,
                  server_default="CURRENT"),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("decision_summary", sa.Text(), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True, server_default="[]"),
        sa.Column("gaps", sa.Text(), nullable=True, server_default="[]"),
        sa.Column("blockers", sa.Text(), nullable=True, server_default="[]"),
        sa.Column("transferable_evidence", sa.Text(), nullable=True,
                  server_default="[]"),
        sa.Column("evidence_emphasis", sa.Text(), nullable=True, server_default="[]"),
        sa.Column("claim_restrictions", sa.Text(), nullable=True, server_default="[]"),
        sa.Column("actions", sa.Text(), nullable=True, server_default="[]"),
        sa.Column("review_notes", sa.Text(), nullable=True, server_default="[]"),
        sa.Column("evidence_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["match_id"], ["match_results.id"],
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_application_strategies_candidate_id",
                    "application_strategies", ["candidate_id"])
    op.create_index("ix_application_strategies_job_id",
                    "application_strategies", ["job_id"])
    op.create_index("ix_application_strategies_match_id",
                    "application_strategies", ["match_id"])


def downgrade() -> None:
    op.drop_index("ix_application_strategies_match_id",
                  table_name="application_strategies")
    op.drop_index("ix_application_strategies_job_id",
                  table_name="application_strategies")
    op.drop_index("ix_application_strategies_candidate_id",
                  table_name="application_strategies")
    op.drop_table("application_strategies")