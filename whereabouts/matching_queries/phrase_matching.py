from __future__ import annotations

from ..QueryStep import QueryStep, query_step


def input_steps(alphabet: str, numeric_pattern: str) -> list[QueryStep]:
    return [
        query_step(
            query_template="""
                SELECT address_id,
                    trim(regexp_replace(regexp_replace(upper(address),
                        '[^{alphabet}0-9]+', ' ', 'g'), '[ ]+', ' ')) AS address
                FROM {source}
            """,
            output_table_name="input_addresses_cleaned",
            input_table_names={"source": "input_addresses", "alphabet": alphabet},
            step_name="Clean addresses",
        ),
        query_step(
            query_template="""
                SELECT address_id, address,
                       unnest(string_to_array(address, ' ')) AS token
                FROM {source}
            """,
            output_table_name="address_tokens",
            input_table_names={"source": "input_addresses_cleaned"},
            step_name="Tokenize addresses",
        ),
        query_step(
            query_template="""
                SELECT address_id, address, array_agg(token) AS numeric_tokens
                FROM {source} WHERE regexp_matches(token, '{pattern}')
                GROUP BY address_id, address
            """,
            output_table_name="addresses_grouped",
            input_table_names={"source": "address_tokens", "pattern": numeric_pattern},
            step_name="Extract numeric tokens",
        ),
        query_step(
            query_template="""
                SELECT t2.address_id, t2.address, t1.numeric_tokens
                FROM {cleaned} t2
                LEFT JOIN {grouped} t1 ON t2.address_id = t1.address_id
            """,
            output_table_name="input_addresses_with_numerics",
            input_table_names={
                "cleaned": "input_addresses_cleaned",
                "grouped": "addresses_grouped",
            },
            step_name="Restore inputs without numeric tokens",
        ),
    ]


def token_steps(alphabet: str) -> list[QueryStep]:
    return [
        query_step(
            query_template="""
                SELECT address_id,
                    unnest(string_to_array(regexp_replace(trim(address),
                        '[^{alphabet}0-9]+', ' ', 'g'), ' ')) AS token
                FROM {source}
            """,
            output_table_name="tokens_pre1",
            input_table_names={
                "source": "input_addresses_with_numerics",
                "alphabet": alphabet,
            },
            step_name="Extract phrase tokens",
        ),
        query_step(
            query_template="SELECT address_id, row_number() OVER () AS row_num, token FROM {source}",
            output_table_name="tokens_pre2",
            input_table_names={"source": "tokens_pre1"},
            step_name="Number phrase tokens",
        ),
        query_step(
            query_template="""
                SELECT address_id,
                       row_number() OVER (PARTITION BY address_id ORDER BY row_num) AS row_num,
                       token
                FROM {source}
            """,
            output_table_name="tokens",
            input_table_names={"source": "tokens_pre2"},
            step_name="Order tokens within each input",
        ),
    ]


def candidate_steps(
    feature_table: str,
    phrase_column: str,
    index_table: str,
    max_frequency: int,
    scorer: str,
) -> list[QueryStep]:
    return [
        query_step(
            query_template=f"""
                SELECT l.{phrase_column}, l.address_id AS address_id1, r.addr_ids AS address_ids2
                FROM {{features}} l
                LEFT JOIN {{index}} r ON l.{phrase_column} = r.{phrase_column}
                    AND r.frequency < {max_frequency}
            """,
            output_table_name="input_phrase_matched_lists",
            input_table_names={"features": feature_table, "index": index_table},
            step_name="Retrieve candidate lists",
        ),
        query_step(
            query_template=f"""
                SELECT address_id1, {phrase_column},
                       CASE WHEN address_ids2 IS NULL THEN unnest([-1])
                            ELSE unnest(address_ids2) END AS address_id2
                FROM {{source}}
            """,
            output_table_name="input_phrase_matched_pre",
            input_table_names={"source": "input_phrase_matched_lists"},
            step_name="Expand candidate lists",
        ),
        query_step(
            query_template=f"""
                SELECT address_id1, {phrase_column}, array_agg(address_id2) AS address_ids2
                FROM {{source}} GROUP BY address_id1, {phrase_column}
            """,
            output_table_name="input_phrase_matched",
            input_table_names={"source": "input_phrase_matched_pre"},
            step_name="Collect candidates per phrase",
        ),
        query_step(
            query_template="SELECT DISTINCT address_id1, unnest(address_ids2) AS address_id2 FROM {source}",
            output_table_name="input_proposed_match",
            input_table_names={"source": "input_phrase_matched"},
            step_name="Deduplicate candidates",
        ),
        query_step(
            query_template=f"""
                SELECT t1.address_id1, t1.address_id2, t2.address,
                       t2.numeric_tokens AS input_numerics, t3.numeric_tokens AS match_numerics,
                       t3.addr AS address_matched,
                       CASE WHEN t3.addr IS NOT NULL THEN
                           {scorer}(t2.address, t3.addr) * numeric_overlap(t2.numeric_tokens, t3.numeric_tokens)
                       ELSE 0.0 END AS similarity
                FROM {{candidates}} t1
                LEFT JOIN {{inputs}} t2 ON t1.address_id1 = t2.address_id
                LEFT JOIN {{reference}} t3 ON t1.address_id2 = t3.addr_id
            """,
            output_table_name="match",
            input_table_names={
                "candidates": "input_proposed_match",
                "inputs": "input_addresses_with_numerics",
                "reference": "remote.addrtext_with_detail",
            },
            step_name="Score candidates",
        ),
        query_step(
            query_template="""
                SELECT t1.address_id1, t1.address_id2, t1.address, t1.address_matched,
                       t1.input_numerics, t1.match_numerics, t2.suburb AS suburb, t2.postcode AS postcode,
                       t2.latitude AS latitude, t2.longitude AS longitude, t1.similarity
                FROM {matches} t1
                LEFT JOIN {reference} t2 ON t1.address_id2 = t2.addr_id
            """,
            output_table_name="match_ranked_pre",
            input_table_names={
                "matches": "match",
                "reference": "remote.addrtext_with_detail",
            },
            step_name="Attach candidate metadata",
        ),
        query_step(
            query_template="SELECT * FROM {source} WHERE list_overlap(input_numerics, match_numerics, 0.5)",
            output_table_name="match_ranked",
            input_table_names={"source": "match_ranked_pre"},
            step_name="Filter by numeric overlap",
        ),
        query_step(
            query_template="""
                SELECT row_number() OVER (PARTITION BY address_id1 ORDER BY similarity DESC) AS rank, *
                FROM {source} ORDER BY address_id1
            """,
            output_table_name="matched_addresses_ranked_by_similarity",
            input_table_names={"source": "match_ranked"},
            step_name="Rank candidates",
        ),
    ]


def result_step(top_n: int) -> QueryStep:
    if type(top_n) is not int or top_n < 1:
        raise ValueError("top_n must be a positive integer")
    return query_step(
        query_template=f"""
            SELECT t1.address_id, t1.address,
                   t2.address_id2, t2.address_matched, t2.suburb, t2.postcode,
                   t2.latitude, t2.longitude, t2.similarity
            FROM {{inputs}} t1
            LEFT JOIN {{ranked}} t2 ON t1.address_id = t2.address_id1
            WHERE t2.rank <= {top_n} OR t2.rank IS NULL
            ORDER BY t1.address_id
        """,
        output_table_name="all_addresses_with_matches",
        input_table_names={
            "inputs": "input_addresses_with_numerics",
            "ranked": "matched_addresses_ranked_by_similarity",
        },
        step_name="Select matches and preserve unmatched inputs",
    )
