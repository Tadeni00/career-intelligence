"""Widen discovered job identifier columns.

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-10-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'g8b9c0d1e2f3'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # JSearch provider ids observed live are ~200 base64 characters, which
    # String(128) truncates at INSERT. external_id carries the same id plus a
    # provider prefix, so both get the same headroom.
    op.alter_column('jobs', 'source_id',
                    existing_type=sa.String(length=128),
                    type_=sa.String(length=512),
                    existing_nullable=True)
    op.alter_column('jobs', 'external_id',
                    existing_type=sa.String(length=256),
                    type_=sa.String(length=512),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column('jobs', 'external_id',
                    existing_type=sa.String(length=512),
                    type_=sa.String(length=256),
                    existing_nullable=True)
    op.alter_column('jobs', 'source_id',
                    existing_type=sa.String(length=512),
                    type_=sa.String(length=128),
                    existing_nullable=True)
