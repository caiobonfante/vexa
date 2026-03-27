"""Add calendar_events table

Revision ID: c8d9e0f1a2b3
Revises: b7f3a2e91c4d
Create Date: 2026-03-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c8d9e0f1a2b3'
down_revision = 'b7f3a2e91c4d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'calendar_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('external_event_id', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('meeting_url', sa.Text(), nullable=True),
        sa.Column('platform', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default='pending'),
        sa.Column('meeting_id', sa.Integer(), nullable=True),
        sa.Column('sync_token', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'external_event_id', name='uq_calendar_event_user_ext_id'),
    )
    op.create_index('ix_calendar_events_id', 'calendar_events', ['id'])
    op.create_index('ix_calendar_events_user_id', 'calendar_events', ['user_id'])
    op.create_index('ix_calendar_events_start_time', 'calendar_events', ['start_time'])
    op.create_index('ix_calendar_events_status', 'calendar_events', ['status'])


def downgrade() -> None:
    op.drop_table('calendar_events')
