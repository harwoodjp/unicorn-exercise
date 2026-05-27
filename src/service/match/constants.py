from typing import get_args

from model.product import Category

CATALOG_CATEGORIES = frozenset(get_args(Category))

PRODUCER_ALIASES: dict[str, str] = {
    "macallan":                       "The Macallan",
    "suntory hibiki":                 "Suntory",
    "old rip van winkle distillery":  "Old Rip Van Winkle",
    "van winkle":                     "Old Rip Van Winkle",
    "lafite rothschild":              "Chateau Lafite Rothschild",
    "drc":                            "Domaine de la Romanee-Conti",
}
