from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        pool_timeout=5,
        connect_args={"connect_timeout": 5},
    )
    return sessionmaker(engine, expire_on_commit=False)


def get_db():
    with get_session_factory()() as session:
        yield session
