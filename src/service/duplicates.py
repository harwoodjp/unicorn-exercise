from dataclasses import dataclass

import psycopg

from repository import submission as submission_repo


@dataclass
class ExactDuplicateSummary:
    clusters: int = 0
    demoted: int = 0


@dataclass
class NearDuplicateSummary:
    clusters: int = 0
    demoted: int = 0


# Exact duplicate = same (name+producer+category+vintage+size_ml)
def identify_exact_duplicates(
    conn: psycopg.Connection, import_id: str
) -> ExactDuplicateSummary:
    summary = ExactDuplicateSummary()
    for _fingerprint, submission_ids in submission_repo.get_exact_duplicates(conn, import_id):
        survivor = min(submission_ids)
        duplicates = [s for s in submission_ids if s != survivor]
        for submission_id in duplicates:
            submission_repo.set_exact_duplicates(conn, submission_id, duplicate_of=survivor)
        summary.clusters += 1
        summary.demoted += len(duplicates)
    return summary


# Near duplicate: distinct submissions that match to the same product
def identify_near_duplicates(
    conn: psycopg.Connection, import_id: str
) -> NearDuplicateSummary:
    summary = NearDuplicateSummary()
    for _product_id, submission_ids in submission_repo.get_near_duplicates(conn, import_id):
        survivor = min(submission_ids)
        duplicates = [s for s in submission_ids if s != survivor]
        for submission_id in duplicates:
            submission_repo.set_near_duplicates(conn, submission_id, duplicate_of=survivor)
        summary.clusters += 1
        summary.demoted += len(duplicates)
    return summary
