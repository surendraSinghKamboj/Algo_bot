from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.config.db import get_database_url

# Create engine using resolved database URL (env DATABASE_URL > settings > sqlite fallback)
engine = create_engine(get_database_url(), pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session
