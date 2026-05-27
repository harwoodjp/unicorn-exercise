CREATE TABLE product (
    product_id        TEXT     PRIMARY KEY,
    canonical_name    TEXT     NOT NULL,
    producer          TEXT     NOT NULL,
    category          category NOT NULL,
    size_ml           INTEGER  NOT NULL
                               CHECK (size_ml IN (50,100,200,375,500,700,750,1000,1500,3000,6000)),
    vintage_required  BOOLEAN  NOT NULL DEFAULT FALSE,

    -- Same canonical product at a different size is a distinct SKU.
    UNIQUE (canonical_name, producer, size_ml)
);
