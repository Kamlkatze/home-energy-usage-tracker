"""Initial migration

Revision ID: 7fb51c659cf1
Revises: 
Create Date: 2026-09-08 00:00:00.000000

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = '7fb51c659cf1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # create meters table (enum type is created implicitly with the table)
    op.create_table('meters',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('meter_type', postgresql.ENUM('electricity', 'gas', 'water', name='metertype'), nullable=False),
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('unit', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_meters_id'), 'meters', ['id'], unique=False)
    
    # create readings table
    op.create_table('readings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('meter_id', sa.Integer(), nullable=False),
    sa.Column('value', sa.Numeric(precision=10, scale=3), nullable=False),
    sa.Column('reading_date', sa.Date(), nullable=False),
    sa.Column('note', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['meter_id'], ['meters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('meter_id', 'reading_date', name='uq_meter_reading_date')
    )
    op.create_index(op.f('ix_readings_id'), 'readings', ['id'], unique=False)
    
    # create tariff_periods table
    op.create_table('tariff_periods',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('meter_id', sa.Integer(), nullable=False),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_to', sa.Date(), nullable=True),
    sa.Column('price_per_unit', sa.Numeric(precision=10, scale=5), nullable=False),
    sa.Column('base_fee_monthly', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['meter_id'], ['meters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('meter_id', 'valid_from', name='uq_meter_valid_from')
    )
    op.create_index(op.f('ix_tariff_periods_id'), 'tariff_periods', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tariff_periods_id'), table_name='tariff_periods')
    op.drop_table('tariff_periods')
    op.drop_index(op.f('ix_readings_id'), table_name='readings')
    op.drop_table('readings')
    op.drop_index(op.f('ix_meters_id'), table_name='meters')
    # enum type is dropped implicitly with the meters table
    op.drop_table('meters')
