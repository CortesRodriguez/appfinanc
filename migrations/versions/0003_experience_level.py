"""experiencia declarada del usuario

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-23 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    # Nullable: las cuentas existentes y las de Google quedan sin declarar.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('experience_level', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('experience_level')
