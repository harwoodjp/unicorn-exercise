  docker exec -i postgres psql -U postgres -d postgres -c "TRUNCATE submission, product CASCADE;" >/dev/null \
    && uv run python -m scripts.import_products \
    && uv run python -m pipeline.ingest
