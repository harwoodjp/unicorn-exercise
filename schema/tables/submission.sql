CREATE TABLE submission (
    submission_id      TEXT                PRIMARY KEY,
    import_id          TEXT                NOT NULL,
    name               TEXT,
    producer           TEXT,
    -- Submission category is intentionally TEXT, not the `category` enum:
    -- the rules allow any value to pass validation; non-catalog values
    -- simply produce no_match at match time.
    category           TEXT,
    vintage            INTEGER,
    size_ml            INTEGER,

    -- Original record kept verbatim for replay and audit; promoted columns
    -- above are denormalized for query and index efficiency.
    raw_json           JSONB               NOT NULL,

    status             submission_status   NOT NULL DEFAULT 'pending',
    decision           submission_decision,
    matched_product_id TEXT                REFERENCES product(product_id),
    explanation        TEXT,
    llm_confidence     REAL                CHECK (llm_confidence IS NULL
                                                  OR (llm_confidence >= 0 AND llm_confidence <= 1)),
    llm_reason         TEXT,
    llm_model          TEXT,
    llm_prompt_version TEXT,
    llm_output         TEXT,
    validation_error   TEXT,
    duplicate_of       TEXT                REFERENCES submission(submission_id),
    fingerprint        TEXT,

    created_at         TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

-- Resume query (status='pending' for an in-flight import) and bucket counts
-- by status both ride this compound index.
CREATE INDEX submission_import_status_idx ON submission (import_id, status);

-- Dedup: GROUP BY fingerprint to find exact duplicates,
-- equality lookup to find the near-duplicate cohort for a new record.
CREATE INDEX submission_fingerprint_idx   ON submission (fingerprint);
