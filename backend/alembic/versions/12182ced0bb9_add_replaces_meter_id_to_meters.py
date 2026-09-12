"""add_replaces_meter_id_to_meters

Revision ID: 12182ced0bb9
Revises: c1940f40123e
Create Date: 2026-09-12 19:03:41.942171

Adds a nullable self-referencing foreign key Meter.replaces_meter_id that
records which predecessor meter (if any) the current meter replaced.

This enables the cost-calculation logic to follow the meter replacement
chain and compute consumption correctly across a meter swap without
producing a negative consumption from the new meter's lower start value.

The constraint is NOT enforced at the DB level (no UNIQUE, no CHECK) beyond
the FK – enforcing that a meter is only replaced once is done in application
logic. The FK has ON DELETE SET NULL so that deleting a predecessor meter
does not cascade-delete the successor.
"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '12182ced0bb9'
down_revision = 'c1940f40123e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'meters',
        sa.Column('replaces_meter_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_meters_replaces_meter_id',
        'meters',
        'meters',
        ['replaces_meter_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_meters_replaces_meter_id', 'meters', type_='foreignkey')
    op.drop_column('meters', 'replaces_meter_id')
