UPDATE submission
SET status = %s,
    decision = %s,
    matched_product_id = %s,
    explanation = %s,
    llm_confidence = %s,
    llm_reason = %s,
    llm_model = %s,
    llm_prompt_version = %s,
    llm_output = %s,
    updated_at = NOW()
WHERE submission_id = %s AND status = 'unmatched';
