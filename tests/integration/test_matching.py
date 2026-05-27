from gemini import prompts as gemini_prompts
from gemini.model import LLMDecision
from model.product import Product
from model.submission import Submission, SubmissionDecision, SubmissionStatus
from repository import product as product_repo
from repository import submission as submission_repo
from service.match.llm import match_llm
from service.match.deterministic import match_deterministic
from service.duplicates import identify_near_duplicates

_IMPORT_ID = "test-matching"


def _insert_product(db, **overrides) -> Product:
    defaults = dict(
        product_id="PROD-1",
        canonical_name="Chateau Margaux",
        producer="Chateau Margaux",
        category="Wine",
        size_ml=750,
        vintage_required=False,
    )
    defaults.update(overrides)
    product = Product(**defaults)
    product_repo.insert(db, product)
    db.commit()
    return product


def _insert_submission(db, *, import_id: str = _IMPORT_ID, **overrides) -> Submission:
    defaults = dict(
        submission_id="SUB-1",
        name="Chateau Margaux",
        producer="Chateau Margaux",
        category="Wine",
        vintage=2015,
        size_ml=750,
    )
    defaults.update(overrides)
    submission = Submission.create(defaults, import_id=import_id)
    submission_repo.insert(db, submission)
    db.commit()
    return submission


def _status(db, submission_id: str) -> tuple[str, str | None, str | None]:
    with db.cursor() as cur:
        cur.execute(
            "SELECT status, decision, matched_product_id FROM submission WHERE submission_id = %s",
            (submission_id,),
        )
        return cur.fetchone()


def test_exact_match_happy_path(db):
    _insert_product(db, product_id="PROD-1")
    _insert_submission(db, submission_id="SUB-1")

    summary = match_deterministic(db, _IMPORT_ID)

    assert summary.exact_matches == 1
    assert _status(db, "SUB-1") == ("matched", "exact_match", "PROD-1")


def test_normalization_allows_case_and_punctuation_differences(db):
    _insert_product(db, canonical_name="Chateau Margaux")
    _insert_submission(db, submission_id="SUB-1", name="  chateau-margaux  ")

    summary = match_deterministic(db, _IMPORT_ID)

    assert summary.exact_matches == 1
    assert _status(db, "SUB-1")[0] == "matched"


def test_unknown_category_emits_no_match(db):
    # Rules: category_mismatch -> no_match regardless of name similarity.
    _insert_product(db)
    _insert_submission(db, submission_id="SUB-1", category="Beer")

    summary = match_deterministic(db, _IMPORT_ID)

    assert summary.exact_matches == 0
    assert summary.no_matches == 1
    assert _status(db, "SUB-1") == ("no_match", "no_match", None)


def test_no_candidates_routes_to_unmatched(db):
    _insert_product(db, producer="Chateau Margaux")
    _insert_submission(db, submission_id="SUB-1", producer="Chateau Latour")

    summary = match_deterministic(db, _IMPORT_ID)

    assert summary.exact_matches == 0
    assert summary.unmatched == 1
    assert _status(db, "SUB-1") == ("unmatched", None, None)


def test_name_mismatch_routes_to_unmatched(db):
    # Producer + category + size_ml match, but name doesn't normalize-equal.
    _insert_product(db, canonical_name="Chateau Margaux")
    _insert_submission(db, submission_id="SUB-1", name="Chateau Latour")

    summary = match_deterministic(db, _IMPORT_ID)

    assert summary.exact_matches == 0
    assert summary.unmatched == 1
    assert _status(db, "SUB-1") == ("unmatched", None, None)


def test_token_subset_matches_when_submission_trims_canonical_suffix(db):
    # Submissions commonly omit the trailing category/marketing tail
    # ("Cognac", "Single Malt Scotch Whisky"). Token-subset within a fixed
    # (producer, category, size_ml) candidate set picks these up.
    _insert_product(db, canonical_name="Hennessy Paradis Cognac", producer="Hennessy", category="Cognac")
    _insert_submission(db, submission_id="SUB-1", name="Hennessy Paradis", producer="Hennessy", category="Cognac", vintage=None)

    summary = match_deterministic(db, _IMPORT_ID)

    assert summary.exact_matches == 1
    assert _status(db, "SUB-1") == ("matched", "exact_match", "PROD-1")


def test_token_subset_with_multiple_candidates_routes_to_human_review(db):
    # Short submission ("Macallan") is a subset of two sibling SKUs. False-
    # positive policy: do not pick one — route to human_review.
    _insert_product(db, product_id="PROD-1",
                    canonical_name="The Macallan 18 Year Old Sherry Oak Single Malt Scotch Whisky",
                    producer="The Macallan", category="Whisky")
    _insert_product(db, product_id="PROD-2",
                    canonical_name="The Macallan 12 Year Old Double Cask Single Malt Scotch Whisky",
                    producer="The Macallan", category="Whisky")
    _insert_submission(db, submission_id="SUB-1", name="Macallan",
                       producer="The Macallan", category="Whisky", vintage=None)

    summary = match_deterministic(db, _IMPORT_ID)

    assert summary.exact_matches == 0
    assert summary.human_reviews == 1
    assert _status(db, "SUB-1") == ("review", "human_review", None)


def test_multiple_normalize_equal_candidates_routes_to_human_review(db):
    # Two catalog rows whose canonical names normalize to the same string.
    # Rules: multiple plausible candidates remain -> human_review.
    _insert_product(db, product_id="PROD-1", canonical_name="Chateau Margaux")
    _insert_product(db, product_id="PROD-2", canonical_name="chateau-margaux")
    _insert_submission(db, submission_id="SUB-1", name="Chateau Margaux")

    summary = match_deterministic(db, _IMPORT_ID)

    assert summary.exact_matches == 0
    assert summary.human_reviews == 1
    # matched_product_id is null — surfacing one of N would be misleading.
    assert _status(db, "SUB-1") == ("review", "human_review", None)


def test_size_mismatch_emits_no_match(db):
    # Rules: size_ml_is_a_discriminator -> size mismatch with the only
    # candidate must produce no_match, not pending/possible_match.
    _insert_product(db, product_id="PROD-1", canonical_name="Chateau Margaux", size_ml=750)
    _insert_submission(db, submission_id="SUB-1", name="Chateau Margaux", size_ml=1500)

    summary = match_deterministic(db, _IMPORT_ID)

    assert summary.exact_matches == 0
    assert summary.no_matches == 1
    assert _status(db, "SUB-1") == ("no_match", "no_match", None)


def test_vintage_required_but_missing_routes_to_human_review(db):
    # Rules: single candidate identified + vintage_required + vintage missing
    # -> human_review (not no_match, not exact_match).
    _insert_product(db, product_id="PROD-1", vintage_required=True)
    _insert_submission(db, submission_id="SUB-1", vintage=None)

    summary = match_deterministic(db, _IMPORT_ID)

    assert summary.exact_matches == 0
    assert summary.human_reviews == 1
    assert _status(db, "SUB-1") == ("review", "human_review", "PROD-1")


def test_vintage_required_and_present_matches(db):
    _insert_product(db, vintage_required=True)
    _insert_submission(db, submission_id="SUB-1", vintage=2015)

    summary = match_deterministic(db, _IMPORT_ID)

    assert summary.exact_matches == 1
    assert _status(db, "SUB-1")[0] == "matched"


def test_mark_near_duplicates_demotes_tail_to_survivor(db):
    # Two submissions that both exact_match the same product form a near-dup
    # cluster. Different vintages make different fingerprints (so they're not
    # exact duplicates) but vintage_required=false means both still resolve.
    _insert_product(db, product_id="PROD-1", vintage_required=False)
    _insert_submission(db, submission_id="SUB-B", vintage=2015)
    _insert_submission(db, submission_id="SUB-A", vintage=2016)
    _insert_submission(db, submission_id="SUB-C", vintage=2017)
    match_deterministic(db, _IMPORT_ID)

    summary = identify_near_duplicates(db, _IMPORT_ID)

    assert summary.clusters == 1
    assert summary.demoted == 2
    # Survivor is lexicographically lowest submission_id, deterministic on rerun.
    assert _status(db, "SUB-A") == ("matched", "exact_match", "PROD-1")
    # Tail keeps matched_product_id as the audit trail for why it was demoted.
    assert _status(db, "SUB-B") == ("near_duplicate", "exact_match", "PROD-1")
    assert _status(db, "SUB-C") == ("near_duplicate", "exact_match", "PROD-1")

    with db.cursor() as cur:
        cur.execute(
            "SELECT submission_id, duplicate_of FROM submission "
            "WHERE status = 'near_duplicate' ORDER BY submission_id"
        )
        assert cur.fetchall() == [("SUB-B", "SUB-A"), ("SUB-C", "SUB-A")]


def test_mark_near_duplicates_is_idempotent(db):
    _insert_product(db, product_id="PROD-1", vintage_required=False)
    _insert_submission(db, submission_id="SUB-A", vintage=2015)
    _insert_submission(db, submission_id="SUB-B", vintage=2016)
    match_deterministic(db, _IMPORT_ID)
    identify_near_duplicates(db, _IMPORT_ID)

    rerun = identify_near_duplicates(db, _IMPORT_ID)

    assert rerun.clusters == 0
    assert rerun.demoted == 0


def test_llm_match_serves_cache_hit_without_calling_api(db):
    # Same content (=> same fingerprint) + same model + same prompt version
    # served from a prior import. The LLM client must not be invoked.
    fake_model = "test-model"

    class _FakeClient:
        model_id = fake_model

        def generate(self, *_args, **_kwargs):
            raise AssertionError("LLM called despite warm cache")

    _insert_product(db, product_id="PROD-1")

    # Prior import: seed an already-resolved cache row.
    cached_output = LLMDecision(
        decision="possible_match",
        confidence=0.9,
        candidate_product_ids=["PROD-1"],
        reason="prior call",
    ).model_dump_json()
    _insert_submission(db, submission_id="PRIOR", import_id="prior")
    with db.cursor() as cur:
        cur.execute("UPDATE submission SET status='unmatched' WHERE submission_id='PRIOR'")
    submission_repo.update_llm_match(
        db, submission_id="PRIOR",
        status=SubmissionStatus.MATCHED, decision=SubmissionDecision.POSSIBLE_MATCH,
        matched_product_id="PROD-1", explanation="llm_possible_match",
        llm_confidence=0.9, llm_reason="prior call",
        llm_model=fake_model, llm_prompt_version=gemini_prompts.PROMPT_VERSION,
        llm_output=cached_output,
    )
    db.commit()

    # Current import: same content, different submission_id, status=unmatched
    # so match_llm picks it up.
    _insert_submission(db, submission_id="CUR", import_id="current")
    with db.cursor() as cur:
        cur.execute("UPDATE submission SET status='unmatched' WHERE submission_id='CUR'")
    db.commit()

    summary = match_llm(db, _FakeClient(), "current")

    assert summary.processed == 1
    assert summary.cache_hits == 1
    assert summary.api_errors == 0
    assert summary.auto_applied == 1

    assert _status(db, "CUR") == ("matched", "possible_match", "PROD-1")

    with db.cursor() as cur:
        cur.execute(
            "SELECT llm_model, llm_prompt_version, llm_output, llm_confidence "
            "FROM submission WHERE submission_id = 'CUR'"
        )
        assert cur.fetchone() == (
            fake_model, gemini_prompts.PROMPT_VERSION, cached_output, 0.9,
        )


def test_llm_match_routes_to_review_on_non_api_exception(db):
    # Spirit of "import always completes": any failure of the LLM call —
    # not just APIError — must route to review rather than crash. Pre-fix
    # this would have propagated and aborted the whole match_llm loop.
    fake_model = "test-model"

    class _FakeClient:
        model_id = fake_model

        def generate(self, *_a, **_kw):
            raise RuntimeError("No parsed response for SUB-X")

    _insert_product(db, product_id="PROD-1")
    _insert_submission(db, submission_id="SUB-X", import_id="current")
    with db.cursor() as cur:
        cur.execute("UPDATE submission SET status='unmatched' WHERE submission_id='SUB-X'")
    db.commit()

    summary = match_llm(db, _FakeClient(), "current")

    assert summary.processed == 1
    assert summary.api_errors == 1
    assert summary.sent_to_review == 1
    assert summary.auto_applied == 0

    with db.cursor() as cur:
        cur.execute(
            "SELECT status, decision, explanation, llm_reason "
            "FROM submission WHERE submission_id = 'SUB-X'"
        )
        status, decision, explanation, llm_reason = cur.fetchone()
        assert (status, decision, explanation) == ("review", "human_review", "llm_unavailable")
        # Exception class name is in the audit trail so operators can tell
        # a code/schema bug apart from real API unavailability.
        assert llm_reason.startswith("RuntimeError:")


def test_mark_near_duplicates_ignores_review_rows_sharing_a_product(db):
    # human_review rows can carry matched_product_id (vintage-missing path) but
    # are not high-confidence — they must not cluster.
    _insert_product(db, product_id="PROD-1", vintage_required=True)
    _insert_submission(db, submission_id="SUB-A", vintage=None)
    _insert_submission(db, submission_id="SUB-B", vintage=None)
    match_deterministic(db, _IMPORT_ID)

    summary = identify_near_duplicates(db, _IMPORT_ID)

    assert summary.clusters == 0
    assert _status(db, "SUB-A")[0] == "review"
    assert _status(db, "SUB-B")[0] == "review"
