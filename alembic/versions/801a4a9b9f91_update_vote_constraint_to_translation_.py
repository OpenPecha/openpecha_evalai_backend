"""update_vote_constraint_to_translation_output

Revision ID: 801a4a9b9f91
Revises: c0c736a86fdf
Create Date: 2025-09-08 17:50:07.163498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '801a4a9b9f91'
down_revision: Union[str, Sequence[str], None] = 'c0c736a86fdf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update vote constraint from user_id+model_version_id to user_id+translation_output_id."""
    # First, remove duplicate votes keeping only the most recent one for each user+translation_output combination
    op.execute("""
        DELETE FROM vote 
        WHERE id NOT IN (
            SELECT DISTINCT ON (user_id, translation_output_id) id
            FROM vote 
            ORDER BY user_id, translation_output_id, created_at DESC
        )
    """)
    
    # Now add new unique constraint for user_id + translation_output_id
    op.create_unique_constraint('unique_user_translation_vote', 'vote', ['user_id', 'translation_output_id'])


def downgrade() -> None:
    """Revert vote constraint back to user_id+model_version_id."""
    # Drop the new constraint
    op.drop_constraint('unique_user_translation_vote', 'vote', type_='unique')
    
    # Re-add the old constraint (this may fail if there are duplicate votes for same user+model)
    op.create_unique_constraint('unique_user_model_vote', 'vote', ['user_id', 'model_version_id'])
