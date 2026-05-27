import psycopg

from db.connection import load_query
from model.product import Product

_INSERT = load_query("product", "insert")
_FIND = load_query("product", "find")
_LIST_ALL = load_query("product", "list_all")


def insert(conn: psycopg.Connection, product: Product) -> None:
    with conn.cursor() as cur:
        cur.execute(
            _INSERT,
            (
                product.product_id,
                product.canonical_name,
                product.producer,
                product.category,
                product.size_ml,
                product.vintage_required,
            ),
        )


def find(
    conn: psycopg.Connection,
    producer: str | None = None,
    category: str | None = None,
    size_ml: int | None = None,
) -> list[Product]:
    # Each filter is independent — pass any subset. Producer is case-insensitive.
    with conn.cursor() as cur:
        cur.execute(_FIND, (producer, producer, category, category, size_ml, size_ml))
        return [_row_to_product(row) for row in cur.fetchall()]


def list_all(conn: psycopg.Connection) -> list[Product]:
    with conn.cursor() as cur:
        cur.execute(_LIST_ALL)
        return [_row_to_product(row) for row in cur.fetchall()]


def _row_to_product(row) -> Product:
    return Product(
        product_id=row[0],
        canonical_name=row[1],
        producer=row[2],
        category=row[3],
        size_ml=row[4],
        vintage_required=row[5],
    )
