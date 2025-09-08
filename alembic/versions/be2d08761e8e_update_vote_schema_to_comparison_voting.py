"""update_vote_schema_to_comparison_voting

Revision ID: be2d08761e8e
Revises: 801a4a9b9f91
Create Date: 2025-09-08 19:17:38.168088

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'be2d08761e8e'
down_revision: Union[str, Sequence[str], None] = '801a4a9b9f91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update vote schema to comparison voting system."""
    # Since we're changing the fundamental structure, drop and recreate the table
    # This is cleaner than trying to migrate existing data
    
    # Drop the entire vote table
    op.drop_table('vote')
    
    # Recreate vote table with new schema
    op.create_table('vote',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('translation_output1_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('translation_output2_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('voted', sa.dialects.postgresql.ARRAY(sa.dialects.postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        
        # Constraints
        sa.CheckConstraint('translation_output1_id != translation_output2_id', name='different_translation_outputs'),
        sa.UniqueConstraint('user_id', 'translation_output1_id', 'translation_output2_id', name='unique_user_comparison_vote'),
        sa.ForeignKeyConstraint(['translation_output1_id'], ['translation_output.id'], name='fk_vote_translation_output1', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['translation_output2_id'], ['translation_output.id'], name='fk_vote_translation_output2', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='vote_pkey')
    )
    
    # Create indexes for better performance
    op.create_index('idx_vote_user_id_new', 'vote', ['user_id'])
    op.create_index('idx_vote_translation_output1_id', 'vote', ['translation_output1_id'])
    op.create_index('idx_vote_translation_output2_id', 'vote', ['translation_output2_id'])
    op.create_index('idx_vote_created_at_new', 'vote', ['created_at'])


def downgrade() -> None:
    """Revert vote schema back to 5-star rating system."""
    # Drop new constraints
    op.drop_constraint('unique_user_comparison_vote', 'vote', type_='unique')
    op.drop_constraint('different_translation_outputs', 'vote', type_='check')
    op.drop_constraint('fk_vote_translation_output1', 'vote', type_='foreignkey')
    op.drop_constraint('fk_vote_translation_output2', 'vote', type_='foreignkey')
    
    # Drop new columns
    op.drop_column('vote', 'translation_output1_id')
    op.drop_column('vote', 'translation_output2_id')
    op.drop_column('vote', 'voted')
    
    # Add back old columns
    op.add_column('vote', sa.Column('model_version_id', sa.dialects.postgresql.UUID(), nullable=False))
    op.add_column('vote', sa.Column('translation_output_id', sa.dialects.postgresql.UUID(), nullable=False))
    op.add_column('vote', sa.Column('score', sa.INTEGER(), nullable=False))
    
    # Add back old constraints
    op.create_foreign_key('fk_vote_model_version', 'vote', 'model_version', ['model_version_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_vote_translation_output', 'vote', 'translation_output', ['translation_output_id'], ['id'], ondelete='CASCADE')
    op.create_unique_constraint('unique_user_translation_vote', 'vote', ['user_id', 'translation_output_id'])
    op.create_check_constraint('valid_score_range', 'vote', 'score >= 1 AND score <= 5')
