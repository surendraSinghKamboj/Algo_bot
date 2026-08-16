from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.config.db import get_database_url

engine = None


def _session_factory():
    global engine
    url = get_database_url()
    if engine is None or engine.url.render_as_string(hide_password=False) != url:
        engine = create_engine(url, pool_pre_ping=True, future=True)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def SessionLocal():
    return _session_factory()()


def get_db():
    with SessionLocal() as session:
        yield session
