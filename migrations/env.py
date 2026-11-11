from alembic import context
from sqlalchemy import create_engine, pool

from core.config import get_settings
from core.db import Base
from core.models import DeadLetter, Lead, LeadIdentity, LeadSource, OutreachLog  # noqa: F401

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def migrate(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        version_table_schema=context.config.attributes.get("migration_schema"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    supplied_connection = context.config.attributes.get("connection")
    if supplied_connection is not None:
        migrate(supplied_connection)
        return
    engine = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        migrate(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
