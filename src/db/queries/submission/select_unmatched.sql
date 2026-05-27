SELECT submission_id, import_id, raw_json AS raw, status,
       name, producer, category, vintage, size_ml,
       validation_error, fingerprint, duplicate_of,
       decision, matched_product_id, explanation,
       llm_confidence, llm_reason, llm_model, llm_prompt_version, llm_output
FROM submission
WHERE import_id = %s AND status = 'unmatched'
ORDER BY submission_id;
