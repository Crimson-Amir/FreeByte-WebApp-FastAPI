"""first

Revision ID: 2c5268ee8525
Revises: 7a0ec308424f
Create Date: 2024-10-18 15:05:47.831929

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c5268ee8525'
down_revision: Union[str, None] = '7a0ec308424f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('purchase', sa.Column('price', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('purchase', 'price')
    # ### end Alembic commands ###
