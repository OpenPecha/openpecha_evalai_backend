"""removed input and output text from elo tables

Revision ID: 623f4f1f9496
Revises: 150302e80ede
Create Date: 2025-09-30 16:18:58.153199

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '623f4f1f9496'
down_revision: Union[str, Sequence[str], None] = '150302e80ede'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
