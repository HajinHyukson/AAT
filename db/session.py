from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator
from urllib.parse import quote

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.env import load_dotenv


def get_database_url(*, prefer_compose_port: bool = False) -> str:
    load_dotenv()

    if prefer_compose_port:
        user = os.getenv("POSTGRES_USER", "attribution")
        password = quote(os.getenv("POSTGRES_PASSWORD", "attribution"), safe="")
        db = os.getenv("POSTGRES_DB", "attribution")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_HOST_PORT", "55432")
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    return get_database_url(prefer_compose_port=True)


@lru_cache(maxsize=2)
def make_engine(prefer_compose_port: bool = False) -> Engine:
    return create_engine(
        get_database_url(prefer_compose_port=prefer_compose_port),
        pool_pre_ping=True,
        pool_size=int(os.getenv("SQLALCHEMY_POOL_SIZE", "3")),
        max_overflow=int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", "2")),
        pool_recycle=int(os.getenv("SQLALCHEMY_POOL_RECYCLE_SECONDS", "1800")),
    )


@lru_cache(maxsize=2)
def make_session_factory(*, prefer_compose_port: bool = False) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(prefer_compose_port), expire_on_commit=False)


@contextmanager
def session_scope(*, prefer_compose_port: bool = False) -> Iterator[Session]:
    factory = make_session_factory(prefer_compose_port=prefer_compose_port)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
