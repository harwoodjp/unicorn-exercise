CREATE TYPE submission_decision AS ENUM (
    'exact_match',
    'possible_match',
    'human_review',
    'no_match'
);
