"""change v2rayconfig config_key to optinal

Revision ID: 29aef44da950
Revises: 78dd70ac2960
Create Date: 2024-08-15 19:56:05.124037

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '29aef44da950'
down_revision: Union[str, None] = '78dd70ac2960'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('v2ray_config', 'config_key',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('v2ray_config', 'config_email',
               existing_type=sa.VARCHAR(),
               nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('v2ray_config', 'config_email',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('v2ray_config', 'config_key',
               existing_type=sa.VARCHAR(),
               nullable=False)
    # ### end Alembic commands ###
