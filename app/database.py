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

def _add_column_if_missing(cursor, table: str, column: str, col_type: str):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if columns and column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    # Automatic schema migration checks for SQLite
    try:
        with engine.connect() as conn:
            cursor = conn.connection.cursor()
            # 1. vehicles table migrations
            _add_column_if_missing(cursor, "vehicles", "ezpass_transponder", "VARCHAR")
            
            # 2. attachment migrations on documents, reference_docs, service_records, orders
            for tbl in ["vehicle_documents", "reference_documents", "service_records", "external_service_orders"]:
                _add_column_if_missing(cursor, tbl, "file_data", "BLOB")
                _add_column_if_missing(cursor, tbl, "file_name", "VARCHAR")
                _add_column_if_missing(cursor, tbl, "file_content_type", "VARCHAR")
                _add_column_if_missing(cursor, tbl, "file_size", "INTEGER")

            conn.connection.commit()
            cursor.close()
    except Exception:
        pass

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
