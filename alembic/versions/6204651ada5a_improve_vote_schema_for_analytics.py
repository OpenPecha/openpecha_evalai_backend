"""improve_vote_schema_for_analytics

Revision ID: 6204651ada5a
Revises: be2d08761e8e
Create Date: 2025-09-08 19:26:54.920009

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6204651ada5a'
down_revision: Union[str, Sequence[str], None] = 'be2d08761e8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade vote schema to improved analytics-optimized version."""
    # Drop the current vote table completely since we're restructuring
    op.drop_table('vote')
    
    # Create the improved vote table with optimized schema
    op.create_table('vote',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('translation_job_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        
        # Normalized comparison pair (A < B lexicographically)
        sa.Column('translation_output_a_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('translation_output_b_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        
        # Simplified preference tracking
        sa.Column('winner_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_tie', sa.Integer(), nullable=False, server_default='0'),
        
        # Analytics metadata
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        
        # Constraints
        sa.CheckConstraint('translation_output_a_id != translation_output_b_id', name='different_translation_outputs'),
        sa.CheckConstraint('translation_output_a_id < translation_output_b_id', name='normalized_uuid_order'),
        sa.CheckConstraint('winner_id IS NULL OR winner_id = translation_output_a_id OR winner_id = translation_output_b_id', name='valid_winner'),
        sa.UniqueConstraint('user_id', 'translation_output_a_id', 'translation_output_b_id', name='unique_user_normalized_comparison'),
        
        # Foreign key constraints
        sa.ForeignKeyConstraint(['translation_job_id'], ['translation_job.id'], name='fk_vote_translation_job', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['translation_output_a_id'], ['translation_output.id'], name='fk_vote_translation_output_a', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['translation_output_b_id'], ['translation_output.id'], name='fk_vote_translation_output_b', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['winner_id'], ['translation_output.id'], name='fk_vote_winner', ondelete='CASCADE'),
        
        sa.PrimaryKeyConstraint('id', name='vote_pkey')
    )
    
    # Create optimized indexes for analytics queries
    op.create_index('idx_vote_user_id_analytics', 'vote', ['user_id'])
    op.create_index('idx_vote_translation_job_id', 'vote', ['translation_job_id'])
    op.create_index('idx_vote_winner_id', 'vote', ['winner_id'])
    op.create_index('idx_vote_is_tie', 'vote', ['is_tie'])
    op.create_index('idx_vote_created_at_analytics', 'vote', ['created_at'])
    op.create_index('idx_vote_comparison_pair', 'vote', ['translation_output_a_id', 'translation_output_b_id'])


def downgrade() -> None:
    """Downgrade back to previous comparison voting schema."""
    # Drop the improved vote table
    op.drop_table('vote')
    
    # Recreate the previous comparison voting table
    op.create_table('vote',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('translation_output1_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('translation_output2_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('voted', sa.dialects.postgresql.ARRAY(sa.dialects.postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        
        sa.CheckConstraint('translation_output1_id != translation_output2_id', name='different_translation_outputs'),
        sa.UniqueConstraint('user_id', 'translation_output1_id', 'translation_output2_id', name='unique_user_comparison_vote'),
        sa.ForeignKeyConstraint(['translation_output1_id'], ['translation_output.id'], name='fk_vote_translation_output1', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['translation_output2_id'], ['translation_output.id'], name='fk_vote_translation_output2', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='vote_pkey')
    )
    
    op.create_index('idx_vote_user_id_new', 'vote', ['user_id'])
    op.create_index('idx_vote_translation_output1_id', 'vote', ['translation_output1_id'])
    op.create_index('idx_vote_translation_output2_id', 'vote', ['translation_output2_id'])
    op.create_index('idx_vote_created_at_new', 'vote', ['created_at'])
