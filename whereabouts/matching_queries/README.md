# Matching Queries

This package contains the different matching query implementations used by the whereabouts geocoder. Each query type uses a different strategy for matching input addresses against the geocoder database.

## Query types

### Standard

**Module:** `standard.py`

The default, general-purpose matching algorithm. Uses token-pair (bigram) phrases from the input address to look up candidates via an inverted index.

**Pipeline steps:**

1. Clean input addresses (remove special characters, convert to uppercase).
2. Extract numeric and alphabetic tokens.
3. Create bigrams (adjacent word pairs) from the address.
4. Look up bigrams in the `phraseinverted` table, filtering out very common phrases.
5. Join matched candidates with address details and filter by numeric overlap.
6. Rank the top 50 candidates using `IOU_min` (alphabetic token similarity) x `IOU` (numeric token similarity).
7. Select the best match per input address.

**When to use:** Default choice for most geocoding tasks. Good balance of speed and accuracy.

### Standard with neighbours

**Module:** `standard_with_neighbours.py`

Extends the standard pipeline with a geographic neighbour correction step. After finding the top 50 candidates, it joins against a `suburb_neighbours` table and considers whether the matched address might belong to a neighbouring suburb.

**Additional steps (compared to standard):**

- Joins candidates against `suburb_neighbours` to find neighbouring suburb variants.
- Replaces the matched suburb/state/postcode with neighbouring suburb alternatives.
- Computes similarity against both the original and neighbour-corrected address.
- Returns a `neighbouring_suburb_correction` field indicating whether a correction was applied.

**When to use:** When addresses may reference nearby suburbs or when addresses near suburb boundaries need more accurate matching.

### Skipphrase

**SQL file:** `queries/geocoder_query_skipphrase2.sql`

Uses skip-phrases (pairs of tokens with a gap of one word between them) rather than adjacent bigrams. This provides broader matching by capturing relationships between non-adjacent tokens.

**Key characteristics:**

- Creates skip-phrases: `token[i] + ' ' + token[i+2]` (skips the middle token).
- Looks up against the `skipphraseinverted` table.
- Uses `jaro_similarity` x `numeric_overlap` for scoring.

**When to use:** Better recall when word order varies or for addresses with extra/missing words between key tokens.

### Trigram

**SQL file:** `queries/geocoder_query_trigramb3.sql`

Uses character-level trigrams (3-character substrings) rather than word-level tokens. This makes it robust to typographical errors and character-level variations.

**Key characteristics:**

- Extracts 3-character substrings from each token (e.g. "SMITH" produces "SMI", "MIT", "ITH").
- Hashes trigram pairs for efficient lookup against the `trigramphraseinverted3` table.
- Uses `ngram_jaccard` x `numeric_overlap` for scoring.

**When to use:** When input addresses contain spelling errors or character-level typos. Requires a large database (built with the `trigram` matcher option).

## Comparison

| Feature | Standard | Std + Neighbours | Skipphrase | Trigram |
|---------|----------|------------------|------------|---------|
| Index type | Word bigrams | Word bigrams | Skip-phrases | Character trigrams |
| Similarity metric | IOU_min x IOU | IOU_min x IOU | Jaro x numeric | N-gram Jaccard x numeric |
| Geographic context | No | Yes | No | No |
| Typo tolerance | Low | Low | Medium | High |
| Database requirement | Standard | Standard + neighbours table | Skipphrase index | Trigram index (large DB) |

## Adding a new query type

1. Create a new module in this package (e.g. `my_query.py`).
2. Use `from ..QueryStep import query_step` and `from ..QueryPipeline import QueryPipeline` to access the pipeline infrastructure.
3. Define your pipeline function and export it from `__init__.py`.
