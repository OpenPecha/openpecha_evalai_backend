"""make_translation_output_id_required_in_vote

Revision ID: c0c736a86fdf
Revises: 6d093658596c
Create Date: 2025-09-08 17:42:31.226062

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0c736a86fdf'
down_revision: Union[str, Sequence[str], None] = '6d093658596c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make translation_output_id NOT NULL in vote table."""
    # First, delete any existing votes with NULL translation_output_id
    # These are invalid votes that shouldn't exist with the new requirement
    op.execute("DELETE FROM vote WHERE translation_output_id IS NULL")
    
    # Now make the column NOT NULL
    op.alter_column('vote', 'translation_output_id',
                   existing_type=sa.dialects.postgresql.UUID(),
                   nullable=False)


def downgrade() -> None:
    """Make translation_output_id nullable again in vote table."""
    op.alter_column('vote', 'translation_output_id',
                   existing_type=sa.dialects.postgresql.UUID(),
                   nullable=True)
