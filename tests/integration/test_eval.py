import json
import os
from pathlib import Path

import ijson
import pytest
from dotenv import load_dotenv

from service import submission as submission_service
from service.duplicates import identify_exact_duplicates, identify_near_duplicates
from gemini.client import Client
from service.match.llm import match_llm
from service.match.deterministic import match_deterministic

load_dotenv()

_EXERCISE_FILES = Path(__file__).resolve().parents[2] / "docs" / "ExerciseFiles"
_SUBMISSIONS_FILE = _EXERCISE_FILES / "product_matching_submissions.json"
_EVAL_FILE = _EXERCISE_FILES / "product_matching_eval.json"


@pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set; eval requires the LLM tier",
)
def test_eval_labels(db, seed_products):
    with open(_SUBMISSIONS_FILE, "rb") as f:
        submission_service.import_records(db, ijson.items(f, "item"), "eval-import")
    identify_exact_duplicates(db, "eval-import")
    match_deterministic(db, "eval-import")
    match_llm(db, Client(), "eval-import")
    identify_near_duplicates(db, "eval-import")

    labels = json.loads(_EVAL_FILE.read_text())["labels"]
    with db.cursor() as cur:
        cur.execute(
            "SELECT submission_id, status, decision, matched_product_id FROM submission"
        )
        rows = {sid: (status, decision, mpid) for sid, status, decision, mpid in cur.fetchall()}

    failures = []
    for label in labels:
        sid = label["submission_id"]
        expected_pid = label["expected_product_id"]
        acceptable = label["acceptable_decisions"]
        row = rows.get(sid)
        if row is None:
            failures.append(f"{sid}: not found in DB")
            continue
        status, decision, matched_pid = row

        # 'invalid' is a status in our model, not a decision class. Eval rows
        # that accept 'invalid' check status; everything else checks decision.
        if "invalid" in acceptable:
            if status != "invalid":
                failures.append(f"{sid}: expected status=invalid, got status={status}")
            if matched_pid is not None:
                failures.append(f"{sid}: expected matched_product_id=None, got {matched_pid}")
            continue

        if matched_pid != expected_pid:
            failures.append(
                f"{sid}: matched_product_id={matched_pid!r}, expected {expected_pid!r}"
            )
        if decision not in acceptable:
            failures.append(
                f"{sid}: decision={decision!r} not in acceptable={acceptable} "
                f"(matched {matched_pid}, note: {label.get('notes', '')!r})"
            )

    assert not failures, "Eval mismatches:\n  " + "\n  ".join(failures)
