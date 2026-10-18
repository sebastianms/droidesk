"""Comments: the comments table and ticket_events.comment_id.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-18 09:48:12.008828
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name=op.f("fk_comments_author_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"], name=op.f("fk_comments_ticket_id_tickets")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comments")),
    )
    with op.batch_alter_table("comments", schema=None) as batch_op:
        batch_op.create_index(
            "ix_comments_ticket_id_created_at",
            ["ticket_id", "created_at"],
            unique=False,
        )

    with op.batch_alter_table("ticket_events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("comment_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_ticket_events_comment_id_comments"),
            "comments",
            ["comment_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("ticket_events", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_ticket_events_comment_id_comments"), type_="foreignkey"
        )
        batch_op.drop_column("comment_id")

    with op.batch_alter_table("comments", schema=None) as batch_op:
        batch_op.drop_index("ix_comments_ticket_id_created_at")

    op.drop_table("comments")
