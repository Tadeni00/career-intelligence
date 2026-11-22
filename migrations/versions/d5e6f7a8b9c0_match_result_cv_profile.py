"""Add cv_profile_id provenance to match_results.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-10-14 00:00:00.000000

Purely additive. A new nullable column plus its index. No historical row is
read, rewritten, recomputed or deleted: every existing match keeps a NULL
cv_profile_id, which records that its provenance is unknown. No uniqueness
constraint is added, because independent rows per (candidate, job) are what
allow two CV profiles to hold separate results.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'd5e6f7a8b9c0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('match_results', sa.Column('cv_profile_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_match_results_cv_profile_id',
        'match_results',
        'cv_profiles',
        ['cv_profile_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_match_results_cv_profile_id'), 'match_results', ['cv_profile_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_match_results_cv_profile_id'), table_name='match_results')
    op.drop_constraint('fk_match_results_cv_profile_id', 'match_results', type_='foreignkey')
    op.drop_column('match_results', 'cv_profile_id')