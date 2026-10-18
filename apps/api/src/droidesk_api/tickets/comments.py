from sqlalchemy import ScalarSelect
from sqlmodel import Session, col, func, select

from droidesk_api.core.errors import InvalidFieldError
from droidesk_api.tickets.models import Comment, Ticket

# El mismo mensaje para un comentario inexistente y para uno de otro ticket: no revela cuáles existen.
REPLY_TARGET_MISSING_MESSAGE = (
    "El comentario al que respondes no existe en este ticket."
)


def list_comments(session: Session, ticket_id: int) -> list[Comment]:
    statement = (
        select(Comment)
        .where(col(Comment.ticket_id) == ticket_id)
        .order_by(col(Comment.created_at), col(Comment.id))
    )
    return list(session.exec(statement))


def ensure_reply_target(
    session: Session, ticket_id: int, reply_to_id: int | None
) -> None:
    """Un comentario solo puede citar a otro del mismo ticket."""
    if reply_to_id is None:
        return
    statement = select(col(Comment.id)).where(
        col(Comment.id) == reply_to_id, col(Comment.ticket_id) == ticket_id
    )
    if session.exec(statement).first() is None:
        raise InvalidFieldError("reply_to_id", REPLY_TARGET_MISSING_MESSAGE)


def comment_count() -> ScalarSelect[int]:
    """Cuántos comentarios tiene cada ticket; se incrusta en la consulta que ya lee `tickets` y usa el índice de `comments`."""
    return (
        select(func.count())
        .select_from(Comment)
        .where(col(Comment.ticket_id) == col(Ticket.id))
        .scalar_subquery()
    )
