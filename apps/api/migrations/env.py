from alembic import context
from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel

import droidesk_api.models  # noqa: F401  (registra las tablas en la metadata)
from droidesk_api.core.config import DatabaseSettings

config = context.config
target_metadata = SQLModel.metadata


def database_url() -> str:
    # Sin alembic.ini no hay sección [alembic]: get_main_option fallaría.
    options = config.get_section(config.config_ini_section, {})
    return options.get("sqlalchemy.url") or DatabaseSettings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Sin build_engine: las FK activas rompen las migraciones batch de SQLite.
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
