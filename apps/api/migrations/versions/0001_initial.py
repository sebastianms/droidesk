"""Initial schema: users, categories, sla_policies, tickets and ticket_events.

Revision ID: 0001
Revises:
Create Date: 2026-10-17 18:13:58.554945
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=60), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("name", name=op.f("uq_categories_name")),
    )
    op.create_table(
        "sla_policies",
        sa.Column(
            "priority",
            sa.Enum(
                "critical",
                "high",
                "medium",
                "low",
                name="priority",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("label", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column(
            "description", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False
        ),
        sa.Column("target_amount", sa.Integer(), nullable=False),
        sa.Column(
            "target_unit",
            sa.Enum("hours", "days", name="targetunit", native_enum=False, length=20),
            nullable=False,
        ),
        sa.CheckConstraint(
            "target_amount > 0", name=op.f("ck_sla_policies_target_amount_positive")
        ),
        sa.PrimaryKeyConstraint("priority", name=op.f("pk_sla_policies")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "username", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False
        ),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column(
            "email", sqlmodel.sql.sqltypes.AutoString(length=254), nullable=False
        ),
        sa.Column(
            "role",
            sa.Enum("requester", "agent", name="role", native_enum=False, length=20),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_users_username"), ["username"], unique=True
        )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "title", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "in_progress",
                "on_hold",
                "resolved",
                "closed",
                "cancelled",
                name="ticketstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum(
                "critical",
                "high",
                "medium",
                "low",
                name="priority",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("updated_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("sla_due_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("sla_paused_minutes", sa.Integer(), nullable=False),
        sa.Column("on_hold_since", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
        sa.Column("resolved_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
        sa.Column("closed_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
        sa.Column("cancelled_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
        sa.CheckConstraint(
            "sla_paused_minutes >= 0",
            name=op.f("ck_tickets_sla_paused_minutes_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"], ["users.id"], name=op.f("fk_tickets_assignee_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_tickets_category_id_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["priority"],
            ["sla_policies.priority"],
            name=op.f("fk_tickets_priority_sla_policies"),
        ),
        sa.ForeignKeyConstraint(
            ["requester_id"], ["users.id"], name=op.f("fk_tickets_requester_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tickets")),
    )
    with op.batch_alter_table("tickets", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_tickets_assignee_id"), ["assignee_id"], unique=False
        )
        batch_op.create_index(
            "ix_tickets_requester_id_created_at",
            ["requester_id", "created_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_tickets_status_sla_due_at", ["status", "sla_due_at"], unique=False
        )

    op.create_table(
        "ticket_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "created",
                "assigned",
                "status_changed",
                "priority_changed",
                "commented",
                name="eventkind",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "from_value", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column(
            "to_value", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column("created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_ticket_events_actor_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            name=op.f("fk_ticket_events_ticket_id_tickets"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ticket_events")),
    )
    with op.batch_alter_table("ticket_events", schema=None) as batch_op:
        batch_op.create_index(
            "ix_ticket_events_ticket_id_created_at",
            ["ticket_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("ticket_events", schema=None) as batch_op:
        batch_op.drop_index("ix_ticket_events_ticket_id_created_at")

    op.drop_table("ticket_events")
    with op.batch_alter_table("tickets", schema=None) as batch_op:
        batch_op.drop_index("ix_tickets_status_sla_due_at")
        batch_op.drop_index("ix_tickets_requester_id_created_at")
        batch_op.drop_index(batch_op.f("ix_tickets_assignee_id"))

    op.drop_table("tickets")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_username"))

    op.drop_table("users")
    op.drop_table("sla_policies")
    op.drop_table("categories")
