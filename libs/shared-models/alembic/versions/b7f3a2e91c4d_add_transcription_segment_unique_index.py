"""add transcription segment unique index

Revision ID: b7f3a2e91c4d
Revises: a1b2c3d4e5f6
Create Date: 2026-03-23

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b7f3a2e91c4d'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Partial unique index required by TC's ON CONFLICT upsert:
    #   INSERT ... ON CONFLICT (meeting_id, segment_id) WHERE segment_id IS NOT NULL
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_transcription_meeting_segment
        ON transcriptions (meeting_id, segment_id)
        WHERE segment_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transcription_meeting_segment")
