\pset format aligned
\pset border 2
\pset linestyle unicode
\pset null '∅'

SELECT
    submission_id                            AS id,
    LEFT(COALESCE(producer, ''), 20)         AS producer,
    LEFT(COALESCE(name, ''), 35)             AS name,
    category,
    vintage                                  AS vint,
    size_ml                                  AS ml,
    status,
    decision,
    matched_product_id                       AS matched,
    ROUND(llm_confidence::numeric, 2)        AS conf,
    LEFT(COALESCE(explanation, llm_reason, validation_error, ''), 40) AS why
FROM submission
WHERE import_id = COALESCE(:'import_id', import_id)
ORDER BY status, submission_id;
