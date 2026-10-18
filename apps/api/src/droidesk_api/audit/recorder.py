from dataclasses import asdict, dataclass
from datetime import datetime

from sqlmodel import Session, col, select

from droidesk_api.audit.enums import EventKind
from droidesk_api.audit.models import TicketEvent


@dataclass(frozen=True)
class NewEvent:
    ticket_id: int
    actor_id: int
    kind: EventKind
    created_at: datetime
    from_value: str | None = None
    to_value: str | None = None


def record_event(session: Session, event: NewEvent) -> TicketEvent:
    """Agrega el evento a la transacción en curso; el commit lo hace el servicio que cambia el ticket."""
    row = TicketEvent(**asdict(event))
    session.add(row)
    session.flush()
    return row


def list_events(session: Session, ticket_id: int) -> list[TicketEvent]:
    statement = (
        select(TicketEvent)
        .where(col(TicketEvent.ticket_id) == ticket_id)
        .order_by(col(TicketEvent.created_at), col(TicketEvent.id))
    )
    return list(session.exec(statement))
