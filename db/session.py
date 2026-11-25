import os
import pathlib
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from db.models import Base

_engine = None
_SessionFactory = None


def _build_engine():
    db_path = os.getenv("DB_PATH", "data/jobs.db")
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )


def get_engine():
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


# Columns added after the first release; SQLite needs them added by hand.
_ADDED_COLUMNS = {
    "cold_email_targets": {"note": "TEXT", "subject": "VARCHAR", "follow_ups": "INTEGER DEFAULT 0"},
}


def create_tables():
    from sqlalchemy import inspect, text
    eng = get_engine()
    Base.metadata.create_all(eng)
    insp = inspect(eng)
    with eng.begin() as conn:
        for table, cols in _ADDED_COLUMNS.items():
            have = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def get_session() -> Session:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), autoflush=True)
    return _SessionFactory()


@contextmanager
def session_scope():
    """Provide a transactional scope; commits on exit, rolls back on exception."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
