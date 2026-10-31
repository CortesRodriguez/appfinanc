"""origen de cada explicacion (LLM o plantilla) y motivo del respaldo

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-31 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    # Nullable: las consultas anteriores no registraron el origen.
    with op.batch_alter_table('query_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('explanation_source', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('fallback_reason', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('query_logs', schema=None) as batch_op:
        batch_op.drop_column('fallback_reason')
        batch_op.drop_column('explanation_source')
