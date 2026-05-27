### Diagrams

* [Pipeline](docs/diagrams/Pipeline.png)
* [Submission lifecycle](docs/diagrams/Lifecycle.png)
* [Data flow](docs/diagrams/Data%20flow.png)


### Summary
* Implementation
  * Organized functionality into `repository`, `service`, `model` layers
    * Repository implements data access with Postgres schema and parameterized SQL
    * Service orchestrates models and repositories and implements matching logic
    * Model implements data shapes and validation via Pydantic `BaseModel`
  * `ingest.py` is an entrypoint and composition root, passing dependencies (Postgres connection, Gemini client) downward
  * Infrastructure choices: Postgres (`db`) and Gemini (`gemini`):
    * Postgres provides ACID guarantees and transactional integrity
    * Gemini is affordable (flash models) and sufficient for string/name matching
      * 1 record = appx. 1500 tokens
      * Gemini 2.5 Flash = $0.30/1M (input), $2.50/1M (output)
        * 1 record = (1500 × $2.50/1M) = ~$0.00375
          * Using output price for conservative estimate
          * Not considering provider caching (usually a token threshold per prompt)
          * Turning "thinking mode" off would also reduce cost
        * 200 records = (200 x ~$0.00375) = ~$0.75/1k
        * 1m records = ~$750


* Skipped/out-of-scope
  * Full repository abstraction
    * `psycopg` internals leak into service layer, ideally repositories abstract the driver
  * Queues, workers, workflow harness
    * Alternative entrypoints (e.g. API, workflow) can re-use submission/matching logic due to layering discipline
  * Concurrency and retry policies
    * At scale, necessary for throughput and resilience
  * Observability/instrumentation
    * Spans, traces, and logs enable debugging and monitoring
    * Instrumenting LLMs, e.g. around tool usage, especially important
  * `pg_trgm` (w/ GIN index) and `RapidFuzz`
    * Useful database and application techniques for fuzzy name matching
    * Could improve match rate for deterministic pass



* Prompting
  * Authoring
    * Should be highly specific about requirements
      * Initially, `store errors in submission table`
      * Observed Pydantic/python syntax in database table
      * Adjusted to: `collect field-level validation errors from Submission creation and store field:reason pairs in validation_error column`
  * Application
    * Initially, repeated deterministic guidance in prompt
    * Removed redundant context and achieved same eval results

### Tier 1

* Implemented ingestion pipeline `pipeline/ingest.py` which: 
  * Imports product records to `product` table
  * Imports submission records, scoped by `import_id`, to `submission` table
    * Pydantic models for field validations
    * `ijson` library for JSON streaming (memory-efficient)
    * `import_id` allows arbitrary selection and ad-hoc re-processing
  * Classifies `status` and `decision` for `pending` submission records as:
    * `invalid` (status=`invalid`, decision=`null`) when submission has invalid data
    * `exact_match` (status=`matched`, decision=`exact_match`) when submission has 1 product with same producer/category/size/normalized name
      * Producer aliases are handled with hardcoded dictionary
      * Name is normalized and matched as token-subset: submission's tokens must be a subset of product's tokens
        * Underspecified names could falsely match over a larger dataset
        * Token equality would allow stricter matching, with LLM resolving at most a `possible_match`
    * `no_match` (status=`no_match`, decision=`no_match`) when submission has unrecognized category or size mismatch
    * `review` (status=`review`, decision=`human_review`) when submission has multiple candidates or required and missing vintage
    * `unmatched` (status=`unmatched`, decision=`null`) when submission has no candidates
  * Builds a report of deterministic matching results
  * Detects `exact_duplicate` submissions (status=`exact_duplicate`, decision=`null`) by "fingerprint" matching
    * Submission fingerprint is a hash of submission's name/producer/category/vintage/size
  * Detects `near_duplicate` submissions (status=`near_duplicate`, decision=`null`) by querying product matches after deterministic pass
    * Near-duplicate submissions have distinct fingerprints but match to the same product
    * Submissions which duplicate product matches are set to `near_duplicate` except first submitted, termed "survivor"
  * Builds a report of deduplication efforts

### Tier 2

* Extends ingestion pipeline with:
  * LLM-assisted matching (`service/match/llm.py`)
    * Defaults to `gemini-2.5-flash`
      * Fast, affordable, robust enough to handle scenario
    * Returns structured `LLMDecision` output, containing `confidence`, a `decision`, and matched products 
      * Defaults to a confidence threshold of `0.85` for matching decisions
      * `possible_match` (status=`matched`, decision=`possible_match`) when LLM returns a candidate with high confidence
      * `human_review` (status=`review`, decision=`human_review`) when LLM explicitly returns `human_review` or low confidence
      * `no_match` (status=`no_match`, decision=`no_match`) when LLM is unable to match a product
  * `submission` table expanded for LLM auditing:
    * `llm_model`
    * `llm_prompt_version`
    * `llm_output`
    * `llm_confidence`
    * `llm_reason`
  * LLM response cache keyed on `(model_id, prompt_version, fingerprint)`
    * `select_llm_cache.sql`
    * Increment `prompt_version` to invalidate cache
    * Cached responses allow cheap(er) re-processing 
* Import is resilient to LLM availability
  * If LLM-related exception, submissions are routed for review (status=`review`, decision=`human_review`)
* `submission` table acts as review queue, queryable with status = `review`

### Tier 3

* $50, 1M submissions
  * Refine ingestion to ensure high quality inputs/labelling 
  * Fortify deterministic matching, reducing LLM volume
      * Fuzzy matching or FTS for more accurate matching strategy 
      * Monitor determinstic/LLM ratio over time
  * Move to cheapest models that can consistently pass eval
  * Utilize provider's context caching (see: implicit caching, explicit caching for Gemini)
  * Index products in vector database and swap context stuffing for RAG
  * Track spend/token allowance, route to review when exceeded
* Eval and regressions
  * Results (`scripts/eval.sh`)
    * `product_id correct:     32/32 = 100.0%`
    * `decision in acceptable: 32/32 = 100.0%`
    * `false positives:        0`
  * Regressions
    * Eval cases establish baseline behavior and define regression boundaries 
    * Run at intervals, on prompt changes, when using new models
    * Detect behavioral changes with snapshot/diffing over time
* Drift
  * Measure frequency of human correction/intervention
  * Measure output e.g. decision distribution and confidence scores
  * Instrument and alert on threshold breaches
  * Preventive: use snapshots e.g. `gpt-4o-2024-08-06` over aliases e.g. `gpt-4o`
* Reversibility
  * `import_id` scoping allows `submission` deletion or invalidation:
    * `DELETE FROM submission WHERE import_id = ?;`
    * `UPDATE submission SET status='reverted' WHERE import_id = ?;`
  * If `submission` records promote to the `product` catalog, store with `import_id` 