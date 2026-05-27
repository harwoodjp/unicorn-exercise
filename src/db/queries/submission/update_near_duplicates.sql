-- Demotes a single matched row into the near-duplicate bucket. The
-- matched_product_id column is intentionally left as-is — it is the audit
-- trail explaining why this row was demoted.
UPDATE submission
SET status = 'near_duplicate',
    duplicate_of = %s
WHERE submission_id = %s;
