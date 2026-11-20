"""Conexión a base de datos SQLAlchemy 2.0 (PostgreSQL en nube / SQLite en local)."""

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
db_url = settings.normalized_database_url
is_sqlite = db_url.startswith("sqlite")

engine_kwargs: dict = {
    "pool_pre_ping": True,
}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(db_url, **engine_kwargs)

if is_sqlite:
    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Clase base para todos los modelos ORM (3FN)."""


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> tuple[bool, str]:
    """Verifica conectividad real a la base de datos configurada."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        motor = "sqlite" if is_sqlite else "postgresql"
        return True, motor
    except Exception as exc:  # pragma: no cover
        return False, str(exc)
