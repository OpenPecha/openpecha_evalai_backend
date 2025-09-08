"""add_updated_at_to_vote_table

Revision ID: 6d093658596c
Revises: 95e1740a0796
Create Date: 2025-09-08 17:37:43.400453

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d093658596c'
down_revision: Union[str, Sequence[str], None] = '95e1740a0796'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add updated_at column to vote table with default value."""
    # Add updated_at column with default value of NOW() and set existing records to created_at value
    op.add_column('vote', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')))
    
    # Update existing records to set updated_at to created_at value
    op.execute("UPDATE vote SET updated_at = created_at WHERE updated_at IS NULL")


def downgrade() -> None:
    """Remove updated_at column from vote table."""
    op.drop_column('vote', 'updated_at')
