-- Groups of 2+ submissions sharing a fingerprint within an import. Restricting
-- to status='pending' makes this step idempotent — already-demoted rows aren't
-- regrouped, and matched/invalid rows can't participate. Survivor selection
-- (which submission_id wins within a cluster) is the service's job.
SELECT
    fingerprint,
    array_agg(submission_id) AS submission_ids
FROM submission
WHERE import_id = %s
  AND status = 'pending'
  AND fingerprint IS NOT NULL
GROUP BY fingerprint
HAVING COUNT(*) > 1
ORDER BY fingerprint;
