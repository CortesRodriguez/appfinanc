"""reinicio del conteo de regeneraciones al cambiar la experiencia

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-23 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    # Nullable: NULL = se cuentan todas las regeneraciones del historial.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('level_reset_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('level_reset_at')
