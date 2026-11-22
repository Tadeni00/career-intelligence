"""extraction boundary state (V3.1)

Revision ID: 3f8a91c47d2e
Revises: 7a1c4d2e9b30
Create Date: 2026-10-07 00:00:00.000000

Records the outcome of the last requirement extraction on the job so that a
failed extraction is never mistaken for "this job has no requirements".
NULL means "never extracted"; the zero-requirement guard treats NULL as
unmatchable.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "3f8a91c47d2e"
down_revision = "7a1c4d2e9b30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("extraction_status", sa.String(length=16),
                                    nullable=True))
    op.add_column("jobs", sa.Column("extraction_error_code",
                                    sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "extraction_error_code")
    op.drop_column("jobs", "extraction_status")