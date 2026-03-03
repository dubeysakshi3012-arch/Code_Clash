"""add match_submissions

Revision ID: add_match_submissions
Revises: add_matches_pvp
Create Date: 2026-02-05 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_match_submissions'
down_revision = 'add_matches_pvp'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'match_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('match_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('answer_type', sa.String(length=50), nullable=False),
        sa.Column('answer_data', sa.Text(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_match_submissions_id'), 'match_submissions', ['id'], unique=False)
    op.create_index(op.f('ix_match_submissions_match_id'), 'match_submissions', ['match_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_match_submissions_match_id'), table_name='match_submissions')
    op.drop_index(op.f('ix_match_submissions_id'), table_name='match_submissions')
    op.drop_table('match_submissions')
