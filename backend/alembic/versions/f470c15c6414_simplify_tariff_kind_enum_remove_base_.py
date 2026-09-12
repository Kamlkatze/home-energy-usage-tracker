"""Simplify tariff_kind enum: remove base_fee and metering_fee, add metering_fee_monthly column

Revision ID: f470c15c6414
Revises: e6a6932b4c88
Create Date: 2026-09-12 08:58:42.614633

PostgreSQL cannot remove enum values directly, so we create a new type with only
the allowed values (consumption, feed_in, self_consumption, wastewater), swap
the column to use the new type, and drop the old type. The casting will fail
loudly if any rows still have tariff_kind='base_fee' or 'metering_fee' (none
expected per maintainer's confirmation). No data migration needed.

Also adds the nullable metering_fee_monthly column for consumption tariffs,
mirroring the existing base_fee_monthly column pattern.
"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = 'f470c15c6414'
down_revision = 'e6a6932b4c88'
branch_labels = None
depends_on = None

ENUM_NAME = 'tariffkind'
TMP_ENUM_NAME = 'tariffkind_new'

OLD_VALUES = (
    'consumption',
    'base_fee',
    'feed_in',
    'self_consumption',
    'metering_fee',
    'wastewater',
)
NEW_VALUES = (
    'consumption',
    'feed_in',
    'self_consumption',
    'wastewater',
)


def _swap_enum(new_values: tuple[str, ...]) -> None:
    """Replace the tariffkind enum with a new set of values.

    Creates the new type under a temporary name, moves the column over,
    drops the old type and renames the new type to the original name.
    """
    values = ", ".join(f"'{value}'" for value in new_values)
    op.execute(f"CREATE TYPE {TMP_ENUM_NAME} AS ENUM ({values})")
    op.execute(
        f"ALTER TABLE tariff_periods ALTER COLUMN tariff_kind TYPE {TMP_ENUM_NAME} "
        f"USING tariff_kind::text::{TMP_ENUM_NAME}"
    )
    op.execute(f"DROP TYPE {ENUM_NAME}")
    op.execute(f"ALTER TYPE {TMP_ENUM_NAME} RENAME TO {ENUM_NAME}")


def upgrade() -> None:
    # 1. Add the metering_fee_monthly column
    op.add_column(
        'tariff_periods',
        sa.Column('metering_fee_monthly', sa.Numeric(precision=10, scale=2), nullable=True)
    )
    
    # 2. Remove base_fee and metering_fee from the enum
    _swap_enum(NEW_VALUES)


def downgrade() -> None:
    # 1. Remove the metering_fee_monthly column
    op.drop_column('tariff_periods', 'metering_fee_monthly')
    
    # 2. Restore the original enum with all values
    _swap_enum(OLD_VALUES)