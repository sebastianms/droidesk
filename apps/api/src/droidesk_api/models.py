"""Importa todas las tablas para registrarlas en `SQLModel.metadata` (Alembic y los tests)."""

from droidesk_api.audit.models import TicketEvent
from droidesk_api.identity.models import User
from droidesk_api.sla.models import SlaPolicy
from droidesk_api.tickets.models import Category, Comment, Ticket

__all__ = ["Category", "Comment", "SlaPolicy", "Ticket", "TicketEvent", "User"]
