"""Application and strategy provenance.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-10-14 00:00:00.000000

Purely additive: one nullable column and index on each of application_strategies
and applications. No constraint is added, altered or removed.

In particular:
  * uq_candidate_job_app (UNIQUE (candidate_id, job_id)) is retained untouched.
    An application is one person's pursuit of one vacancy; two CV profiles
    assessing the same vacancy must not create two application rows.
  * application_strategies keeps its free-form revision chain. Scoping strategy
    history by cv_profile_id is done in the retrieval helpers, not by a
    constraint, so no existing strategy version is ever overwritten or deleted.

No historical row is read, rewritten or recomputed. Every existing strategy and
application keeps cv_profile_id = NULL, which records honestly that its
provenance is unknown. No identifier is ever back-filled.

RESTRICT matches the Task 36 profile lifecycle: archival retires a profile,
hard deletion is refused, and a null here can never be produced by deleting one.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'f7a8b9c0d1e2'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'application_strategies', sa.Column('cv_profile_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_application_strategies_cv_profile_id',
        'application_strategies',
        'cv_profiles',
        ['cv_profile_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    op.create_index(
        op.f('ix_application_strategies_cv_profile_id'),
        'application_strategies',
        ['cv_profile_id'],
        unique=False,
    )

    op.add_column(
        'applications', sa.Column('cv_profile_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_applications_cv_profile_id',
        'applications',
        'cv_profiles',
        ['cv_profile_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    op.create_index(
        op.f('ix_applications_cv_profile_id'),
        'applications',
        ['cv_profile_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_applications_cv_profile_id'), table_name='applications')
    op.drop_constraint('fk_applications_cv_profile_id', 'applications', type_='foreignkey')
    op.drop_column('applications', 'cv_profile_id')
    op.drop_index(
        op.f('ix_application_strategies_cv_profile_id'),
        table_name='application_strategies',
    )
    op.drop_constraint(
        'fk_application_strategies_cv_profile_id',
        'application_strategies',
        type_='foreignkey',
    )
    op.drop_column('application_strategies', 'cv_profile_id')