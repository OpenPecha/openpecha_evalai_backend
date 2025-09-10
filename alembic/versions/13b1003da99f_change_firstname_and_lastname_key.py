"""change firstname and lastname key

Revision ID: 13b1003da99f
Revises: 7ebcddc81423
Create Date: 2025-09-10 12:27:41.064015

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13b1003da99f'
down_revision: Union[str, Sequence[str], None] = '7ebcddc81423'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new nullable columns first
    op.add_column('user', sa.Column('first_name', sa.String(), nullable=True, server_default=''))
    op.add_column('user', sa.Column('last_name', sa.String(), nullable=True, server_default=''))
    
    # Copy data from old columns to new columns
    op.execute("UPDATE \"user\" SET first_name = COALESCE(\"firstName\", '') WHERE first_name IS NULL")
    op.execute("UPDATE \"user\" SET last_name = COALESCE(\"lastName\", '') WHERE last_name IS NULL")
    
    # Drop the old columns
    op.drop_column('user', 'firstName')
    op.drop_column('user', 'lastName')


def downgrade() -> None:
    """Downgrade schema."""
    # Add old columns back as nullable first
    op.add_column('user', sa.Column('lastName', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('user', sa.Column('firstName', sa.VARCHAR(), autoincrement=False, nullable=True))
    
    # Copy data back
    op.execute("UPDATE \"user\" SET \"firstName\" = first_name")
    op.execute("UPDATE \"user\" SET \"lastName\" = last_name")
    
    # Drop the new columns
    op.drop_column('user', 'last_name')
    op.drop_column('user', 'first_name')
