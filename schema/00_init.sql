-- Postgres' /docker-entrypoint-initdb.d does not recurse into subdirectories,
-- so this loader explicitly applies the per-folder schema files in the
-- required order: enums (referenced types) before tables (referencers).

\i /docker-entrypoint-initdb.d/enums/category.sql
\i /docker-entrypoint-initdb.d/enums/submission_status.sql
\i /docker-entrypoint-initdb.d/enums/submission_decision.sql

\i /docker-entrypoint-initdb.d/tables/product.sql
\i /docker-entrypoint-initdb.d/tables/submission.sql
