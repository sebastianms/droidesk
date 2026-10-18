"""Comment replies: comments.reply_to_id.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-18 10:33:33.174401
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("comments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reply_to_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_comments_reply_to_id_comments"),
            "comments",
            ["reply_to_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("comments", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_comments_reply_to_id_comments"), type_="foreignkey"
        )
        batch_op.drop_column("reply_to_id")
