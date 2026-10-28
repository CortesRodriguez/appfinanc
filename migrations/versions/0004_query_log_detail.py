"""detalle de cada consulta para el historial del perfil

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-23 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    # Nullable: las consultas anteriores quedan sin detalle (la tabla muestra "-").
    with op.batch_alter_table('query_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('value', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('unit', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('risk_level', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('period_days', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('query_logs', schema=None) as batch_op:
        batch_op.drop_column('period_days')
        batch_op.drop_column('risk_level')
        batch_op.drop_column('unit')
        batch_op.drop_column('value')
