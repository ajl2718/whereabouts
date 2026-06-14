from duckdb import DuckDBPyConnection

from ..QueryStep import query_step
from ..QueryPipeline import QueryPipeline
from ..constants import MAX_PHRASE_FREQUENCY


def create_matching_query(con: DuckDBPyConnection) -> QueryPipeline:
    """
    Clean the pipeline for the standard query matching process. This pipeline consists of the following steps:
    1. Clean the input addresses by removing special characters and converting to uppercase.
    2. Extract numeric tokens from the cleaned addresses.
    3. Extract alphabetic tokens from the cleaned addresses.
    4. Create bigrams from the cleaned addresses for matching.
    5. Join the input phrases with an inverted index in the geocode database to find potential matches, filtering to those with frequency less than a specified threshold to avoid very common phrases.
    6. Unnest the matched address IDs for further processing.
    7. Extract detailed information for the matched address candidates.
    8. Filter the matched address candidates to the top 50 based on similarity.
    9. Match addresses with neighbouring suburbs for further processing.
    10. Compute similarity between addresses and their neighbouring suburb matches.
    11. Rank addresses by their similarity to neighbouring suburb matches.
    12. Select the top-ranked match per input address.
    13. Left-join matches back to input addresses so unmatched rows are preserved.
    """
    clean_addresses = query_step(
        query_template="""
        SELECT address_id,
        trim(regexp_replace(regexp_replace(unaccent(upper(address)), '[^A-Z0-9]+', ' ', 'g'), '[ ]+', ' ')) AS address
        FROM {addresses}""",
        output_table_name="clean_addresses",
        input_table_names={"addresses": "input_addresses"},
        step_name="Clean addresses",
        step_description="Cleans the input addresses by removing special characters and converting to uppercase.",
    )

    create_address_numerics = query_step(
        query_template="""
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
        FROM {input_table}""",
        output_table_name="input_addresses_with_numerics",
        input_table_names={"input_table": "clean_addresses"},
        step_name="Append column with numeric tokens",
        step_description="Extracts numeric tokens from the input addresses.",
    )

    create_address_alpha_tokens = query_step(
        query_template="""
        SELECT
        address_id,
        address,
        numeric_tokens,
        NULLIF(
            regexp_extract_all(
                address,
                '[A-Z]+'
            ),
            []::VARCHAR[]        ) AS alpha_tokens
        FROM {input_table}""",
        output_table_name="input_addresses_with_alpha_tokens",
        input_table_names={"input_table": "input_addresses_with_numerics"},
        step_name="Append column with alpha tokens",
        step_description="Extracts alphabetic tokens from the input addresses.",
    )

    create_input_phrases = query_step(
        query_template="""
        SELECT 
        address_id, arr[i] || ' ' || arr[i + 1] AS tokenphrase
        FROM 
        (
            SELECT 
            address_id, string_to_array(address, ' ') AS arr 
            FROM {input_table}
        ),
        unnest(generate_series(1, array_length(arr, 1) - 1)) AS gs(i)
        UNION ALL
        SELECT address_id, arr[i] || ' ' || arr[i + 2] AS tokenphrase
        FROM (
            SELECT address_id, string_to_array(address, ' ') AS arr 
            FROM {input_table}
        ),
        unnest(generate_series(1, len(arr) - 2)) AS gs(i)
        WHERE TRY_CAST(arr[i] AS INTEGER) IS NOT NULL""",
        output_table_name="input_phrases",
        input_table_names={"input_table": "input_addresses_with_alpha_tokens"},
        step_name="Create bigrams",
        step_description="Creates bigrams from the input addresses for matching.",
    )

    first_matching_step = query_step(
        query_template=f"""
        SELECT 
        l.address_id AS address_id1, 
        r.addr_ids AS address_ids2
        FROM {{input_table1}} AS l
        LEFT JOIN {{input_table2}} AS r
        ON l.tokenphrase = r.tokenphrase AND r.frequency < {MAX_PHRASE_FREQUENCY}""",
        output_table_name="matched_address_ids",
        input_table_names={"input_table1": "input_phrases", "input_table2": "remote.phraseinverted"},
        step_name="First matching step",
        step_description=f"Joins the input phrases with inverted index in geocode database to find potential matches. Filter to those with frequency less than {MAX_PHRASE_FREQUENCY} to avoid very common phrases.",
    )

    unnest_match_candidates = query_step(
        query_template="""
        SELECT DISTINCT 
        address_id1, 
        unnest(address_ids2) AS address_id2
        FROM {input_table}
        WHERE address_ids2 IS NOT NULL""",
        output_table_name="unnested_matches",
        input_table_names={"input_table": "matched_address_ids"},
        step_name="Unnest match candidates",
        step_description="Unnests the matched address IDs for further processing.",
    )

    extract_match_candidate_details = query_step(
        query_template="""
        SELECT
        t1.address_id1,
        t1.address_id2,
        t2.address,
        t2.numeric_tokens AS input_numerics,
        t3.numeric_tokens AS match_numerics,
        t2.alpha_tokens AS input_alpha_tokens,
        NULLIF(regexp_extract_all(t3.addr, '[A-Z]+'), []::VARCHAR[]) AS match_alpha_tokens,
        t3.addr AS address_matched,
        t3.suburb,
        t3.state,
        t3.POSTCODE AS postcode,
        t3.LATITUDE AS latitude,
        t3.LONGITUDE AS longitude
        FROM {input_table1} t1
        INNER JOIN {input_table2} t2 ON t1.address_id1 = t2.address_id
        INNER JOIN {input_table3} t3 ON t1.address_id2 = t3.addr_id
        WHERE list_overlap(t2.numeric_tokens, t3.numeric_tokens, 0.2)""",
        output_table_name="unnested_addresses_with_details",
        input_table_names={"input_table1": "unnested_matches", "input_table2": "input_addresses_with_alpha_tokens", "input_table3": "remote.addrtext_with_detail"},
        step_name="Extract match candidate details",
        step_description="Extracts detailed information for the matched address candidates.",
    )

    filter_to_top50_candidates = query_step(
        query_template="""
        SELECT *
        FROM (
            SELECT 
            *,
            row_number() OVER (
                PARTITION BY address_id1
                ORDER BY IOU_min(input_alpha_tokens, match_alpha_tokens) * IOU(input_numerics, match_numerics) DESC, address_id2
            ) AS pre_rank
            FROM {input_table}
        )
        WHERE pre_rank <= 50""",
        output_table_name="top_50_candidates",
        input_table_names={"input_table": "unnested_addresses_with_details"},
        step_name="Filter to top 50 candidates",
        step_description="Filters the matched address candidates to the top 50 based on similarity.",
    )

    compute_similarity = query_step(
        query_template="""
        SELECT
        address_id1,
        address,
        suburb,
        input_numerics,
        input_alpha_tokens,
        address_id2,
        address_matched,
        match_numerics,
        match_alpha_tokens,
        postcode,
        latitude,
        longitude,
        case when address is not null then
        IOU_min(input_alpha_tokens, match_alpha_tokens) * IOU(input_numerics, match_numerics)
        else 0.0 end as similarity
        FROM {input_table}""",
        output_table_name="matched_addresses_with_similarities",
        input_table_names={"input_table": "top_50_candidates"},
        step_name="Compute Similarity",
        step_description="Computes the similarity between input addresses and matched addresses.",
    )

    rank_by_similarity = query_step(
        query_template="""
        SELECT *,
        row_number() OVER (
            PARTITION BY address_id1
            ORDER BY similarity DESC, address_id2
        ) AS rank
        FROM {input_table}""",
        output_table_name="matched_addresses_ranked_by_similarity",
        input_table_names={"input_table": "matched_addresses_with_similarities"},
        step_name="Rank by similarity",
        step_description="Ranks addresses by their similarity to neighbouring suburb matches.",
    )

    select_current = query_step(
        query_template="""
        SELECT
        address_id1 AS address_id,
        address AS input_address,
        address_matched,
        suburb,
        postcode,
        latitude,
        longitude,
        similarity,
        match_numerics, 
        match_alpha_tokens,
        input_numerics,
        input_alpha_tokens,
        FROM {input_table}
        WHERE RANK == 1
        ORDER BY address_id1""",
        output_table_name="final_matched_addresses",
        input_table_names={"input_table": "matched_addresses_ranked_by_similarity"},
        step_name="Select final matched addresses",
        step_description="Selects the top-ranked match per input address.",
    )

    rejoin_all_inputs = query_step(
        query_template="""
        SELECT
        t1.address_id,
        t1.address AS input_address,
        t2.address_matched,
        t2.suburb,
        t2.postcode,
        t2.latitude,
        t2.longitude,
        t2.similarity,
        t2.match_numerics, 
        t2.match_alpha_tokens,
        t2.input_numerics,
        t2.input_alpha_tokens,
        FROM {input_table1} t1
        LEFT JOIN {input_table2} t2
        ON t1.address_id = t2.address_id
        ORDER BY t1.address_id""",
        output_table_name="all_addresses_with_matches",
        input_table_names={"input_table1": "input_addresses_with_numerics", "input_table2": "final_matched_addresses"},
        step_name="Rejoin all inputs",
        step_description="Left-joins matches back to input addresses so unmatched rows are preserved.",
    )

    pipeline = QueryPipeline(
        con=con, 
        steps=[
            clean_addresses, 
            create_address_numerics, 
            create_address_alpha_tokens,
            create_input_phrases, 
            first_matching_step, 
            unnest_match_candidates,
            extract_match_candidate_details,
            filter_to_top50_candidates,
            compute_similarity,
            rank_by_similarity,
            select_current,
            rejoin_all_inputs]
        )

    return pipeline
