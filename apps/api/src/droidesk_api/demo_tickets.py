"""Tickets de ejemplo de la demo: los escenarios son datos y se reproducen con `TicketService`."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlmodel import Session, select

from droidesk_api.core.db import persisted_id
from droidesk_api.identity.models import User
from droidesk_api.sla.calendar import BusinessCalendar
from droidesk_api.tickets.enums import Priority
from droidesk_api.tickets.lifecycle import TicketAction
from droidesk_api.tickets.models import Category
from droidesk_api.tickets.schemas import (
    CommentCreate,
    TicketCreate,
    TicketDetail,
    TicketUpdate,
)
from droidesk_api.tickets.service import TicketService


@dataclass(frozen=True)
class Step(ABC):
    """Algo que `actor` (su nombre de usuario) hace en el ticket, `after` tiempo después de lo anterior."""

    actor: str
    after: timedelta

    @abstractmethod
    def apply(
        self, service: TicketService, actor: User, ticket: TicketDetail
    ) -> TicketDetail: ...


@dataclass(frozen=True)
class StateStep(Step):
    action: TicketAction

    def apply(
        self, service: TicketService, actor: User, ticket: TicketDetail
    ) -> TicketDetail:
        return service.apply_transition(actor, ticket.id, self.action)


@dataclass(frozen=True)
class PriorityStep(Step):
    priority: Priority

    def apply(
        self, service: TicketService, actor: User, ticket: TicketDetail
    ) -> TicketDetail:
        return service.change_priority(
            actor, ticket.id, TicketUpdate(priority=self.priority)
        )


@dataclass(frozen=True)
class CommentStep(Step):
    """`replies_to` es la posición (desde 0) del comentario del ticket que se responde."""

    body: str
    replies_to: int | None = None

    def apply(
        self, service: TicketService, actor: User, ticket: TicketDetail
    ) -> TicketDetail:
        data = CommentCreate(body=self.body, reply_to_id=self._quoted_id(ticket))
        return service.add_comment(actor, ticket.id, data)

    def _quoted_id(self, ticket: TicketDetail) -> int | None:
        if self.replies_to is None:
            return None
        return ticket.comments[self.replies_to].id


@dataclass(frozen=True)
class DemoTicket:
    """Un ticket con su historia: lo crea `requester` hace `created_ago` y los pasos ocurren después, en orden."""

    requester: str
    category: str
    priority: Priority
    title: str
    description: str
    created_ago: timedelta
    steps: tuple[Step, ...] = ()


class ReplayClock:
    """El reloj del seed: se coloca en el pasado para cada ticket y avanza a mano con cada paso."""

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def set(self, now: datetime) -> None:
        self._now = now

    def advance(self, delta: timedelta) -> None:
        self._now += delta


class DemoTicketLoader:
    """Reproduce los escenarios con el servicio real, para que historial, SLA y contadores queden consistentes."""

    def __init__(
        self, session: Session, calendar: BusinessCalendar, loaded_at: datetime
    ) -> None:
        self._loaded_at = loaded_at
        self._clock = ReplayClock(loaded_at)
        self._service = TicketService(session, self._clock, calendar)
        self._users = {user.username: user for user in session.exec(select(User))}
        self._category_ids = {
            category.name: persisted_id(category)
            for category in session.exec(select(Category))
        }

    def load(self, tickets: Iterable[DemoTicket]) -> None:
        for ticket in tickets:
            self._replay(ticket)

    def _replay(self, demo: DemoTicket) -> None:
        self._clock.set(self._loaded_at - demo.created_ago)
        ticket = self._service.create_ticket(
            self._users[demo.requester], self._creation_of(demo)
        )
        for step in demo.steps:
            self._clock.advance(step.after)
            ticket = step.apply(self._service, self._users[step.actor], ticket)

    def _creation_of(self, demo: DemoTicket) -> TicketCreate:
        return TicketCreate(
            title=demo.title,
            description=demo.description,
            category_id=self._category_ids[demo.category],
            priority=demo.priority,
        )


# Cada escenario deja un SLA que no depende del día ni de la hora de la carga: el vencido es tan
# antiguo que lo está aunque haya fines de semana de por medio, y los demás son lo bastante
# recientes (o ya terminaron a tiempo) para no estar vencidos ni por vencer.
DEMO_TICKETS = (
    DemoTicket(
        requester="carla.mena",
        category="Red y conectividad",
        priority=Priority.HIGH,
        title="Sin conexión a internet en todo el piso 3",
        description=(
            "Desde hace unos minutos nadie del piso 3 tiene internet ni acceso a los "
            "sistemas internos. Falla tanto el cable como el wifi. Somos unas 25 "
            "personas sin poder trabajar."
        ),
        created_ago=timedelta(minutes=25),
        steps=(
            PriorityStep(
                actor="felipe.araya",
                after=timedelta(minutes=10),
                priority=Priority.CRITICAL,
            ),
        ),
    ),
    DemoTicket(
        requester="diego.fuentes",
        category="Hardware",
        priority=Priority.MEDIUM,
        title="Varias teclas del teclado no responden",
        description=(
            "Las teclas E y R y la barra espaciadora fallan con frecuencia y hay que "
            "presionarlas varias veces. Estoy usando un teclado prestado, pero "
            "necesito uno de reemplazo."
        ),
        created_ago=timedelta(days=1, hours=3),
    ),
    DemoTicket(
        requester="bruno.castillo",
        category="Software",
        priority=Priority.LOW,
        title="Consulta sobre un editor de PDF autorizado",
        description=(
            "¿Existe un editor de PDF aprobado por la organización? Hoy uso la "
            "versión de prueba de uno gratuito y quisiera saber si puedo instalar "
            "otro o si me pueden asignar una licencia. No es urgente."
        ),
        created_ago=timedelta(days=3),
    ),
    DemoTicket(
        requester="ana.rojas",
        category="Accesos y cuentas",
        priority=Priority.HIGH,
        title="No puedo abrir la carpeta compartida de Finanzas",
        description=(
            "Desde el cambio de área de la semana pasada recibo «Acceso denegado» al "
            "abrir la carpeta compartida de Finanzas. Necesito los archivos del "
            "cierre mensual y no tengo otra forma de acceder a ellos."
        ),
        created_ago=timedelta(days=6),
        steps=(
            CommentStep(
                actor="ana.rojas",
                after=timedelta(days=4),
                body=(
                    "Sigo sin acceso y el cierre mensual vence esta semana. ¿Falta "
                    "alguna autorización de mi jefatura?"
                ),
            ),
        ),
    ),
    DemoTicket(
        requester="bruno.castillo",
        category="Hardware",
        priority=Priority.MEDIUM,
        title="La impresora del segundo piso imprime con rayas",
        description=(
            "Desde el lunes la impresora multifuncional del segundo piso deja rayas "
            "verticales en todas las hojas. Se ve igual al imprimir y al sacar copias."
        ),
        created_ago=timedelta(days=2),
        steps=(
            StateStep(
                actor="elena.vidal",
                after=timedelta(hours=2),
                action=TicketAction.TAKE,
            ),
            CommentStep(
                actor="elena.vidal",
                after=timedelta(minutes=20),
                body=(
                    "Hola Bruno, ¿la falla ocurre con cualquier documento o solo con "
                    "algunos? ¿Probaste con otro tipo de papel?"
                ),
            ),
            CommentStep(
                actor="bruno.castillo",
                after=timedelta(hours=1, minutes=40),
                body=(
                    "Ocurre con todos los documentos y también con las copias. Probé "
                    "con hoja carta y oficio y el resultado es el mismo."
                ),
                replies_to=0,
            ),
            CommentStep(
                actor="elena.vidal",
                after=timedelta(hours=1),
                body=(
                    "Gracias, eso apunta al tóner. Lo cambio hoy en la tarde y te "
                    "aviso cuando esté listo."
                ),
            ),
        ),
    ),
    DemoTicket(
        requester="carla.mena",
        category="Software",
        priority=Priority.MEDIUM,
        title="No puedo instalar el cliente de videollamadas",
        description=(
            "Al ejecutar el instalador aparece el error «No se pudo completar la "
            "instalación» y se cierra. Necesito la aplicación para las reuniones con "
            "clientes de la próxima semana."
        ),
        created_ago=timedelta(days=3),
        steps=(
            StateStep(
                actor="felipe.araya",
                after=timedelta(hours=1),
                action=TicketAction.TAKE,
            ),
            CommentStep(
                actor="felipe.araya",
                after=timedelta(minutes=15),
                body=(
                    "Hola Carla, ¿me envías la versión de Windows de tu equipo y una "
                    "captura del mensaje de error completo? Dejo el ticket en espera "
                    "hasta tu respuesta."
                ),
            ),
            StateStep(
                actor="felipe.araya",
                after=timedelta(minutes=1),
                action=TicketAction.HOLD,
            ),
        ),
    ),
    DemoTicket(
        requester="diego.fuentes",
        category="Accesos y cuentas",
        priority=Priority.HIGH,
        title="Mi cuenta de correo quedó bloqueada",
        description=(
            "Intenté ingresar varias veces con una contraseña antigua y ahora el "
            "correo dice que la cuenta está bloqueada. Necesito revisar mis mensajes "
            "para una reunión de hoy."
        ),
        created_ago=timedelta(days=1),
        steps=(
            StateStep(
                actor="gabriela.soto",
                after=timedelta(minutes=30),
                action=TicketAction.TAKE,
            ),
            CommentStep(
                actor="gabriela.soto",
                after=timedelta(minutes=10),
                body=(
                    "Desbloqueé tu cuenta y restablecí la contraseña. Ingresa con la "
                    "clave temporal que te envié y confirma si todo funciona."
                ),
            ),
            StateStep(
                actor="gabriela.soto",
                after=timedelta(minutes=5),
                action=TicketAction.RESOLVE,
            ),
        ),
    ),
    DemoTicket(
        requester="ana.rojas",
        category="Red y conectividad",
        priority=Priority.MEDIUM,
        title="Solicitud de acceso a la VPN para teletrabajo",
        description=(
            "El próximo mes teletrabajaré dos días a la semana y necesito acceso a la "
            "VPN para conectarme a los sistemas internos desde mi casa. Mi jefatura "
            "ya está al tanto."
        ),
        created_ago=timedelta(days=5),
        steps=(
            StateStep(
                actor="elena.vidal",
                after=timedelta(hours=1),
                action=TicketAction.TAKE,
            ),
            CommentStep(
                actor="elena.vidal",
                after=timedelta(minutes=30),
                body=(
                    "Creé tu perfil de VPN y te envié las instrucciones de instalación "
                    "a tu correo."
                ),
            ),
            StateStep(
                actor="elena.vidal",
                after=timedelta(hours=2),
                action=TicketAction.RESOLVE,
            ),
            StateStep(
                actor="ana.rojas",
                after=timedelta(days=1),
                action=TicketAction.CLOSE,
            ),
        ),
    ),
    DemoTicket(
        requester="bruno.castillo",
        category="Otro",
        priority=Priority.LOW,
        title="Préstamo de un proyector para el jueves",
        description=(
            "Necesito un proyector portátil para una presentación con mi equipo el "
            "jueves en la sala 2."
        ),
        created_ago=timedelta(days=4),
        steps=(
            CommentStep(
                actor="bruno.castillo",
                after=timedelta(hours=3),
                body=(
                    "Ya conseguí un proyector con el área de Operaciones, así que "
                    "cancelo esta solicitud."
                ),
            ),
            StateStep(
                actor="bruno.castillo",
                after=timedelta(minutes=1),
                action=TicketAction.CANCEL,
            ),
        ),
    ),
)


def load_demo_tickets(
    session: Session, calendar: BusinessCalendar, loaded_at: datetime
) -> None:
    DemoTicketLoader(session, calendar, loaded_at).load(DEMO_TICKETS)
