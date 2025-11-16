"""Phase 3: Content Generation and Auto-Posting

Revision ID: 003_phase3
Revises: 002_phase2_carbon_aware_scheduling
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_phase3'
down_revision = '002_phase2'
branch_labels = None
depends_on = None


def upgrade():
    """Add Phase 3 fields to scheduled_posts table."""

    # Add new columns to scheduled_posts
    op.add_column('scheduled_posts',
        sa.Column('posting_job_id', sa.Integer(), sa.ForeignKey('job_queue.id'), nullable=True,
                  comment='Reference to posting job')
    )
    op.add_column('scheduled_posts',
        sa.Column('user_approved', sa.Boolean(), nullable=False, server_default='false',
                  comment='Whether user has approved the generated content')
    )
    op.add_column('scheduled_posts',
        sa.Column('user_edited', sa.Boolean(), nullable=False, server_default='false',
                  comment='Whether user has manually edited the content')
    )
    op.add_column('scheduled_posts',
        sa.Column('auto_post_enabled', sa.Boolean(), nullable=False, server_default='true',
                  comment='Whether to automatically post at scheduled time')
    )

    # Add CANCELLED status to PostStatus enum if not exists
    # Note: This is database-specific. For PostgreSQL:
    op.execute("ALTER TYPE poststatus ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade():
    """Remove Phase 3 fields."""

    op.drop_column('scheduled_posts', 'auto_post_enabled')
    op.drop_column('scheduled_posts', 'user_edited')
    op.drop_column('scheduled_posts', 'user_approved')
    op.drop_column('scheduled_posts', 'posting_job_id')

    # Note: Removing enum values is complex in PostgreSQL and generally not recommended
    # We'll leave the CANCELLED status in place even on downgrade
