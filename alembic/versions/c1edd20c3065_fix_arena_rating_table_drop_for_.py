"""fix_arena_rating_table_drop_for_production

Revision ID: c1edd20c3065
Revises: 611e22ed1f2a
Create Date: 2025-09-24 20:02:41.385183

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1edd20c3065'
down_revision: Union[str, Sequence[str], None] = '611e22ed1f2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # This migration handles the arena_rating table drop issue for production
    # Check if the arena_rating table exists before attempting to drop it
    
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Check if arena_rating table exists
    if 'arena_rating' in inspector.get_table_names():
        print("arena_rating table found, dropping it...")
        op.drop_table('arena_rating')
    else:
        print("arena_rating table not found, skipping drop operation...")


def downgrade() -> None:
    """Downgrade schema."""
    # This is a fix migration, no downgrade needed
    pass
