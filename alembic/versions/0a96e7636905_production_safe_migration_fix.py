"""production_safe_migration_fix

Revision ID: 0a96e7636905
Revises: c1edd20c3065
Create Date: 2025-09-24 20:13:55.566920

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a96e7636905'
down_revision: Union[str, Sequence[str], None] = 'c1edd20c3065'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Production Safe Migration."""
    # Get database connection and inspect existing tables
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()
    
    print(f"Found tables in database: {existing_tables}")
    
    # Only perform operations on tables that exist in production
    # Focus on core user foreign key updates
    
    # 1. Handle template table - convert username to user_id foreign key
    if 'template' in existing_tables:
        print("Updating template table...")
        # Check if user_id column already exists
        columns = [col['name'] for col in inspector.get_columns('template')]
        if 'user_id' not in columns and 'username' in columns:
            # Add user_id column
            op.add_column('template', sa.Column('user_id', sa.String(), nullable=True))
            # TODO: Manual data migration needed to populate user_id from username
            # After data migration, make user_id NOT NULL and drop username
            print("Added user_id column to template table - manual data migration required")
    
    # 2. Handle model table - add foreign keys for created_by and updated_by
    if 'model' in existing_tables:
        print("Updating model table...")
        # Add foreign key constraints if they don't exist
        try:
            op.create_foreign_key('fk_model_created_by', 'model', 'user', ['created_by'], ['id'])
            print("Added foreign key constraint for model.created_by")
        except Exception as e:
            print(f"Skipped model.created_by foreign key: {e}")
        
        try:
            op.create_foreign_key('fk_model_updated_by', 'model', 'user', ['updated_by'], ['id'])
            print("Added foreign key constraint for model.updated_by")
        except Exception as e:
            print(f"Skipped model.updated_by foreign key: {e}")
    
    # 3. Skip arena-related tables that don't exist in production
    arena_tables = ['arena_challenge', 'arena_ranking', 'battle_result', 
                   'elo_rating_by_model', 'elo_rating_by_model_and_template', 
                   'elo_rating_by_template', 'arena_rating']
    
    for table in arena_tables:
        if table in existing_tables:
            print(f"Arena table {table} exists - skipping for safety")
        else:
            print(f"Arena table {table} not found - skipping")
    
    print("Production safe migration completed!")


def downgrade() -> None:
    """Downgrade schema."""
    # Rollback the foreign key constraints
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()
    
    if 'model' in existing_tables:
        try:
            op.drop_constraint('fk_model_created_by', 'model', type_='foreignkey')
        except Exception:
            pass
        try:
            op.drop_constraint('fk_model_updated_by', 'model', type_='foreignkey')
        except Exception:
            pass
    
    if 'template' in existing_tables:
        try:
            op.drop_column('template', 'user_id')
        except Exception:
            pass
