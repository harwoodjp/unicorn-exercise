from dataclasses import dataclass

import psycopg

from model.product import Product
from model.submission import (
    MatchReason,
    Submission,
    SubmissionDecision,
    SubmissionStatus,
)
from repository import product as product_repo
from repository import submission as submission_repo
from service.match.constants import CATALOG_CATEGORIES, PRODUCER_ALIASES


@dataclass
class MatchSummary:
    exact_matches: int = 0
    human_reviews: int = 0
    no_matches: int = 0
    unmatched: int = 0


def match_deterministic(conn: psycopg.Connection, import_id: str) -> MatchSummary:
    summary = MatchSummary()
    for submission in submission_repo.find_pending(conn, import_id):
        status = _classify(conn, submission)
        if status is SubmissionStatus.MATCHED:
            summary.exact_matches += 1
        elif status is SubmissionStatus.REVIEW:
            summary.human_reviews += 1
        elif status is SubmissionStatus.NO_MATCH:
            summary.no_matches += 1
        elif status is SubmissionStatus.UNMATCHED:
            summary.unmatched += 1
    return summary


def _classify(conn: psycopg.Connection, submission: Submission) -> SubmissionStatus:
    if submission.category not in CATALOG_CATEGORIES:
        return _set_no_match(conn, submission, MatchReason.CATEGORY_MISMATCH)

    producer = _canonical_producer(submission.producer)
    products_at_size = product_repo.find(conn, producer, submission.category, submission.size_ml)
    candidates = _with_matching_name(submission.name, products_at_size)

    if len(candidates) == 1:
        candidate = candidates[0]
        if candidate.vintage_required and submission.vintage is None:
            return _set_human_review(conn, submission, MatchReason.VINTAGE_REQUIRED_MISSING,
                                     matched_product_id=candidate.product_id)
        return _set_exact_match(conn, submission, candidate.product_id)

    if len(candidates) > 1:
        return _set_human_review(conn, submission, MatchReason.MULTIPLE_CANDIDATES)

    # No matches at submission's size_ml. size_ml_is_a_discriminator: if exactly
    # one product matches the name at any other size, this is wrong-size no_match.
    products_at_any_size = product_repo.find(conn, producer, submission.category, size_ml=None)
    candidates = _with_matching_name(submission.name, products_at_any_size)
    if len(candidates) == 1:
        return _set_no_match(conn, submission, MatchReason.SIZE_ML_MISMATCH)

    # Deterministic logic could not decide. Decision is left NULL; Tier 2 will
    # assign one of {exact_match, possible_match, human_review, no_match} when
    # it processes the unmatched queue.
    return _set_decision(conn, submission, SubmissionStatus.UNMATCHED, decision=None)


def _with_matching_name(name: str, products: list[Product]) -> list[Product]:
    sub_tokens = set(_normalize(name).split())
    return [p for p in products if sub_tokens <= set(_normalize(p.canonical_name).split())]


def _set_exact_match(
    conn: psycopg.Connection,
    submission: Submission,
    matched_product_id: str,
) -> SubmissionStatus:
    return _set_decision(conn, submission, SubmissionStatus.MATCHED, SubmissionDecision.EXACT_MATCH,
                         matched_product_id=matched_product_id)


def _set_human_review(
    conn: psycopg.Connection,
    submission: Submission,
    reason: MatchReason,
    *,
    matched_product_id: str | None = None,
) -> SubmissionStatus:
    return _set_decision(conn, submission, SubmissionStatus.REVIEW, SubmissionDecision.HUMAN_REVIEW,
                         matched_product_id=matched_product_id, reason=reason)


def _set_no_match(
    conn: psycopg.Connection,
    submission: Submission,
    reason: MatchReason,
) -> SubmissionStatus:
    return _set_decision(conn, submission, SubmissionStatus.NO_MATCH, SubmissionDecision.NO_MATCH,
                         reason=reason)


def _set_decision(
    conn: psycopg.Connection,
    submission: Submission,
    status: SubmissionStatus,
    decision: SubmissionDecision | None,
    *,
    matched_product_id: str | None = None,
    reason: MatchReason | None = None,
) -> SubmissionStatus:
    submission_repo.update_match(
        conn,
        submission_id=submission.submission_id,
        status=status,
        decision=decision,
        matched_product_id=matched_product_id,
        explanation=reason,
    )
    submission_repo.set_duplicate_match(
        conn, submission.submission_id, matched_product_id, decision,
    )
    return status


def _normalize(s: str) -> str:
    cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in s.lower())
    return " ".join(cleaned.split())


def _canonical_producer(submitted: str) -> str:
    return PRODUCER_ALIASES.get(submitted.lower().strip(), submitted)
