-- Groups of 2+ exact-match submissions sharing a matched_product_id. Predicate
-- is strictly status='matched': human_review rows also carry matched_product_id
-- but the near-dup rule requires high-confidence resolution. Survivor selection
-- (which submission_id wins within a cluster) is the service's job.
SELECT
    matched_product_id,
    array_agg(submission_id) AS submission_ids
FROM submission
WHERE import_id = %s AND status = 'matched'
GROUP BY matched_product_id
HAVING COUNT(*) > 1
ORDER BY matched_product_id;
