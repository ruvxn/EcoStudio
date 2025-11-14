"""phase2_carbon_aware_scheduling

Revision ID: 002_phase2
Revises:
Create Date: 2025-11-13

Adds Phase 2 carbon-aware scheduling tables and fields:
- green_windows table for storing optimal execution windows
- carbon_savings table for tracking environmental impact
- system_config table for dynamic configuration
- Additional fields in job_queue for carbon optimization
- is_renewable_high field in carbon_forecasts
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_phase2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_renewable_high to carbon_forecasts
    op.add_column('carbon_forecasts',
        sa.Column('is_renewable_high', sa.Boolean(), nullable=True, default=False,
                  comment='True if renewable energy percentage > 70%')
    )

    # Add Phase 2 fields to job_queue
    op.add_column('job_queue',
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=True,
                  comment='Estimated job duration for scheduling (Phase 2)')
    )
    op.add_column('job_queue',
        sa.Column('optimal_window_start', sa.DateTime(timezone=True), nullable=True,
                  comment='Recommended green window start time (Phase 2)')
    )
    op.add_column('job_queue',
        sa.Column('optimal_window_end', sa.DateTime(timezone=True), nullable=True,
                  comment='Recommended green window end time (Phase 2)')
    )
    op.add_column('job_queue',
        sa.Column('carbon_score', sa.Float(), nullable=True,
                  comment='Carbon optimization score 0-1 (Phase 2)')
    )

    # Create green_windows table
    op.create_table('green_windows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('region', sa.String(length=50), nullable=False, comment='Region code (e.g., AU-VIC)'),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False, comment='Start of green window (UTC)'),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False, comment='End of green window (UTC)'),
        sa.Column('avg_carbon_intensity', sa.Integer(), nullable=True, comment='Average carbon intensity during window (gCO2/kWh)'),
        sa.Column('min_carbon_intensity', sa.Integer(), nullable=True, comment='Minimum carbon intensity during window (gCO2/kWh)'),
        sa.Column('renewable_percentage', sa.Float(), nullable=True, comment='Percentage of renewable energy during window'),
        sa.Column('recommendation_score', sa.Float(), nullable=True, comment='Recommendation score (0-1, higher is better)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='When this window was calculated'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_green_windows_time', 'green_windows', ['window_start', 'window_end'])
    op.create_index('idx_green_windows_region_score', 'green_windows', ['region', 'recommendation_score'])
    op.create_index(op.f('ix_green_windows_id'), 'green_windows', ['id'])
    op.create_index(op.f('ix_green_windows_region'), 'green_windows', ['region'])
    op.create_index(op.f('ix_green_windows_window_start'), 'green_windows', ['window_start'])
    op.create_index(op.f('ix_green_windows_window_end'), 'green_windows', ['window_end'])

    # Create carbon_savings table
    op.create_table('carbon_savings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False, comment='Reference to the job that was executed'),
        sa.Column('scheduled_carbon_intensity', sa.Integer(), nullable=False, comment='Actual carbon intensity when job executed (gCO2/kWh)'),
        sa.Column('average_carbon_intensity', sa.Integer(), nullable=True, comment='Average carbon intensity for the time period'),
        sa.Column('baseline_carbon_intensity', sa.Integer(), nullable=True, comment='What carbon intensity would have been without optimization'),
        sa.Column('carbon_saved_grams', sa.Integer(), nullable=True, comment='Grams of CO2 saved by smart scheduling'),
        sa.Column('energy_used_kwh', sa.Float(), nullable=True, comment='Estimated energy consumption of the job (kWh)'),
        sa.Column('calculation_method', sa.String(length=100), nullable=True, comment='Method used to calculate savings'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='When savings were calculated'),
        sa.ForeignKeyConstraint(['job_id'], ['job_queue.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_carbon_savings_id'), 'carbon_savings', ['id'])
    op.create_index(op.f('ix_carbon_savings_job_id'), 'carbon_savings', ['job_id'])

    # Create system_config table
    op.create_table('system_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('config_key', sa.String(length=100), nullable=False, comment='Unique configuration key'),
        sa.Column('config_value', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Configuration value (JSON format for flexibility)'),
        sa.Column('description', sa.String(length=500), nullable=True, comment='Human-readable description of this setting'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='When this config was last updated'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('config_key', name='uix_config_key')
    )
    op.create_index(op.f('ix_system_config_id'), 'system_config', ['id'])
    op.create_index(op.f('ix_system_config_config_key'), 'system_config', ['config_key'])

    # Insert default system configurations
    op.execute("""
        INSERT INTO system_config (config_key, config_value, description) VALUES
        ('carbon_threshold_low', '{"value": 300, "unit": "gCO2/kWh"}', 'Carbon intensity considered low (good for scheduling)'),
        ('carbon_threshold_high', '{"value": 600, "unit": "gCO2/kWh"}', 'Carbon intensity considered high (avoid scheduling)'),
        ('scheduler_enabled', '{"value": true}', 'Enable automatic job scheduling'),
        ('green_window_preference', '{"value": 0.7, "min": 0.0, "max": 1.0}', 'How much to prioritize green windows (0=no preference, 1=only green)'),
        ('default_region', '{"value": "AU-VIC"}', 'Default electricity grid region for carbon data'),
        ('forecast_update_interval_hours', '{"value": 6}', 'How often to fetch new carbon forecasts (hours)')
    """)


def downgrade() -> None:
    # Drop tables
    op.drop_table('system_config')
    op.drop_table('carbon_savings')
    op.drop_table('green_windows')

    # Remove Phase 2 fields from job_queue
    op.drop_column('job_queue', 'carbon_score')
    op.drop_column('job_queue', 'optimal_window_end')
    op.drop_column('job_queue', 'optimal_window_start')
    op.drop_column('job_queue', 'estimated_duration_minutes')

    # Remove is_renewable_high from carbon_forecasts
    op.drop_column('carbon_forecasts', 'is_renewable_high')
