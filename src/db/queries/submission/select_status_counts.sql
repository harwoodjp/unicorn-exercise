SELECT status, COUNT(*)
FROM submission
WHERE import_id = %s
GROUP BY status
ORDER BY status;
