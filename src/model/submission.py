import hashlib
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, TypeAdapter, ValidationError

_NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_SizeMl = Literal[50, 100, 200, 375, 500, 700, 750, 1000, 1500, 3000, 6000]
_Vintage = Annotated[int | None, Field(ge=1800, le=2026)]

# Per-field validators. Each field is checked independently so a single bad
# value (e.g. vintage="two thousand ten") doesn't suppress promotion of the
# fields that DID parse. Missing required fields surface as "Field required".
_FIELD_ADAPTERS: dict[str, TypeAdapter] = {
    "name": TypeAdapter(_NonEmptyStr),
    "producer": TypeAdapter(_NonEmptyStr),
    "category": TypeAdapter(_NonEmptyStr),
    "vintage": TypeAdapter(_Vintage),
    "size_ml": TypeAdapter(_SizeMl),
}
_REQUIRED_FIELDS = frozenset({"name", "producer", "category", "size_ml"})


def _validate_fields(raw: dict) -> tuple[dict, list[str]]:
    # Returns ({field: coerced_value, ...}, ["field: reason", ...]). The two
    # are independent: clean may be partial when errors is non-empty.
    clean: dict = {}
    errors: list[str] = []
    for field, adapter in _FIELD_ADAPTERS.items():
        if field not in raw:
            if field in _REQUIRED_FIELDS:
                errors.append(f"{field}: Field required")
            else:
                clean[field] = None
            continue
        try:
            clean[field] = adapter.validate_python(raw[field])
        except ValidationError as e:
            errors.append(f"{field}: {e.errors()[0]['msg']}")
    return clean, errors


class SubmissionStatus(StrEnum):
    PENDING = "pending"
    INVALID = "invalid"
    EXACT_DUPLICATE = "exact_duplicate"
    NEAR_DUPLICATE = "near_duplicate"
    MATCHED = "matched"
    REVIEW = "review"
    NO_MATCH = "no_match"
    UNMATCHED = "unmatched"


class SubmissionDecision(StrEnum):
    EXACT_MATCH = "exact_match"
    POSSIBLE_MATCH = "possible_match"
    HUMAN_REVIEW = "human_review"
    NO_MATCH = "no_match"


class MatchReason(StrEnum):
    # Named policies from product_matching_rules.json. Stored verbatim in
    # submission.explanation so audit/eval can group by reason.
    CATEGORY_MISMATCH = "category_mismatch"
    VINTAGE_REQUIRED_MISSING = "vintage_required_missing"
    SIZE_ML_MISMATCH = "size_ml_mismatch"
    MULTIPLE_CANDIDATES = "multiple_candidates"


def _fingerprint(name: str, producer: str, category: str, vintage: int | None, size_ml: int) -> str:
    payload = "|".join([
        name.strip(),
        producer.strip(),
        category.strip(),
        "" if vintage is None else str(vintage),
        str(size_ml),
    ])
    return hashlib.sha256(payload.encode()).hexdigest()


class Submission(BaseModel):
    submission_id: str
    import_id: str
    raw: dict
    status: SubmissionStatus = SubmissionStatus.PENDING
    name: str | None = None
    producer: str | None = None
    category: str | None = None
    vintage: int | None = None
    size_ml: int | None = None
    validation_error: str | None = None
    fingerprint: str | None = None
    duplicate_of: str | None = None
    decision: SubmissionDecision | None = None
    matched_product_id: str | None = None
    explanation: str | None = None
    llm_confidence: float | None = None
    llm_reason: str | None = None
    llm_model: str | None = None
    llm_prompt_version: str | None = None
    llm_output: str | None = None

    @classmethod
    def create(cls, raw: dict, import_id: str) -> "Submission":
        submission_id = raw["submission_id"]
        clean, errors = _validate_fields(raw)
        if errors:
            # Invalid: promote whatever fields parsed cleanly; the bad ones
            # stay NULL. Fingerprint is left unset so invalid records don't
            # participate in exact-duplicate detection.
            return cls(
                submission_id=submission_id,
                import_id=import_id,
                raw=raw,
                status=SubmissionStatus.INVALID,
                validation_error="; ".join(errors),
                name=clean.get("name"),
                producer=clean.get("producer"),
                category=clean.get("category"),
                vintage=clean.get("vintage"),
                size_ml=clean.get("size_ml"),
            )
        return cls(
            submission_id=submission_id,
            import_id=import_id,
            raw=raw,
            name=clean["name"],
            producer=clean["producer"],
            category=clean["category"],
            vintage=clean["vintage"],
            size_ml=clean["size_ml"],
            fingerprint=_fingerprint(
                clean["name"], clean["producer"], clean["category"],
                clean["vintage"], clean["size_ml"],
            ),
        )
