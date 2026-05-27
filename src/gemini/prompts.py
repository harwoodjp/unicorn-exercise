from model.product import Product
from model.submission import Submission

PROMPT_VERSION = "v2"

_SYSTEM_HEAD = """You match wine/spirits submissions to a canonical catalog. The deterministic tier already handled direct matches, the producer aliases listed below, and name-token-subset matches; you only see submissions it could not resolve.

DECISION CLASSES:
- possible_match: a single best candidate identified via abbreviation expansion or fuzzy reasoning
- no_match: no candidate fits, or a key attribute definitively disqualifies (size_ml mismatch)
- human_review: multiple plausible candidates remain, or producer disagrees in a way you can't reliably resolve

POLICIES:
- size_ml is a discriminator: different size = different SKU. Wrong-size candidate is no_match.
- vintage_required products: with a missing vintage, do not auto-match; route to human_review if a single line is identified.
- False positives are worse than false negatives. When in doubt prefer human_review over possible_match.

PRODUCER ALIASES (already applied by the deterministic tier):
"""

_CATALOG_HEADER = "\n\nCATALOG (product_id | producer | canonical_name | category | size_ml | vintage_required):\n"


def system_instruction(catalog: list[Product], producer_aliases: dict[str, str]) -> str:
    return _SYSTEM_HEAD + _render_aliases(producer_aliases) + _CATALOG_HEADER + _render_products(catalog)


def user_message(submission: Submission) -> str:
    return "Submission to match:\n" + _render_submission(submission)


def _render_aliases(aliases: dict[str, str]) -> str:
    return "\n".join(f"{alias} -> {canonical}" for alias, canonical in sorted(aliases.items()))


def _render_products(products: list[Product]) -> str:
    rows = sorted(products, key=lambda p: p.product_id)
    return "\n".join(
        f"{p.product_id} | {p.producer} | {p.canonical_name} | {p.category} | {p.size_ml} | {p.vintage_required}"
        for p in rows
    )


def _render_submission(submission: Submission) -> str:
    return (

        f"submission_id: {submission.submission_id}\n"
        f"name: {submission.name}\n"
        f"producer: {submission.producer}\n"
        f"category: {submission.category}\n"
        f"vintage: {submission.vintage}\n"
        f"size_ml: {submission.size_ml}"
    )
