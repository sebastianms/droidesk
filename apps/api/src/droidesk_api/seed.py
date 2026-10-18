import logging

from sqlmodel import Session, select

from droidesk_api.core.config import get_settings
from droidesk_api.core.db import build_engine
from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from droidesk_api.sla.enums import TargetUnit
from droidesk_api.sla.models import SlaPolicy
from droidesk_api.tickets.enums import Priority
from droidesk_api.tickets.models import Category

logger = logging.getLogger(__name__)

DEMO_EMAIL_DOMAIN = "droidesk.local"
CATEGORY_NAMES = [
    "Hardware",
    "Software",
    "Accesos y cuentas",
    "Red y conectividad",
    "Otro",
]


def demo_users() -> list[User]:
    """Los solicitantes van primero: los ids 1 a 4 son solicitantes y 5 a 7, agentes."""
    return [
        _demo_user("Ana Rojas", "ana.rojas", Role.REQUESTER),
        _demo_user("Bruno Castillo", "bruno.castillo", Role.REQUESTER),
        _demo_user("Carla Mena", "carla.mena", Role.REQUESTER),
        _demo_user("Diego Fuentes", "diego.fuentes", Role.REQUESTER),
        _demo_user("Elena Vidal", "elena.vidal", Role.AGENT),
        _demo_user("Felipe Araya", "felipe.araya", Role.AGENT),
        _demo_user("Gabriela Soto", "gabriela.soto", Role.AGENT),
    ]


def _demo_user(name: str, username: str, role: Role) -> User:
    return User(
        username=username, name=name, email=f"{username}@{DEMO_EMAIL_DOMAIN}", role=role
    )


def sla_policies() -> list[SlaPolicy]:
    return [
        SlaPolicy(
            priority=Priority.CRITICAL,
            rank=1,
            label="Crítica",
            description="Servicio caído o bloqueo total que afecta a varias personas. Plazo: 4 horas hábiles.",
            target_amount=4,
            target_unit=TargetUnit.HOURS,
        ),
        SlaPolicy(
            priority=Priority.HIGH,
            rank=2,
            label="Alta",
            description="Una persona no puede trabajar y no tiene alternativa. Plazo: 1 día hábil.",
            target_amount=1,
            target_unit=TargetUnit.DAYS,
        ),
        SlaPolicy(
            priority=Priority.MEDIUM,
            rank=3,
            label="Media",
            description="Algo falla, pero se puede seguir trabajando. Plazo: 3 días hábiles.",
            target_amount=3,
            target_unit=TargetUnit.DAYS,
        ),
        SlaPolicy(
            priority=Priority.LOW,
            rank=4,
            label="Baja",
            description="Consulta o mejora sin urgencia. Plazo: 5 días hábiles.",
            target_amount=5,
            target_unit=TargetUnit.DAYS,
        ),
    ]


def seed_demo_data(session: Session) -> bool:
    """Carga usuarios, categorías y políticas si la base está vacía; devuelve si cargó."""
    if not _is_empty(session):
        return False
    session.add_all(demo_users())
    session.add_all(Category(name=name) for name in CATEGORY_NAMES)
    session.add_all(sla_policies())
    session.commit()
    return True


def _is_empty(session: Session) -> bool:
    return all(
        session.exec(select(model).limit(1)).first() is None
        for model in (User, Category, SlaPolicy)
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()
    if not settings.seed_demo_data:
        logger.info("Seed omitido: DROIDESK_SEED_DEMO_DATA no está activo.")
        return
    engine = build_engine(settings.database_url)
    try:
        with Session(engine) as session:
            loaded = seed_demo_data(session)
    finally:
        engine.dispose()
    logger.info(
        "Datos de demo cargados." if loaded else "Seed omitido: la base ya tiene datos."
    )


if __name__ == "__main__":
    main()
