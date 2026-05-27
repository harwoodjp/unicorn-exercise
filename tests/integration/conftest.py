import json
from pathlib import Path

import pytest

from db.connection import connect
from model.product import Product
from model.submission import Submission
from repository import product as product_repo
from repository import submission as submission_repo

_TABLES = ["submission", "product"]
_EXERCISE_FILES = Path(__file__).resolve().parents[2] / "docs" / "ExerciseFiles"
_CATALOG_FILE = _EXERCISE_FILES / "inventory_existing_catalog.json"
_SUBMISSIONS_FILE = _EXERCISE_FILES / "product_matching_submissions.json"


def _truncate(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(_TABLES)} CASCADE")
    conn.commit()


@pytest.fixture(scope="session")
def db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def clean_db(db):
    _truncate(db)
    yield
    _truncate(db)


@pytest.fixture
def seed_products(db) -> list[Product]:
    records = json.loads(_CATALOG_FILE.read_text())
    products = [Product.model_validate(r) for r in records]
    for product in products:
        product_repo.insert(db, product)
    db.commit()
    return products


@pytest.fixture
def seed_submissions(db) -> list[Submission]:
    records = json.loads(_SUBMISSIONS_FILE.read_text())
    submissions = [Submission.create(r, import_id="seed") for r in records]
    for submission in submissions:
        submission_repo.insert(db, submission)
    db.commit()
    return submissions
