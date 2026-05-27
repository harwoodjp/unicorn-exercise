import json
from pathlib import Path

from db.connection import connect
from model.product import Product
from repository import product as product_repo

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = PROJECT_ROOT / "docs" / "ExerciseFiles" / "inventory_existing_catalog.json"


def main() -> None:
    with open(CATALOG_PATH) as f:
        records = json.load(f)
    products = [Product.model_validate(r) for r in records]
    with connect() as conn:
        for product in products:
            product_repo.insert(conn, product)
    print(f"Loaded {len(products)} products from {CATALOG_PATH}")


if __name__ == "__main__":
    main()
