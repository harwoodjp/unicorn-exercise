SELECT product_id, canonical_name, producer, category, size_ml, vintage_required
FROM product
WHERE (%s::text IS NULL OR LOWER(producer) = LOWER(%s))
  AND (%s::text IS NULL OR category = %s::category)
  AND (%s::int  IS NULL OR size_ml = %s);
