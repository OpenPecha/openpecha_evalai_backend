"""add_target_language_to_translation_job

Revision ID: 330f677be24c
Revises: 6204651ada5a
Create Date: 2025-09-09 09:10:42.995569

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '330f677be24c'
down_revision: Union[str, Sequence[str], None] = '6204651ada5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add target_language column to translation_job table."""
    # Add target_language column to translation_job table
    op.add_column('translation_job', sa.Column('target_language', sa.String(), nullable=True))


def downgrade() -> None:
    """Remove target_language column from translation_job table."""
    # Remove target_language column from translation_job table
    op.drop_column('translation_job', 'target_language')
