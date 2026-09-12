"""Add tariff_kind and prevent overlapping tariff periods

Revision ID: 1f8d3205b439
Revises: 7fb51c659cf1
Create Date: 2026-09-09 00:00:00.000000

About dropping UNIQUE(meter_id, valid_from) (uq_meter_valid_from):
The new EXCLUDE constraint excl_tariff_period_no_overlap fully covers it:
two rows for the same (meter_id, tariff_kind) with the same valid_from always
overlap, because the lower range bound is inclusive (daterange '[]').
Rows with the same valid_from but DIFFERENT tariff_kind are now deliberately
allowed (parallel price components: consumption price, feed-in tariff, ...),
which the old UNIQUE constraint would have wrongly rejected. Therefore the
UNIQUE constraint is dropped and is NOT recreated in downgrade(): data added
under the new regime may legitimately contain the same valid_from for
different tariff_kind values, so restoring it could fail. It can be re-added
manually after resolving any such rows if ever needed.

btree_gist is NOT dropped in downgrade(): other parts of the schema may depend
on it later, and leaving an unused extension installed is harmless.
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = '1f8d3205b439'
down_revision = '7fb51c659cf1'
branch_labels = None
depends_on = None

TARIFF_KIND_VALUES = (
    'consumption',
    'base_fee',
    'feed_in',
    'self_consumption',
    'metering_fee',
)

# create_type=False: the type is created explicitly below. Unlike
# op.create_table (which creates enum types implicitly via table events),
# op.add_column does not create native enum types by itself.
tariff_kind_enum = postgresql.ENUM(
    *TARIFF_KIND_VALUES,
    name='tariffkind',
    create_type=False,
)


def _conflicting_rows(conn):
    """Find existing rows that overlap within the same (meter_id, tariff_kind).

    NULL valid_to means open-ended (upper bound +infinity); both bounds are
    inclusive, matching daterange(valid_from, valid_to, '[]').
    """
    return conn.execute(sa.text(
        """
        SELECT a.meter_id, a.tariff_kind, a.valid_from, a.valid_to,
               b.id AS other_id,
               b.valid_from AS other_valid_from, b.valid_to AS other_valid_to
        FROM tariff_periods a
        JOIN tariff_periods b
          ON a.meter_id = b.meter_id
         AND a.tariff_kind = b.tariff_kind
         AND a.id < b.id
         AND a.valid_from <= COALESCE(b.valid_to, 'infinity'::date)
         AND b.valid_from <= COALESCE(a.valid_to, 'infinity'::date)
        ORDER BY a.meter_id, a.tariff_kind, a.valid_from
        """
    )).fetchall()


def upgrade() -> None:
    # create the enum type explicitly (see note above on create_type=False)
    tariff_kind_enum.create(op.get_bind(), checkfirst=True)

    # 1. add column with a server_default so existing rows are backfilled
    op.add_column(
        'tariff_periods',
        sa.Column('tariff_kind', tariff_kind_enum, nullable=False,
                  server_default='consumption'),
    )

    # 2. explicit backfill (no-op for rows added under the server_default,
    #    kept as safety net for any rows inserted mid-migration)
    op.execute("UPDATE tariff_periods SET tariff_kind = 'consumption' "
               "WHERE tariff_kind IS NULL")

    # 3. drop the server_default (standard NOT NULL add-column pattern)
    op.alter_column('tariff_periods', 'tariff_kind',
                    existing_type=tariff_kind_enum, server_default=None)

    # 4. refuse to proceed if existing data would violate the new constraint.
    #    STOP here and report the conflicts - never modify or delete data
    #    automatically; a human must decide how to resolve them.
    conn = op.get_bind()
    conflicts = _conflicting_rows(conn)
    if conflicts:
        lines = "\n".join(
            f"  meter_id={row.meter_id}, tariff_kind='{row.tariff_kind}': "
            f"period [{row.valid_from} .. {row.valid_to or 'NULL (open-ended)'}] "
            f"overlaps period [{row.other_valid_from} .. "
            f"{row.other_valid_to or 'NULL (open-ended)'}] (id {row.other_id})"
            for row in conflicts
        )
        raise RuntimeError(
            "Migration aborted: existing tariff_periods rows overlap within the "
            "same (meter_id, tariff_kind) and would violate the constraint "
            "excl_tariff_period_no_overlap. No data was modified.\n"
            "Resolve these conflicts manually, then re-run the migration:\n"
            + lines
        )

    # 5. enable btree_gist (required for scalar equality in EXCLUDE USING gist).
    #    If the DB role lacks the privileges to create extensions, this fails
    #    on purpose - report the exact error, do not work around it.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # 6. drop the now-redundant UNIQUE constraint (see module docstring).
    #    IF EXISTS: after a downgrade (which deliberately does NOT recreate
    #    this constraint) a re-upgrade must still work.
    op.execute("ALTER TABLE tariff_periods "
               "DROP CONSTRAINT IF EXISTS uq_meter_valid_from")

    # 7. prevent overlapping periods within the same (meter_id, tariff_kind);
    #    different tariff_kind values may overlap in time. '[]' = inclusive
    #    bounds on both ends; NULL valid_to -> unbounded upper end, so an
    #    open-ended period conflicts with any later period of the same kind.
    op.execute(
        """
        ALTER TABLE tariff_periods
        ADD CONSTRAINT excl_tariff_period_no_overlap
        EXCLUDE USING gist (
            meter_id WITH =,
            tariff_kind WITH =,
            daterange(valid_from, valid_to, '[]') WITH &&
        )
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE tariff_periods "
               "DROP CONSTRAINT IF EXISTS excl_tariff_period_no_overlap")
    op.drop_column('tariff_periods', 'tariff_kind')
    tariff_kind_enum.drop(op.get_bind(), checkfirst=True)
    # btree_gist intentionally NOT dropped (see module docstring)
