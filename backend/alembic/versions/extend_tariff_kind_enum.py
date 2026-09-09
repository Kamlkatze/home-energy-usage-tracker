"""Add 'wastewater' to the TariffKind enum

Revision ID: extend_tariff_kind_enum
Revises: cd75ae9d539a
Create Date: 2026-09-09 00:00:00.000000

A PostgreSQL enum type cannot have values removed via ALTER TYPE, so the
change is done by creating a new type, altering the column to use it and
dropping the old type (same swap technique as extend_meter_type_enum).
No data migration is required: 'wastewater' is only added. Downgrade
restores the original 5-value enum; if rows with tariff_kind='wastewater'
were created meanwhile, the USING cast fails loudly instead of silently
corrupting data.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'extend_tariff_kind_enum'
down_revision = 'cd75ae9d539a'
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
)
NEW_VALUES = OLD_VALUES + ('wastewater',)


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
    _swap_enum(NEW_VALUES)


def downgrade() -> None:
    _swap_enum(OLD_VALUES)
