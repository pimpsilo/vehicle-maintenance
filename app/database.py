from typing import Generator
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event
from sqlalchemy.engine import Engine
from app.config import settings

# SQLite configuration with WAL mode and foreign key enforcement
connect_args = {"check_same_thread": False}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    # Automatic schema migration checks
    try:
        with engine.connect() as conn:
            cursor = conn.connection.cursor()
            cursor.execute("PRAGMA table_info(vehicles)")
            columns = [row[1] for row in cursor.fetchall()]
            if columns and "ezpass_transponder" not in columns:
                cursor.execute("ALTER TABLE vehicles ADD COLUMN ezpass_transponder VARCHAR")
                conn.connection.commit()
            cursor.close()
    except Exception:
        pass

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
