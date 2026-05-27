from typing import Literal

from pydantic import BaseModel

Category = Literal["Wine", "Whisky", "Bourbon", "Tequila", "Rum", "Cognac"]


class Product(BaseModel):
    product_id: str
    canonical_name: str
    producer: str
    category: Category
    size_ml: int
    vintage_required: bool = False
