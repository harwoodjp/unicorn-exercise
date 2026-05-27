from dataclasses import dataclass

import psycopg

from gemini import prompts as gemini_prompts
from gemini.client import Client
from gemini.model import LLMDecision, LLMReason, MatchResult
from model.submission import (
    Submission,
    SubmissionDecision,
    SubmissionStatus,
)
from repository import product as product_repo
from repository import submission as submission_repo
from service.match.constants import PRODUCER_ALIASES

AUTO_APPLY_THRESHOLD = 0.85


@dataclass
class MatchSummary:
    processed: int = 0
    cache_hits: int = 0
    api_errors: int = 0
    auto_applied: int = 0
    sent_to_review: int = 0
    no_matches: int = 0


@dataclass
class Audit:
    confidence: float | None
    rationale: str | None
    model: str
    prompt_version: str | None
    output_text: str | None


def match_llm(conn: psycopg.Connection, client: Client, import_id: str) -> MatchSummary:
    summary = MatchSummary()
    catalog = product_repo.list_all(conn)
    model_id = client.model_id

    for submission in submission_repo.find_unmatched(conn, import_id):
        summary.processed += 1

        result = _from_cache(conn, submission, model_id)
        if result is not None:
            summary.cache_hits += 1
        else:
            try:
                result = client.generate(submission, catalog, PRODUCER_ALIASES)
            except Exception as e:
                error = f"{type(e).__name__}: {e}"
                print(error)
                summary.api_errors += 1
                _route_to_review(conn, submission, model_id, error)
                summary.sent_to_review += 1
                continue

        status = _apply(conn, submission, result, model_id)
        if status is SubmissionStatus.MATCHED:
            summary.auto_applied += 1
        elif status is SubmissionStatus.REVIEW:
            summary.sent_to_review += 1
        elif status is SubmissionStatus.NO_MATCH:
            summary.no_matches += 1

    return summary


def _from_cache(
    conn: psycopg.Connection, submission: Submission, model_id: str
) -> MatchResult | None:
    cached_output = submission_repo.find_llm_cache(
        conn, model_id, gemini_prompts.PROMPT_VERSION, submission.fingerprint,
    )
    if cached_output is None:
        return None
    return MatchResult(
        decision=LLMDecision.model_validate_json(cached_output),
        prompt_version=gemini_prompts.PROMPT_VERSION,
        output_text=cached_output,
    )


def _apply(
    conn: psycopg.Connection,
    submission: Submission,
    result: MatchResult,
    model_id: str,
) -> SubmissionStatus:
    decision = result.decision
    audit = Audit(
        confidence=decision.confidence,
        rationale=decision.reason,
        model=model_id,
        prompt_version=result.prompt_version,
        output_text=result.output_text,
    )

    if decision.decision == "no_match":
        return _set_no_match(conn, submission, LLMReason.LLM_NO_MATCH, audit=audit)

    candidate = decision.candidate_product_ids[0] if decision.candidate_product_ids else None

    if decision.decision == "human_review" or decision.confidence < AUTO_APPLY_THRESHOLD:
        return _set_human_review(conn, submission, LLMReason.LLM_HUMAN_REVIEW,
                                 matched_product_id=candidate, audit=audit)

    # Cap the LLM tier at possible_match. Per the rules doc, exact_match
    # requires deterministic resolution (direct match or alias table); anything
    # that needed LLM/fuzzy reasoning to resolve is possible_match by definition.
    return _set_possible_match(conn, submission, candidate, audit=audit)


def _route_to_review(
    conn: psycopg.Connection, submission: Submission, model_id: str, error_message: str
) -> SubmissionStatus:
    # Call didn't return — no output to log, but record the prompt version
    # we would have used so audit can pair the error with the prompt.
    audit = Audit(
        confidence=None,
        rationale=error_message,
        model=model_id,
        prompt_version=gemini_prompts.PROMPT_VERSION,
        output_text=None,
    )
    return _set_human_review(conn, submission, LLMReason.LLM_UNAVAILABLE, audit=audit)


def _set_possible_match(
    conn: psycopg.Connection,
    submission: Submission,
    matched_product_id: str | None,
    *,
    audit: Audit,
) -> SubmissionStatus:
    return _set_decision(conn, submission, SubmissionStatus.MATCHED, SubmissionDecision.POSSIBLE_MATCH,
                         matched_product_id=matched_product_id,
                         reason=LLMReason.LLM_POSSIBLE_MATCH, audit=audit)


def _set_human_review(
    conn: psycopg.Connection,
    submission: Submission,
    reason: LLMReason,
    *,
    matched_product_id: str | None = None,
    audit: Audit,
) -> SubmissionStatus:
    return _set_decision(conn, submission, SubmissionStatus.REVIEW, SubmissionDecision.HUMAN_REVIEW,
                         matched_product_id=matched_product_id, reason=reason, audit=audit)


def _set_no_match(
    conn: psycopg.Connection,
    submission: Submission,
    reason: LLMReason,
    *,
    audit: Audit,
) -> SubmissionStatus:
    return _set_decision(conn, submission, SubmissionStatus.NO_MATCH, SubmissionDecision.NO_MATCH,
                         reason=reason, audit=audit)


def _set_decision(
    conn: psycopg.Connection,
    submission: Submission,
    status: SubmissionStatus,
    decision: SubmissionDecision | None,
    *,
    matched_product_id: str | None = None,
    reason: LLMReason | None = None,
    audit: Audit,
) -> SubmissionStatus:
    submission_repo.update_llm_match(
        conn,
        submission_id=submission.submission_id,
        status=status,
        decision=decision,
        matched_product_id=matched_product_id,
        explanation=reason,
        llm_confidence=audit.confidence,
        llm_reason=audit.rationale,
        llm_model=audit.model,
        llm_prompt_version=audit.prompt_version,
        llm_output=audit.output_text,
    )
    submission_repo.set_duplicate_match(
        conn, submission.submission_id, matched_product_id, decision,
    )
    return status
