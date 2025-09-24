"""change template id to string

Revision ID: ae9062696746
Revises: 5924870362e5
Create Date: 2025-09-19 10:13:28.407927

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae9062696746'
down_revision: Union[str, Sequence[str], None] = '5924870362e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
