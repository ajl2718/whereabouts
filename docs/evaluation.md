## Evaluation harness

Both the Streamlit app and the CLI review UI are single-user, loopback-only development tools (not hosted services).

### Streamlit app

```bash
uv run --extra evaluation streamlit run whereabouts/evaluation/streamlit_app.py \
  --server.address 127.0.0.1 --browser.gatherUsageStats false
```

* **Match addresses:** Select a repo CSV or upload one with `input_address` and `best_match` columns. Pick an algorithm, local reference DB snapshot, threshold, top-k, batch size, and experiment name.
* **Results:** Green/red rows show label agreement (case/whitespace-normalized only)—not verified gold accuracy. Missing or below-threshold predictions count as incorrect.
* **Error tagging:** Click any incorrect row to add a free-text error type (empty text clears it). Tags are stored as run-specific, append-only records in `evaluation_runs/errors.sqlite3` and never modify the CSV or run evidence.
* **Saving & archiving:** Runs save automatically and can be reopened without re-executing, or exported as JSON/CSV. A downloaded JSON alone isn't executable—keep the local run directory, source snapshots, lockfiles, and reference DB snapshots for reproducibility.
* **Comparing runs:** Requires identical datasets and reference snapshots. Measured geocoding time excludes setup, warm-up, and scoring; wall time includes worktree prep, env startup, and first-run installs. Compare speed only on the same machine with matching settings.
* **Reference lookup:** Independently choose an installed reference DB or an absolute `.db` path.
  Filter by street-number token, `LOT` number, street-name phrase, and/or exact suburb.
  All nonempty filters are combined with AND; matching ignores case and whitespace.
  At least one filter is required. Results include reference IDs, labels, suburb and
  available location metadata, with a total count and pages of 100 (no truncated result set).
  Queries open the database read-only and do not execute a matching algorithm.
  Existing DBs do **not** store structured street/lot components: a street-number
  token can occur in a unit, lot, postcode, or range, and street-name phrases can
  also occur elsewhere in a label. Use the database's literal spellings/abbreviations;
  no parsing, range inference, or fuzzy/abbreviation expansion is performed.

---

### Algorithm versions

The default **Working copy** runs a snapshot of your current package source in a separate Python process using the app's environment (saved under `evaluation_runs/implementations/sources/`). This captures uncommitted SQL/similarity tweaks, but doesn't isolate external modules or create a separate venv.

**Registering a historical commit:**
1. Commit an implementation containing `whereabouts/evaluation/worker.py`, `pyproject.toml`, and `uv.lock`.
2. Add a name and its full 40-character local commit SHA in the sidebar (the app won't fetch or commit).
3. Select the registered version and run.

* **Execution:** Registered versions are saved in `evaluation_runs/versions.json` and run in detached Git worktrees (`evaluation_runs/implementations/worktrees/`) with isolated `.venv` environments via `uv run --locked`. Your working branch is never switched, and modified cached worktrees are rejected. Clean up old worktrees with `git worktree remove <exact-worktree-path>`.
* **Security:** Only register trusted local code—running a revision executes its Python and build scripts with your user permissions.
* **Protocol v1:** Accepts a JSON request (DB path, checksums, `RunConfig`) and returns a saved-run path. The controller validates checksums, config, and commit SHA before saving. Older commits must port this contract before registering. Supports `standard`, `skipphrase`, and `trigram` with threshold/top-k/batch-size settings; structural SQL/similarity changes are versioned by commit.
* **Database compatibility:** The worker checks for required tables, but DuckDB surfaces column/type mismatches. Keep a compatible DB snapshot per implementation—checksums are verified, and DBs aren't copied into worktrees. Accepts installed DBs or explicit `.db` paths.

---

### CLI & local review UI

Uses Python's standard library (no extra web dependencies). The existing `benchmark` command is unchanged.

```bash
# 1. Import legacy CSV labels (marked unverified)
uv run python -m whereabouts evaluate import-csv example_data/test_set_au.csv \
  --output evaluation_data/au_v1.json

# 2. Run evaluation (requires installed DB, e.g. au_all_sm)
uv run python -m whereabouts evaluate run evaluation_data/au_v1.json \
  --database au_all_sm --how standard --threshold 0.3 0.5 0.7 --top-k 5

# 3. Launch local review UI at [http://127.0.0.1:8765](http://127.0.0.1:8765) (Ctrl+C to stop)
uv run python -m whereabouts evaluate review --runs evaluation_runs --port 8765
```

* **Review UI:** Compare baseline vs. challenger runs, filter regressions or shared failures, inspect ranked candidates, and launch built-in variations on development datasets (custom Python pipelines are CLI-only). Binds to loopback, enforces Host/Origin checks, and requires a token for writes.
* **Run artifacts:** Saved as immutable JSON files in `evaluation_runs/` (never overwritten). Records SHA-256 hashes (dataset, DB, package source, generated query), Git revision/dirty state, config, Python/DuckDB versions, candidates, metrics, and timings. Changes to inputs or source mid-run abort the save. Remote DBs are unsupported.
* **Timing:** Records setup, one warm-up batch, and measured batches separately. Hashing and scoring are excluded; candidate materialization and input-table prep are included. This is a warm-run measurement—compare only on the same machine, DB, batch size, and top-k.

---

### Dataset format

```json
{
  "schema_version": 1,
  "name": "au",
  "version": "2",
  "split": "development",
  "cases": [{
    "case_id": "stable-case-001",
    "input_address": "115 Sydney Rd Brunswick",
    "precision": "building",
    "label_status": "verified",
    "acceptable": [{"address": "115 SYDNEY RD BRUNSWICK VIC 3056"}],
    "expect_abstention": false,
    "tags": ["missing_postcode"],
    "evidence": "Independent reference identifying the intended premises.",
    "notes": "",
    "error_mode": ""
  }]
}
```

* **IDs & splits:** `case_id` must be unique and stable across versions (CSV import derives IDs from normalized inputs). Splits are `development` or `held_out`; keep typo variants and repeated premises in the same split to prevent leakage.
* **Label statuses:** `verified`, `needs_review`, or `ambiguous`. Only `verified` cases count toward accuracy and require human-supplied `evidence` plus `acceptable` answers (or `expect_abstention: true` with an empty list). Unverified cases still run and appear in label agreement.
* **Precision matching:**
  * `exact`, `unit`, `building`, `street`: List acceptable full DB labels or snapshot-specific `reference_id`s (IDs take precedence). Matches normalize only case and whitespace. For street-only inputs, list acceptable street-level candidates or mark as `ambiguous`.
  * `locality`: Use `{"locality": "BRUNSWICK", "postcode": "3056"}` (`postcode` is optional).
  * Component inference and distance-based scoring are not supported yet.

---

### Metrics & diagnoses

* **Accuracy:** Correct decisions / verified cases (includes expected abstentions).
* **Coverage:** Returned decisions / verified cases.
* **Accepted accuracy:** Correct returned decisions / returned decisions.
* **Top-k recall:** Verified positive cases with an acceptable retained candidate / verified positive cases (ignores threshold).
* **Label agreement:** Agreement across all supplied labels, including unverified ones.
* **Breakdowns:** Grouped by requested precision and dataset tag.

The evaluator applies the threshold to the rank-1 candidate while retaining lower-ranked candidates as evidence. Matcher and evaluator share `standard`, `skipphrase`, and `trigram` pipeline factories (`standard` still ignores `top_n` and `threshold` in the public matcher; `skipphrase` uses its own pipeline).

**Failure diagnoses:**
* `ranking`: Acceptable candidate retained below rank 1.
* `threshold_rejection`: Rank-1 acceptable candidate fell below threshold.
* `false_positive`: Returned an answer when abstention was expected.
* `not_in_top_k`: Missing from retained candidates (may be pruned, ranked lower, or absent from the DB—not necessarily a retrieval bug). Use `error_mode` and `tags` for finer human diagnoses.

---

### Compare & review workflow

```bash
# Compare two runs (add --fail-on-regression for CI exit codes)
uv run python -m whereabouts evaluate compare evaluation_runs/BASELINE_ID.json \
  evaluation_runs/CHALLENGER_ID.json --output evaluation_runs/comparison.json

# Export reviewed proposals into a new dataset version
uv run python -m whereabouts evaluate export-reviewed evaluation_data/au_v1.json \
  --reviews evaluation_runs/reviews.sqlite3 --version 2 --output evaluation_data/au_v2.json
```

* Comparisons require identical dataset/DB checksums, case IDs, and evidence, and break down regressions, improvements, shared outcomes, and unscored cases.
* Review proposals are append-only in SQLite and never alter recorded metrics. After exporting a new dataset version, rerun **both** configurations against it—never compare across changed labels.
* Keep `held_out` separate from tuning. The UI blocks new runs on held-out datasets; use the CLI for final checks.

---

### Custom pipelines

```bash
uv run python -m whereabouts evaluate run evaluation_data/au_v2.json \
  --database au_all_sm --pipeline whereabouts.matching_queries.standard_with_neighbours:create_matching_query
```

* **Contract:** Provide a trusted `module:function` that takes a DuckDB connection and returns a `QueryPipeline`. It must expose a `matched_addresses_ranked_by_similarity` step with columns: `address_id1`, `address_id2`, `address_matched`, `suburb`, `postcode`, `latitude`, `longitude`, `similarity`, and `rank`. The evaluator runs up to that step and exports top-k.
* **Indexes:** Built-in `standard`, `skipphrase`, and `trigram` algorithms require their corresponding indexes in the reference DB.
* **Tracking:** The factory's source file, SQL/query identity, and lockfile are checksummed (and checked for mid-run edits), though arbitrary imported dependencies aren't fingerprinted—retain external sources alongside your config.