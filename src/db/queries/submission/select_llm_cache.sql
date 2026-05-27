-- Idempotency cache: same submission content + same model + same prompt
-- version => reuse the prior LLM output. Oldest answer wins so a non-
-- deterministic model can't re-roll a previously committed decision.
SELECT llm_output
FROM submission
WHERE llm_model = %s
  AND llm_prompt_version = %s
  AND fingerprint = %s
  AND llm_output IS NOT NULL
ORDER BY updated_at ASC
LIMIT 1;
