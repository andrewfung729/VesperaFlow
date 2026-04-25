"""add task target working directory

Revision ID: 7dd6bb6c746f
Revises: b4272fbe1936
Create Date: 2026-04-25 22:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7dd6bb6c746f"
down_revision = "b4272fbe1936"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("target_working_directory", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "target_working_directory")
