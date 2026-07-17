from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import Column

from workbench.database.models import Base


def sqlite_url(database_path: Path) -> str:
    return f"sqlite:///{database_path.expanduser().resolve()}"


def create_sqlite_engine(database_path: Path) -> Engine:
    database_path.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(sqlite_url(database_path), future=True)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def initialize_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    ensure_schema_upgrades(engine)


def ensure_schema_upgrades(engine: Engine) -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns or not column.nullable:
                    continue
                column_sql = _compile_column_for_sqlite(column, engine)
                connection.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column_sql}"))


def _compile_column_for_sqlite(column: Column[Any], engine: Engine) -> str:
    column_type = column.type.compile(dialect=engine.dialect)
    return f"{column.name} {column_type}"


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
