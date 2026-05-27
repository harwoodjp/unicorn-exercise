from dataclasses import dataclass, field
from typing import Iterable

import psycopg

from model.submission import Submission
from repository import submission as submission_repo


@dataclass
class ImportSummary:
    total: int = 0
    inserted: int = 0
    skipped_missing_id: int = 0
    skipped_duplicate_id: list[str] = field(default_factory=list)


def import_records(
    conn: psycopg.Connection,
    records: Iterable[dict],
    import_id: str,
) -> ImportSummary:
    # Validate + insert. Exact-duplicate detection is a separate post-ingest
    # step (mark_exact_duplicates) so this loop stays single-pass and free
    # of O(N) in-memory state — relevant at the production volume of
    # hundreds-of-thousands to millions per import.
    summary = ImportSummary()
    for raw in records:
        summary.total += 1
        submission_id = raw.get("submission_id")
        if not submission_id:
            summary.skipped_missing_id += 1
            continue

        submission = Submission.create(raw, import_id)

        try:
            with conn.transaction():
                submission_repo.insert(conn, submission)
                summary.inserted += 1
        except psycopg.errors.UniqueViolation:
            summary.skipped_duplicate_id.append(submission.submission_id)

    return summary
