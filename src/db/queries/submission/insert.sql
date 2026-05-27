INSERT INTO submission
    (submission_id, import_id, raw_json, status,
     name, producer, category, vintage, size_ml,
     validation_error, fingerprint, duplicate_of)
VALUES
    (%s, %s, %s, %s,
     %s, %s, %s, %s, %s,
     %s, %s, %s);
