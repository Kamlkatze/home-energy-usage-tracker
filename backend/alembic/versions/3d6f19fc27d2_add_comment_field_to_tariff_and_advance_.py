"""add_comment_field_to_tariff_and_advance_payment

Revision ID: 3d6f19fc27d2
Revises: 60757ca5eeef
Create Date: 2026-09-18 21:33:42.053171

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '3d6f19fc27d2'
down_revision = '60757ca5eeef'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('advance_payments', sa.Column('comment', sa.String(length=500), nullable=True))
    op.add_column('tariff_periods', sa.Column('comment', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('tariff_periods', 'comment')
    op.drop_column('advance_payments', 'comment')