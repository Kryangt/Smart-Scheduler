import os
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv("backend/.env")

_engine = None
_SessionLocal = None


def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    return database_url


def get_migration_database_url():
    migration_url = os.getenv("MIGRATION_DATABASE_URL")
    if migration_url:
        return migration_url

    database_url = get_database_url()
    if "-pooler." in database_url:
        raise RuntimeError(
            "MIGRATION_DATABASE_URL must use a direct Neon connection, not the pooled endpoint"
        )
    return database_url


def get_engine():
    global _engine

    if _engine is None:
        _engine = create_engine(
            get_database_url(),
            echo=os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
            pool_pre_ping=True,
        )

    return _engine


def get_migration_engine():
    return create_engine(
        get_migration_database_url(),
        echo=os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
        pool_pre_ping=True,
    )


def get_session_local():
    global _SessionLocal

    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False
        )

    return _SessionLocal


def get_db():
    SessionLocal = get_session_local()
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def get_connection():
    return psycopg2.connect(get_database_url())
