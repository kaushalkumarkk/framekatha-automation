from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from core.db import Base


@pytest.mark.postgres
def test_migration_upgrade_and_downgrade(engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("Set TEST_DATABASE_URL to verify PostgreSQL migrations")
    schema = "migration_" + uuid4().hex
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.attributes["migration_schema"] = schema
    with engine.connect().execution_options(schema_translate_map={None: schema}) as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        # Alembic ALTER TABLE operations do not use schema_translate_map.
        # Set the search path too, so add/drop-column DDL stays isolated.
        connection.execute(
            text("SELECT set_config('search_path', :schema, false)"), {"schema": schema}
        )
        connection.commit()
        config.attributes["connection"] = connection
        try:
            command.upgrade(config, "head")
            tables = set(inspect(connection).get_table_names(schema=schema))
            assert tables == set(Base.metadata.tables) | {"alembic_version"}
            connection.commit()
            command.downgrade(config, "base")
            assert inspect(connection).get_table_names(schema=schema) == ["alembic_version"]
        finally:
            connection.rollback()
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            connection.execute(text("RESET search_path"))
            connection.commit()
