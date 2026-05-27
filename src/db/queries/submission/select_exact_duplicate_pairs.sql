SELECT submission_id, duplicate_of
FROM submission
WHERE import_id = %s AND status = 'exact_duplicate'
ORDER BY submission_id;
