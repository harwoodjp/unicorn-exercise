-- Demotes a single pending row into the exact-duplicate bucket. Mirrors
-- set_near_duplicates; the duplicate_of column points at the surviving sibling.
UPDATE submission
SET status = 'exact_duplicate',
    duplicate_of = %s
WHERE submission_id = %s;
