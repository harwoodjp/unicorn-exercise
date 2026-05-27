import os
from pathlib import Path

import psycopg

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/postgres",
)

_QUERIES_DIR = Path(__file__).parent / "queries"


def connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def load_query(entity: str, name: str) -> str:
    return (_QUERIES_DIR / entity / f"{name}.sql").read_text()
