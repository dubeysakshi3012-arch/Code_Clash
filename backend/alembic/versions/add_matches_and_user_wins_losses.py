"""add matches and user wins losses

Revision ID: add_matches_pvp
Revises: add_anti_cheat_tables
Create Date: 2026-02-05 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_matches_pvp'
down_revision = 'add_anti_cheat_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('wins', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('losses', sa.Integer(), nullable=False, server_default='0'))

    op.create_table(
        'matches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='waiting'),
        sa.Column('winner_id', sa.Integer(), nullable=True),
        sa.Column('language', sa.String(length=20), nullable=False),
        sa.Column('time_limit_per_question', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('server_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['winner_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_matches_id'), 'matches', ['id'], unique=False)
    op.create_index(op.f('ix_matches_status'), 'matches', ['status'], unique=False)
    op.create_index(op.f('ix_matches_winner_id'), 'matches', ['winner_id'], unique=False)

    op.create_table(
        'match_participants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('match_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('left_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_match_participants_id'), 'match_participants', ['id'], unique=False)
    op.create_index(op.f('ix_match_participants_match_id'), 'match_participants', ['match_id'], unique=False)
    op.create_index(op.f('ix_match_participants_user_id'), 'match_participants', ['user_id'], unique=False)

    op.create_table(
        'match_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('match_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_match_questions_id'), 'match_questions', ['id'], unique=False)
    op.create_index(op.f('ix_match_questions_match_id'), 'match_questions', ['match_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_match_questions_match_id'), table_name='match_questions')
    op.drop_index(op.f('ix_match_questions_id'), table_name='match_questions')
    op.drop_table('match_questions')
    op.drop_index(op.f('ix_match_participants_user_id'), table_name='match_participants')
    op.drop_index(op.f('ix_match_participants_match_id'), table_name='match_participants')
    op.drop_index(op.f('ix_match_participants_id'), table_name='match_participants')
    op.drop_table('match_participants')
    op.drop_index(op.f('ix_matches_winner_id'), table_name='matches')
    op.drop_index(op.f('ix_matches_status'), table_name='matches')
    op.drop_index(op.f('ix_matches_id'), table_name='matches')
    op.drop_table('matches')
    op.drop_column('users', 'losses')
    op.drop_column('users', 'wins')
