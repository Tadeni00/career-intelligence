"""Add cv_profiles table.

Revision ID: c4d5e6f7a8b9
Revises: a1b2c3d4e5f6
Create Date: 2026-10-14 00:00:00.000000

Purely additive. No existing table is altered and no historical row is read,
rewritten or deleted, so candidates, jobs, requirements, match results,
tailored CVs, cover letters and applications are all left exactly as they were.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'c4d5e6f7a8b9'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'cv_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('cv_id', sa.Integer(), nullable=True),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('file_type', sa.String(length=16), nullable=False),
        sa.Column('storage_path', sa.String(length=1024), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('extracted_data', sa.Text(), nullable=True),
        sa.Column('extracted_issues', sa.Text(), nullable=True),
        sa.Column('confirmed_data', sa.Text(), nullable=True),
        sa.Column('extracted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cv_id'], ['cv_documents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cv_id', name='uq_cv_profiles_cv_id'),
    )
    op.create_index(op.f('ix_cv_profiles_candidate_id'), 'cv_profiles', ['candidate_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_cv_profiles_candidate_id'), table_name='cv_profiles')
    op.drop_table('cv_profiles')