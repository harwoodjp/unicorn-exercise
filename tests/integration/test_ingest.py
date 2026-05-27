from pathlib import Path

import ijson

from service import submission as submission_service
from service.duplicates import identify_exact_duplicates, identify_near_duplicates
from service.match.deterministic import match_deterministic

_SUBMISSIONS_FILE = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "ExerciseFiles"
    / "product_matching_submissions.json"
)


def test_ingest_summary_and_status_counts(db):
    with open(_SUBMISSIONS_FILE, "rb") as f:
        import_summary = submission_service.import_records(db, ijson.items(f, "item"), "test-import")

    # import_records is now validate + insert only. Dedup is a separate step.
    assert import_summary.total == 34
    assert import_summary.inserted == 34
    assert import_summary.skipped_missing_id == 0
    assert import_summary.skipped_duplicate_id == []

    with db.cursor() as cur:
        cur.execute("SELECT status, COUNT(*) FROM submission GROUP BY status")
        counts = dict(cur.fetchall())
        # All non-invalid records still pending — dedup hasn't run yet.
        assert counts == {"pending": 30, "invalid": 4}

        cur.execute(
            "SELECT submission_id FROM submission "
            "WHERE status = 'invalid' ORDER BY submission_id"
        )
        invalid_ids = [row[0] for row in cur.fetchall()]
        assert invalid_ids == ["SUB-2028", "SUB-2029", "SUB-2030", "SUB-2031"]

    dedup_summary = identify_exact_duplicates(db, "test-import")

    assert dedup_summary.clusters == 1
    assert dedup_summary.demoted == 1

    with db.cursor() as cur:
        cur.execute("SELECT status, COUNT(*) FROM submission GROUP BY status")
        counts = dict(cur.fetchall())
        assert counts == {"pending": 29, "invalid": 4, "exact_duplicate": 1}

        cur.execute(
            "SELECT submission_id, duplicate_of FROM submission "
            "WHERE status = 'exact_duplicate'"
        )
        assert cur.fetchall() == [("SUB-2024", "SUB-2023")]


def test_exact_match(db, seed_products):
    with open(_SUBMISSIONS_FILE, "rb") as f:
        submission_service.import_records(db, ijson.items(f, "item"), "test-import")
    identify_exact_duplicates(db, "test-import")

    match_summary = match_deterministic(db, "test-import")
    near_dup_summary = identify_near_duplicates(db, "test-import")

    # exact_match = token-subset of canonical_name tokens within a fixed
    # (producer, category, size_ml) candidate set, with producer resolved
    # through PRODUCER_ALIASES first. Submissions deterministic rules still
    # can't decide (name abbreviations, fuzzy reasoning) land in 'unmatched' —
    # Tier 2's queue.
    assert match_summary.exact_matches == 15
    assert match_summary.human_reviews == 1
    assert match_summary.no_matches == 3
    assert match_summary.unmatched == 10
    assert near_dup_summary.clusters == 3
    assert near_dup_summary.demoted == 3

    with db.cursor() as cur:
        cur.execute("SELECT status, COUNT(*) FROM submission GROUP BY status")
        counts = dict(cur.fetchall())
        assert counts == {
            "matched": 12,
            "near_duplicate": 3,
            "review": 1,
            "no_match": 3,
            "exact_duplicate": 1,
            "invalid": 4,
            "unmatched": 10,
        }

        cur.execute(
            "SELECT submission_id, matched_product_id, decision FROM submission "
            "WHERE status = 'matched' ORDER BY submission_id"
        )
        matches = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
        assert matches == {
            "SUB-2001": ("PROD-0001", "exact_match"),
            "SUB-2002": ("PROD-0003", "exact_match"),
            "SUB-2003": ("PROD-0011", "exact_match"),
            "SUB-2004": ("PROD-0020", "exact_match"),
            "SUB-2005": ("PROD-0017", "exact_match"),
            "SUB-2006": ("PROD-0012", "exact_match"),
            "SUB-2012": ("PROD-0007", "exact_match"),
            "SUB-2017": ("PROD-0004", "exact_match"),
            "SUB-2018": ("PROD-0009", "exact_match"),
            "SUB-2023": ("PROD-0002", "exact_match"),
            "SUB-2026": ("PROD-0024", "exact_match"),
            "SUB-2033": ("PROD-0014", "exact_match"),
        }

        # Near-dup cohorts: PROD-0001 (Macallan via alias), PROD-0024 (Hennessy
        # Paradis ± "Cognac" suffix), PROD-0014 (Chateau Margaux at different
        # vintages). Lex-min survives; the tail keeps matched_product_id as
        # audit trail.
        cur.execute(
            "SELECT submission_id, matched_product_id, duplicate_of FROM submission "
            "WHERE status = 'near_duplicate' ORDER BY submission_id"
        )
        assert cur.fetchall() == [
            ("SUB-2007", "PROD-0001", "SUB-2001"),
            ("SUB-2027", "PROD-0024", "SUB-2026"),
            ("SUB-2034", "PROD-0014", "SUB-2033"),
        ]

        cur.execute(
            "SELECT submission_id, decision, explanation FROM submission "
            "WHERE status = 'no_match' ORDER BY submission_id"
        )
        assert cur.fetchall() == [
            ("SUB-2015", "no_match", "size_ml_mismatch"),
            ("SUB-2016", "no_match", "size_ml_mismatch"),
            ("SUB-2021", "no_match", "category_mismatch"),
        ]

        cur.execute(
            "SELECT submission_id, matched_product_id, decision, explanation FROM submission "
            "WHERE status = 'review' ORDER BY submission_id"
        )
        reviews = cur.fetchall()
        assert reviews == [("SUB-2032", "PROD-0014", "human_review", "vintage_required_missing")]

        cur.execute(
            "SELECT submission_id, matched_product_id, decision, duplicate_of FROM submission "
            "WHERE status = 'exact_duplicate' ORDER BY submission_id"
        )
        assert cur.fetchall() == [("SUB-2024", "PROD-0002", "exact_match", "SUB-2023")]
