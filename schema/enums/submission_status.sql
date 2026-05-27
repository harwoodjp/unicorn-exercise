CREATE TYPE submission_status AS ENUM (
    'pending',
    'invalid',
    'exact_duplicate',
    'near_duplicate',
    'matched',
    'review',
    'no_match',
    'unmatched'
);
