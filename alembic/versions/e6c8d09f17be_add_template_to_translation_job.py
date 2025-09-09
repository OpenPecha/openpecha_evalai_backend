"""add_template_to_translation_job

Revision ID: e6c8d09f17be
Revises: 330f677be24c
Create Date: 2025-09-09 10:37:20.835467

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e6c8d09f17be'
down_revision: Union[str, Sequence[str], None] = '330f677be24c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add template column to translation_job table."""
    # Add template column to translation_job table
    op.add_column('translation_job', sa.Column('template', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove template column from translation_job table."""
    # Remove template column from translation_job table
    op.drop_column('translation_job', 'template')
