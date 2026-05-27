UPDATE submission
SET status = %s,
    decision = %s,
    matched_product_id = %s,
    explanation = %s,
    updated_at = NOW()
WHERE submission_id = %s AND status = 'pending';
