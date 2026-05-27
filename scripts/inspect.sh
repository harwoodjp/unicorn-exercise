#!/usr/bin/env bash
set -euo pipefail
docker exec -i postgres psql -U postgres -d postgres -f - < scripts/pretty_submissions.sql
