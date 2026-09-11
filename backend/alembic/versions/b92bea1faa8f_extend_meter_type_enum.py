"""Extend MeterType enum from 3 generic to 6 specific values

Revision ID: b92bea1faa8f
Revises: 1f8d3205b439
Create Date: 2026-09-09 00:00:00.000000

A PostgreSQL enum type cannot have values removed via ALTER TYPE, so the
change is done by creating a new type, altering the column to use it and
dropping the old type. No data migration is required: no production data
exists yet. If rows with removed enum values were present anyway, the
USING cast would fail loudly instead of silently corrupting data.

Downgrade restores the original 3-value enum (same swap technique).
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b92bea1faa8f'
down_revision = '1f8d3205b439'
branch_labels = None
depends_on = None

ENUM_NAME = 'metertype'
TMP_ENUM_NAME = 'metertype_new'

OLD_VALUES = ('electricity', 'gas', 'water')
NEW_VALUES = (
    'gas',
    'water_cold',
    'water_garden',
    'electricity_import',
    'electricity_export',
    'electricity_production',
)


def _swap_enum(new_values: tuple[str, ...]) -> None:
    """Replace the metertype enum with a new set of values.

    Creates the new type under a temporary name, moves the column over,
    drops the old type and renames the new type to the original name.
    """
    values = ", ".join(f"'{value}'" for value in new_values)
    op.execute(f"CREATE TYPE {TMP_ENUM_NAME} AS ENUM ({values})")
    op.execute(
        f"ALTER TABLE meters ALTER COLUMN meter_type TYPE {TMP_ENUM_NAME} "
        f"USING meter_type::text::{TMP_ENUM_NAME}"
    )
    op.execute(f"DROP TYPE {ENUM_NAME}")
    op.execute(f"ALTER TYPE {TMP_ENUM_NAME} RENAME TO {ENUM_NAME}")


def upgrade() -> None:
    _swap_enum(NEW_VALUES)


def downgrade() -> None:
    _swap_enum(OLD_VALUES)
