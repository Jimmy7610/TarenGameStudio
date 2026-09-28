from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.base import Base


def database_url() -> str:
    return os.getenv("TGS_DATABASE_URL", "sqlite+pysqlite:///./taren_game_studio.db")


engine = create_engine(
    database_url(),
    future=True,
    connect_args={"check_same_thread": False} if database_url().startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def init_database() -> None:
    Base.metadata.create_all(engine)


def get_session():
    with SessionLocal() as session:
        yield session
