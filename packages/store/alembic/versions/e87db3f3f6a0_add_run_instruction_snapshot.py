"""add run instruction snapshot

Revision ID: e87db3f3f6a0
Revises: c6b90bd3d7fe
Create Date: 2026-05-12 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e87db3f3f6a0"
down_revision: str | Sequence[str] | None = "c6b90bd3d7fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "runs",
        sa.Column("instruction_source_snapshot", sa.Text(), nullable=True),
    )
    op.execute(
        """
        UPDATE runs
        SET instruction_source_snapshot = (
            SELECT tasks.instruction_source
            FROM tasks
            WHERE tasks.task_id = runs.task_id
        )
        """
    )
    op.alter_column("runs", "instruction_source_snapshot", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("runs", "instruction_source_snapshot")
