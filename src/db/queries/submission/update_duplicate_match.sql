UPDATE submission
SET matched_product_id = %s,
    decision = %s
WHERE duplicate_of = %s
  AND status = 'exact_duplicate';
