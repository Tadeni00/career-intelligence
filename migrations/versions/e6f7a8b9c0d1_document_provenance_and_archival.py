"""Document provenance (TailoredCV, CoverLetter) and profile archival.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-10-14 00:00:00.000000

Additive apart from one deliberate foreign-key change.

Additive:
  - cv_profiles.archived_at                 (soft retirement)
  - tailored_cvs.cv_profile_id             (nullable provenance)
  - cover_letters.cv_profile_id            (nullable provenance)

Deliberate change:
  - match_results.cv_profile_id moves from ON DELETE SET NULL to ON DELETE
    RESTRICT.

    Reason: a NULL cv_profile_id means "calculated from the shared Candidate
    record". Under SET NULL, deleting a profile would null the column on all of
    its matches, permanently and invisibly relabelling profile-specific results
    as legacy ones. RESTRICT refuses the deletion instead, and the supported way
    to retire a profile is archival, which preserves provenance.

    Consequence, covered by tests: a profile with dependent history cannot be
    hard-deleted, and its matches, tailored CVs and cover letters keep their
    profile identifier.

No historical row is read, rewritten, recomputed or deleted. Existing tailored
CVs and cover letters keep cv_profile_id = NULL, which records honestly that
their provenance is unknown. No profile identifier is ever back-filled.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'e6f7a8b9c0d1'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- profile archival -------------------------------------------------
    op.add_column(
        'cv_profiles', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True)
    )

    # --- document provenance ---------------------------------------------
    op.add_column(
        'tailored_cvs', sa.Column('cv_profile_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_tailored_cvs_cv_profile_id',
        'tailored_cvs',
        'cv_profiles',
        ['cv_profile_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    op.create_index(
        op.f('ix_tailored_cvs_cv_profile_id'), 'tailored_cvs', ['cv_profile_id'], unique=False
    )

    op.add_column(
        'cover_letters', sa.Column('cv_profile_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_cover_letters_cv_profile_id',
        'cover_letters',
        'cv_profiles',
        ['cv_profile_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    op.create_index(
        op.f('ix_cover_letters_cv_profile_id'), 'cover_letters', ['cv_profile_id'], unique=False
    )

    # --- provenance must not be erased by deleting a profile -------------
    op.drop_constraint('fk_match_results_cv_profile_id', 'match_results', type_='foreignkey')
    op.create_foreign_key(
        'fk_match_results_cv_profile_id',
        'match_results',
        'cv_profiles',
        ['cv_profile_id'],
        ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint('fk_match_results_cv_profile_id', 'match_results', type_='foreignkey')
    op.create_foreign_key(
        'fk_match_results_cv_profile_id',
        'match_results',
        'cv_profiles',
        ['cv_profile_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.drop_index(op.f('ix_cover_letters_cv_profile_id'), table_name='cover_letters')
    op.drop_constraint('fk_cover_letters_cv_profile_id', 'cover_letters', type_='foreignkey')
    op.drop_column('cover_letters', 'cv_profile_id')
    op.drop_index(op.f('ix_tailored_cvs_cv_profile_id'), table_name='tailored_cvs')
    op.drop_constraint('fk_tailored_cvs_cv_profile_id', 'tailored_cvs', type_='foreignkey')
    op.drop_column('tailored_cvs', 'cv_profile_id')
    op.drop_column('cv_profiles', 'archived_at')