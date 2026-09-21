"""add_category_to_advance_payments

Revision ID: 60757ca5eeef
Revises: b65e5e4f6fbc
Create Date: 2026-09-18 18:30:35.074102

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '60757ca5eeef'
down_revision = 'b65e5e4f6fbc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Create the enum type for category (lowercase values match
    # the meter_type values, making the data migration straightforward).
    op.execute(
        "CREATE TYPE advancepaymentcategory AS ENUM "
        "('gas', 'cold_water', 'wastewater', 'power_import')"
    )

    # Step 2: Add category as nullable initially for data migration.
    op.add_column(
        'advance_payments',
        sa.Column(
            'category',
            sa.Enum(
                'gas', 'cold_water', 'wastewater', 'power_import',
                name='advancepaymentcategory',
                create_type=False,
            ),
            nullable=True,
        ),
    )

    # Step 3: Add new FK columns (nullable).
    op.add_column(
        'advance_payments',
        sa.Column('water_cold_meter_id', sa.Integer(), nullable=True),
    )
    op.add_column(
        'advance_payments',
        sa.Column('water_garden_meter_id', sa.Integer(), nullable=True),
    )

    # Step 4: Make meter_id nullable.
    op.alter_column(
        'advance_payments', 'meter_id',
        existing_type=sa.INTEGER(),
        nullable=True,
    )

    # Step 5: Create foreign key constraints for the new columns.
    op.create_foreign_key(
        'fk_advance_payments_water_cold_meter_id',
        'advance_payments', 'meters',
        ['water_cold_meter_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_advance_payments_water_garden_meter_id',
        'advance_payments', 'meters',
        ['water_garden_meter_id'], ['id'],
        ondelete='CASCADE',
    )

    # Step 6: Data migration – fill category based on the linked meter type.
    op.execute(
        """
        UPDATE advance_payments ap
        SET category = m.meter_type::text::advancepaymentcategory
        FROM meters m
        WHERE ap.meter_id = m.id
        """
    )

    # Step 7: Set category NOT NULL now that data is migrated.
    op.alter_column(
        'advance_payments', 'category',
        existing_type=sa.Enum(
            'gas', 'cold_water', 'wastewater', 'power_import',
            name='advancepaymentcategory',
            create_type=False,
        ),
        nullable=False,
    )

    # Step 8: Drop the old EXCLUDE constraint (meter_id-based).
    op.execute(
        "ALTER TABLE advance_payments "
        "DROP CONSTRAINT IF EXISTS excl_advance_payment_no_overlap"
    )

    # Step 9: Add CHECK constraints.
    op.execute(
        """
        ALTER TABLE advance_payments
        ADD CONSTRAINT ck_advance_payment_wastewater
        CHECK (
            NOT (category = 'wastewater')
            OR (meter_id IS NULL AND water_cold_meter_id IS NOT NULL)
        )
        """
    )
    op.execute(
        """
        ALTER TABLE advance_payments
        ADD CONSTRAINT ck_advance_payment_non_wastewater
        CHECK (
            (category = 'wastewater')
            OR (meter_id IS NOT NULL AND water_cold_meter_id IS NULL
                AND water_garden_meter_id IS NULL)
        )
        """
    )

    # Step 10: Enable btree_gist (idempotent – already enabled if any
    # previous migration ran).
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # Step 11: Partial EXCLUDE constraint for non-wastewater:
    # no overlap for same (meter_id, category).
    op.execute(
        """
        ALTER TABLE advance_payments
        ADD CONSTRAINT excl_advance_payment_non_wastewater
        EXCLUDE USING gist (
            meter_id WITH =,
            category WITH =,
            daterange(valid_from, valid_to, '[]') WITH &&
        )
        WHERE (category != 'wastewater')
        """
    )

    # Step 12: Partial EXCLUDE constraint for wastewater:
    # no overlap for same water_cold_meter_id.
    op.execute(
        """
        ALTER TABLE advance_payments
        ADD CONSTRAINT excl_advance_payment_wastewater
        EXCLUDE USING gist (
            water_cold_meter_id WITH =,
            daterange(valid_from, valid_to, '[]') WITH &&
        )
        WHERE (category = 'wastewater')
        """
    )

    # Step 13: Create indexes for the new FK columns.
    op.create_index(
        op.f('ix_advance_payments_water_cold_meter_id'),
        'advance_payments', ['water_cold_meter_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_advance_payments_water_garden_meter_id'),
        'advance_payments', ['water_garden_meter_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_advance_payments_category'),
        'advance_payments', ['category'],
        unique=False,
    )


def downgrade() -> None:
    # Step 1: Drop indexes.
    op.drop_index(
        op.f('ix_advance_payments_category'),
        table_name='advance_payments',
    )
    op.drop_index(
        op.f('ix_advance_payments_water_garden_meter_id'),
        table_name='advance_payments',
    )
    op.drop_index(
        op.f('ix_advance_payments_water_cold_meter_id'),
        table_name='advance_payments',
    )

    # Step 2: Drop EXCLUDE constraints.
    op.execute(
        "ALTER TABLE advance_payments "
        "DROP CONSTRAINT IF EXISTS excl_advance_payment_wastewater"
    )
    op.execute(
        "ALTER TABLE advance_payments "
        "DROP CONSTRAINT IF EXISTS excl_advance_payment_non_wastewater"
    )

    # Step 3: Drop CHECK constraints.
    op.execute(
        "ALTER TABLE advance_payments "
        "DROP CONSTRAINT IF EXISTS ck_advance_payment_wastewater"
    )
    op.execute(
        "ALTER TABLE advance_payments "
        "DROP CONSTRAINT IF EXISTS ck_advance_payment_non_wastewater"
    )

    # Step 4: Recreate the original EXCLUDE constraint.
    op.execute(
        """
        ALTER TABLE advance_payments
        ADD CONSTRAINT excl_advance_payment_no_overlap
        EXCLUDE USING gist (
            meter_id WITH =,
            daterange(valid_from, valid_to, '[]') WITH &&
        )
        """
    )

    # Step 5: Drop foreign key constraints (named).
    op.drop_constraint(
        'fk_advance_payments_water_garden_meter_id',
        'advance_payments', type_='foreignkey',
    )
    op.drop_constraint(
        'fk_advance_payments_water_cold_meter_id',
        'advance_payments', type_='foreignkey',
    )

    # Step 6: Revert meter_id to NOT NULL (must happen before column drops).
    op.alter_column(
        'advance_payments', 'meter_id',
        existing_type=sa.INTEGER(),
        nullable=False,
    )

    # Step 7: Drop columns (order matters – drop FKs before referenced cols).
    op.drop_column('advance_payments', 'water_garden_meter_id')
    op.drop_column('advance_payments', 'water_cold_meter_id')
    op.drop_column('advance_payments', 'category')

    # Step 8: Drop the enum type.
    op.execute("DROP TYPE IF EXISTS advancepaymentcategory")