import os
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from core.config import Settings, get_settings
from core.db import Base, get_db, get_session_factory
from core.models import DeadLetter, Lead, LeadIdentity, LeadSource, OutreachLog  # noqa: F401

load_dotenv()


@pytest.fixture(scope="session")
def engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        if not url.startswith("postgresql+psycopg://"):
            raise ValueError("TEST_DATABASE_URL must use postgresql+psycopg://")
        admin = create_engine(url)
        schema = "test_" + uuid4().hex
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        database = admin.execution_options(schema_translate_map={None: schema})
        Base.metadata.create_all(database)
        yield database
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
    else:
        database = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(database)
        yield database
        database.dispose()


@pytest.fixture
def factory(engine):
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        api_key="test-only-key-with-enough-characters",
        retry_base_seconds=0,
        fuzzy_name_threshold=92,
    )


@pytest.fixture
def client(factory, settings):
    def db_override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_db] = db_override
    # Lifespan calls the config directly, so provide a valid key independently.
    original_key = os.environ.get("API_KEY")
    os.environ["API_KEY"] = settings.api_key.get_secret_value()
    get_settings.cache_clear()
    try:
        with TestClient(app) as test_client:
            test_client.headers["X-API-Key"] = settings.api_key.get_secret_value()
            yield test_client
    finally:
        app.dependency_overrides.clear()
        if original_key is None:
            os.environ.pop("API_KEY", None)
        else:
            os.environ["API_KEY"] = original_key
        get_settings.cache_clear()
