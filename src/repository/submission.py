from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from db.connection import load_query
from model.submission import Submission, SubmissionDecision, SubmissionStatus

_INSERT = load_query("submission", "insert")
_SELECT_STATUS_COUNTS = load_query("submission", "select_status_counts")
_SELECT_INVALID_WITH_REASONS = load_query("submission", "select_invalid_with_reasons")
_SELECT_EXACT_DUPLICATE_PAIRS = load_query("submission", "select_exact_duplicate_pairs")
_SELECT_PENDING = load_query("submission", "select_pending")
_SELECT_UNMATCHED = load_query("submission", "select_unmatched")
_UPDATE_LLM_MATCH = load_query("submission", "update_llm_match")
_UPDATE_MATCH = load_query("submission", "update_match")
_SELECT_NEAR_DUPLICATE_GROUPS = load_query("submission", "select_near_duplicate_groups")
_UPDATE_NEAR_DUPLICATES = load_query("submission", "update_near_duplicates")
_SELECT_EXACT_DUPLICATE_GROUPS = load_query("submission", "select_exact_duplicate_groups")
_UPDATE_EXACT_DUPLICATES = load_query("submission", "update_exact_duplicates")
_UPDATE_DUPLICATE_MATCH = load_query("submission", "update_duplicate_match")
_SELECT_LLM_CACHE = load_query("submission", "select_llm_cache")


def insert(conn: psycopg.Connection, submission: Submission) -> None:
    with conn.cursor() as cur:
        cur.execute(
            _INSERT,
            (
                submission.submission_id,
                submission.import_id,
                Jsonb(submission.raw),
                submission.status,
                submission.name,
                submission.producer,
                submission.category,
                submission.vintage,
                submission.size_ml,
                submission.validation_error,
                submission.fingerprint,
                submission.duplicate_of,
            ),
        )


def get_status_counts(conn: psycopg.Connection, import_id: str) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute(_SELECT_STATUS_COUNTS, (import_id,))
        return dict(cur.fetchall())


def find_invalid_with_reasons(conn: psycopg.Connection, import_id: str) -> list[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(_SELECT_INVALID_WITH_REASONS, (import_id,))
        return cur.fetchall()


def exact_duplicates(conn: psycopg.Connection, import_id: str) -> list[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(_SELECT_EXACT_DUPLICATE_PAIRS, (import_id,))
        return cur.fetchall()


def find_pending(conn: psycopg.Connection, import_id: str) -> Iterator[Submission]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(_SELECT_PENDING, (import_id,))
        for row in cur:
            yield Submission.model_validate(row)


def find_unmatched(conn: psycopg.Connection, import_id: str) -> Iterator[Submission]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(_SELECT_UNMATCHED, (import_id,))
        for row in cur:
            yield Submission.model_validate(row)


def update_llm_match(
    conn: psycopg.Connection,
    submission_id: str,
    status: SubmissionStatus,
    decision: SubmissionDecision | None,
    matched_product_id: str | None,
    explanation: str | None,
    llm_confidence: float | None,
    llm_reason: str | None,
    llm_model: str | None,
    llm_prompt_version: str | None,
    llm_output: str | None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            _UPDATE_LLM_MATCH,
            (
                status, decision, matched_product_id, explanation,
                llm_confidence, llm_reason, llm_model,
                llm_prompt_version, llm_output,
                submission_id,
            ),
        )


def update_match(
    conn: psycopg.Connection,
    submission_id: str,
    status: SubmissionStatus,
    decision: SubmissionDecision | None,
    matched_product_id: str | None,
    explanation: str | None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            _UPDATE_MATCH,
            (status, decision, matched_product_id, explanation, submission_id),
        )


def get_near_duplicates(
    conn: psycopg.Connection, import_id: str
) -> list[tuple[str, list[str]]]:
    with conn.cursor() as cur:
        cur.execute(_SELECT_NEAR_DUPLICATE_GROUPS, (import_id,))
        return [(product_id, sids) for product_id, sids in cur.fetchall()]


def set_near_duplicates(
    conn: psycopg.Connection, submission_id: str, duplicate_of: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(_UPDATE_NEAR_DUPLICATES, (duplicate_of, submission_id))


def get_exact_duplicates(
    conn: psycopg.Connection, import_id: str
) -> list[tuple[str, list[str]]]:
    with conn.cursor() as cur:
        cur.execute(_SELECT_EXACT_DUPLICATE_GROUPS, (import_id,))
        return [(fingerprint, sids) for fingerprint, sids in cur.fetchall()]


def set_exact_duplicates(
    conn: psycopg.Connection, submission_id: str, duplicate_of: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(_UPDATE_EXACT_DUPLICATES, (duplicate_of, submission_id))


def find_llm_cache(
    conn: psycopg.Connection,
    model_id: str,
    prompt_version: str,
    fingerprint: str,
) -> str | None:
    with conn.cursor() as cur:
        cur.execute(_SELECT_LLM_CACHE, (model_id, prompt_version, fingerprint))
        row = cur.fetchone()
        return row[0] if row else None


def set_duplicate_match(
    conn: psycopg.Connection,
    survivor_id: str,
    matched_product_id: str | None,
    decision: SubmissionDecision | None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(_UPDATE_DUPLICATE_MATCH, (matched_product_id, decision, survivor_id))
