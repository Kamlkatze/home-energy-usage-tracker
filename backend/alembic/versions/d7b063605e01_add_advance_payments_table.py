"""add_advance_payments_table

Revision ID: d7b063605e01
Revises: 12182ced0bb9
Create Date: 2026-09-12 20:20:18.804006

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = 'd7b063605e01'
down_revision = '12182ced0bb9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('advance_payments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('meter_id', sa.Integer(), nullable=False),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_to', sa.Date(), nullable=True),
    sa.Column('monthly_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['meter_id'], ['meters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_advance_payments_id'), 'advance_payments', ['id'], unique=False)

    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

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


def downgrade() -> None:
    op.execute("ALTER TABLE advance_payments "
               "DROP CONSTRAINT IF EXISTS excl_advance_payment_no_overlap")
    op.drop_index(op.f('ix_advance_payments_id'), table_name='advance_payments')
    op.drop_table('advance_payments')