SELECT submission_id, validation_error
FROM submission
WHERE import_id = %s AND status = 'invalid'
ORDER BY submission_id;
