INSERT INTO product
    (product_id, canonical_name, producer, category, size_ml, vintage_required)
VALUES
    (%s, %s, %s, %s, %s, %s);
