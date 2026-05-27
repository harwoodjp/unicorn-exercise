import uuid
from pathlib import Path

import ijson
from dotenv import load_dotenv

load_dotenv()

from db.connection import connect
from gemini.client import Client
from repository import submission as submission_repo
from service import submission as submission_service
from service.duplicates import (
    ExactDuplicateSummary,
    NearDuplicateSummary,
    identify_exact_duplicates,
    identify_near_duplicates,
)
from service.match import deterministic, llm
from service.match.deterministic import match_deterministic
from service.match.llm import match_llm
from service.submission import ImportSummary

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUBMISSIONS_PATH = PROJECT_ROOT / "docs" / "ExerciseFiles" / "product_matching_submissions.json"


def main() -> None:
    import_id = str(uuid.uuid4())
    with open(SUBMISSIONS_PATH, "rb") as f, connect() as conn:
        import_summary = submission_service.import_records(conn, ijson.items(f, "item"), import_id)
        exact_dup_summary = identify_exact_duplicates(conn, import_id)
        match_summary = match_deterministic(conn, import_id)
        llm_summary = match_llm(conn, Client(), import_id)
        near_dup_summary = identify_near_duplicates(conn, import_id)
        status_counts = submission_repo.get_status_counts(conn, import_id)
        invalid_records = submission_repo.find_invalid_with_reasons(conn, import_id)
        duplicate_pairs = submission_repo.exact_duplicates(conn, import_id)
    _print_report(
        import_id, import_summary, exact_dup_summary, match_summary, near_dup_summary,
        llm_summary, status_counts, invalid_records, duplicate_pairs,
    )


def _print_report(
    import_id: str,
    import_summary: ImportSummary,
    exact_dup_summary: ExactDuplicateSummary,
    match_summary: deterministic.MatchSummary,
    near_dup_summary: NearDuplicateSummary,
    llm_summary: llm.MatchSummary,
    status_counts: dict[str, int],
    invalid_records: list[tuple[str, str]],
    duplicate_pairs: list[tuple[str, str]],
) -> None:
    invalid_count = status_counts.get("invalid", 0)
    valid = import_summary.inserted - invalid_count
    into_matching = valid - exact_dup_summary.demoted

    def row(label: str, value: int, *, indent: int = 0, note: str = "") -> None:
        pad = "  " * (indent + 1)
        suffix = f"   {note}" if note else ""
        print(f"{pad}{label:<38} {value:>5}{suffix}")

    print(f"\nimport_id={import_id}")

    print("\nFinal status:")
    for status, count in status_counts.items():
        print(f"  {status:<18} {count:>5}")
    print(f"  {'-' * 18} {'-' * 5}")
    print(f"  {'total':<18} {sum(status_counts.values()):>5}")

    print("\nPipeline:")

    row("read from source", import_summary.total)
    row("skipped (no submission_id)", import_summary.skipped_missing_id, indent=1)
    row("skipped (duplicate submission_id)", len(import_summary.skipped_duplicate_id), indent=1,
        note=str(import_summary.skipped_duplicate_id) if import_summary.skipped_duplicate_id else "")
    row("inserted", import_summary.inserted, indent=1)

    print()
    row("inserted", import_summary.inserted)
    row("invalid (failed validation)", invalid_count, indent=1)
    row("valid", valid, indent=1)

    print()
    row("valid", valid)
    row("exact duplicates demoted", exact_dup_summary.demoted, indent=1,
        note=f"({exact_dup_summary.clusters} clusters)")
    row("into matching", into_matching, indent=1)

    print()
    print("  tier 1 - deterministic")
    row("processed", into_matching, indent=1)
    row("exact_match", match_summary.exact_matches, indent=2)
    row("human_review", match_summary.human_reviews, indent=2)
    row("no_match", match_summary.no_matches, indent=2)
    row("to tier 2 (unmatched)", match_summary.unmatched, indent=2)

    print()
    print("  tier 2 - LLM")
    row("processed", llm_summary.processed, indent=1,
        note=f"(cache hits: {llm_summary.cache_hits}, api errors: {llm_summary.api_errors})")
    row("auto-applied (possible_match)", llm_summary.auto_applied, indent=2)
    row("sent to review", llm_summary.sent_to_review, indent=2)
    row("no_match", llm_summary.no_matches, indent=2)

    print()
    print("  near-duplicate sweep")
    row("demoted from matched", near_dup_summary.demoted, indent=1,
        note=f"({near_dup_summary.clusters} clusters)")

    if invalid_records:
        print("\nInvalid records:")
        for sid, error in invalid_records:
            print(f"  {sid}: {error or ''}")

    if duplicate_pairs:
        print("\nDuplicate pairs:")
        for sid, dup_of in duplicate_pairs:
            print(f"  {sid} -> {dup_of}")


if __name__ == "__main__":
    main()
