WITH input_addresses_cleaned AS ( ---- remove accents, punctuation, multiple spaces, and convert to uppercase
    SELECT
        address_id,
        trim(regexp_replace(regexp_replace(unaccent(upper(address)), '[^A-Z0-9]+', ' ', 'g'), '[ ]+', ' ')) AS address
    FROM input_addresses
),
input_addresses_with_numerics AS ( -- extract the numeric tokens
    SELECT
        address_id,
        address,
        NULLIF(
            regexp_extract_all(
                address,
                '[0-9]+[A-Z]?'
            ),
            []::VARCHAR[]
        ) AS numeric_tokens
    FROM input_addresses_cleaned
),
input_phrases AS ( -- create phrases
    SELECT 
        address_id, arr[i] || ' ' || arr[i + 1] AS tokenphrase
    FROM (
        SELECT address_id, string_to_array(address, ' ') AS arr FROM input_addresses_with_numerics
        ),
    unnest(generate_series(1, len(arr) - 1)) AS gs(i)
    UNION ALL
    SELECT address_id, arr[i] || ' ' || arr[i + 2] AS tokenphrase
    FROM (SELECT address_id, string_to_array(address, ' ') AS arr FROM input_addresses_with_numerics),
    unnest(generate_series(1, len(arr) - 2)) AS gs(i)
    WHERE TRY_CAST(arr[i] AS INTEGER) IS NOT NULL
),
input_phrase_matched_lists AS (
    SELECT l.address_id AS address_id1, r.addr_ids AS address_ids2
    FROM input_phrases AS l
    LEFT JOIN remote.phraseinverted AS r
    ON l.tokenphrase = r.tokenphrase AND r.frequency < 1000
),
input_proposed_match AS (
    SELECT DISTINCT address_id1, unnest(address_ids2) AS address_id2
    FROM input_phrase_matched_lists
    WHERE address_ids2 IS NOT NULL
),
input_proposed_match2 AS (
    SELECT
        t1.address_id1,
        t1.address_id2,
        t2.address,
        t2.numeric_tokens AS input_numerics,
        t3.numeric_tokens AS match_numerics,
        t3.addr AS address_matched,
        t3.suburb,
        t3.state,
        t3.POSTCODE AS postcode,
        t3.LATITUDE AS latitude,
        t3.LONGITUDE AS longitude
    FROM input_proposed_match t1
    INNER JOIN input_addresses_with_numerics t2 ON t1.address_id1 = t2.address_id
    INNER JOIN remote.addrtext_with_detail t3 ON t1.address_id2 = t3.addr_id
    WHERE list_overlap(t2.numeric_tokens, t3.numeric_tokens, 0.5)
),
input_proposed_match2_top AS (
    SELECT *
    FROM (
        SELECT 
        *,
        row_number() OVER (
            PARTITION BY address_id1
            ORDER BY jaro_winkler_similarity(address, address_matched) DESC, address_id2
        ) AS pre_rank
        FROM input_proposed_match2
    )
    WHERE pre_rank <= 50
),
input_proposed_match_ns AS (
    SELECT
        a.address_id1,
        a.address,
        a.suburb,
        a.input_numerics,
        s.neighbour_suburb_state_postcode AS neighbouring_suburb_state_postcode,
        a.address_id2,
        a.address_matched,
        a.postcode,
        a.match_numerics,
        a.latitude,
        a.longitude,
        REGEXP_REPLACE(
            a.address_matched,
            '\\b' || a.suburb || '\\b' || a.state || '\\b' || a.postcode,
            s.neighbour_suburb_state_postcode
        ) AS address_matched_ns
    FROM input_proposed_match2_top a
    JOIN remote.suburb_neighbours s ON (a.suburb = s.suburb_name AND a.state = s.state_name AND a.postcode = s.postcode)
),
best_matches AS (
    SELECT
        address_id1,
        address,
        suburb,
        input_numerics,
        neighbouring_suburb_state_postcode,
        address_id2,
        address_matched,
        match_numerics,
        postcode,
        latitude,
        longitude,
        address_matched_ns,
        case when address is not null then
        ngram_jaccard(address, address_matched_ns) * multiset_jaccard(input_numerics, match_numerics)
        else 0.0 end as similarity
    FROM input_proposed_match_ns
),
best_matches_ranked AS (
    SELECT *,
        row_number() OVER (
            PARTITION BY address_id1
            ORDER BY similarity DESC, address_id2
        ) AS rank
    FROM best_matches
)
SELECT
    address_id1 AS address_id,
    address,
    address_id2,
    address_matched,
    suburb,
    postcode,
    latitude,
    longitude,
    similarity
FROM best_matches_ranked
WHERE (rank<=?) OR (rank IS NULL) -- select top matches
ORDER BY address_id, rank