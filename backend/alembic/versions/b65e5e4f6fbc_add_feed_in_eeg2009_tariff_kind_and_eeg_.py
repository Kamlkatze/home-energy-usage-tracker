"""add feed_in_eeg2009 tariff kind and eeg fields

Revision ID: b65e5e4f6fbc
Revises: d7b063605e01
Create Date: 2026-09-12 20:51:03.689981

Adds feed_in_eeg2009 to the TariffKind enum and the three EEG-specific
nullable columns (eeg_tier1_rate, eeg_tier2_rate, metering_point_fee_yearly)
to tariff_periods.

PostgreSQL cannot add enum values via ALTER TYPE ADD VALUE in a transaction
block that also does DDL, so we use the same swap technique as the previous
enum migrations: create a new type, move the column, drop the old type.
"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = 'b65e5e4f6fbc'
down_revision = 'd7b063605e01'
branch_labels = None
depends_on = None

ENUM_NAME = 'tariffkind'
TMP_ENUM_NAME = 'tariffkind_new'

OLD_VALUES = (
    'consumption',
    'feed_in',
    'self_consumption',
    'wastewater',
)
NEW_VALUES = OLD_VALUES + ('feed_in_eeg2009',)


def _swap_enum(new_values: tuple[str, ...]) -> None:
    values = ", ".join(f"'{value}'" for value in new_values)
    op.execute(f"CREATE TYPE {TMP_ENUM_NAME} AS ENUM ({values})")
    op.execute(
        f"ALTER TABLE tariff_periods ALTER COLUMN tariff_kind TYPE {TMP_ENUM_NAME} "
        f"USING tariff_kind::text::{TMP_ENUM_NAME}"
    )
    op.execute(f"DROP TYPE {ENUM_NAME}")
    op.execute(f"ALTER TYPE {TMP_ENUM_NAME} RENAME TO {ENUM_NAME}")


def upgrade() -> None:
    # 1. Add the three new EEG-specific columns
    op.add_column('tariff_periods', sa.Column('eeg_tier1_rate', sa.Numeric(precision=10, scale=5), nullable=True))
    op.add_column('tariff_periods', sa.Column('eeg_tier2_rate', sa.Numeric(precision=10, scale=5), nullable=True))
    op.add_column('tariff_periods', sa.Column('metering_point_fee_yearly', sa.Numeric(precision=10, scale=2), nullable=True))

    # 2. Add feed_in_eeg2009 to the enum
    _swap_enum(NEW_VALUES)


def downgrade() -> None:
    # 1. Restore the original enum (removes feed_in_eeg2009)
    _swap_enum(OLD_VALUES)

    # 2. Drop the three EEG-specific columns
    op.drop_column('tariff_periods', 'metering_point_fee_yearly')
    op.drop_column('tariff_periods', 'eeg_tier2_rate')
    op.drop_column('tariff_periods', 'eeg_tier1_rate')