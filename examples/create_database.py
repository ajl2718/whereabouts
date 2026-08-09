# Example of how to create an address matching database suitable for geocoding
# load the test data
from tests.test_pipeline_components import pipeline_connection, con


from whereabouts.QueryPipeline import QueryPipeline
from whereabouts.matching_queries.standard_with_neighbours import (
    clean_addresses,
    create_address_numerics,
    create_address_alpha_tokens,
    create_input_phrases,
    first_matching_step,
    unnest_match_candidates,
    extract_match_candidate_details,
    filter_to_top50_candidates,
    neighbouring_suburb_match,
    compute_similarity,
    rank_by_similarity,
    select_current,
    rejoin_all_inputs,
)

# module fixture setup
pc_gen = pipeline_connection.__wrapped__()  # not .wrapped()
db = next(pc_gen)  # value from yield

# function fixture setup (depends on pipeline_connection)
con_gen = con.__wrapped__(db)
test_con = next(con_gen)

pipeline = QueryPipeline(con=test_con, steps=[clean_addresses])
pipeline.execute()

pipeline = QueryPipeline(con=test_con, steps=[clean_addresses, create_address_numerics])
pipeline.execute()

pipeline = QueryPipeline(
    con=test_con,
    steps=[clean_addresses, create_address_numerics, create_address_alpha_tokens],
)
pipeline.execute()

pipeline = QueryPipeline(
    con=test_con,
    steps=[
        clean_addresses,
        create_address_numerics,
        create_address_alpha_tokens,
        create_input_phrases,
    ],
)

pipeline = QueryPipeline(
    con=test_con,
    steps=[
        clean_addresses,
        create_address_numerics,
        create_address_alpha_tokens,
        create_input_phrases,
        first_matching_step,
    ],
)

pipeline = QueryPipeline(
    con=test_con,
    steps=[
        clean_addresses,
        create_address_numerics,
        create_address_alpha_tokens,
        create_input_phrases,
        first_matching_step,
        unnest_match_candidates,
    ],
)

pipeline = QueryPipeline(
    con=test_con,
    steps=[
        clean_addresses,
        create_address_numerics,
        create_address_alpha_tokens,
        create_input_phrases,
        first_matching_step,
        unnest_match_candidates,
        extract_match_candidate_details,
    ],
)

pipeline = QueryPipeline(
    con=test_con,
    steps=[
        clean_addresses,
        create_address_numerics,
        create_address_alpha_tokens,
        create_input_phrases,
        first_matching_step,
        unnest_match_candidates,
        extract_match_candidate_details,
        filter_to_top50_candidates,
    ],
)

pipeline = QueryPipeline(
    con=test_con,
    steps=[
        clean_addresses,
        create_address_numerics,
        create_address_alpha_tokens,
        create_input_phrases,
        first_matching_step,
        unnest_match_candidates,
        extract_match_candidate_details,
        filter_to_top50_candidates,
        neighbouring_suburb_match,
    ],
)

pipeline = QueryPipeline(
    con=test_con,
    steps=[
        clean_addresses,
        create_address_numerics,
        create_address_alpha_tokens,
        create_input_phrases,
        first_matching_step,
        unnest_match_candidates,
        extract_match_candidate_details,
        filter_to_top50_candidates,
        neighbouring_suburb_match,
        compute_similarity,
    ],
)

pipeline = QueryPipeline(
    con=test_con,
    steps=[
        clean_addresses,
        create_address_numerics,
        create_address_alpha_tokens,
        create_input_phrases,
        first_matching_step,
        unnest_match_candidates,
        extract_match_candidate_details,
        filter_to_top50_candidates,
        neighbouring_suburb_match,
        compute_similarity,
    ],
)

pipeline = QueryPipeline(
    con=test_con,
    steps=[
        clean_addresses,
        create_address_numerics,
        create_address_alpha_tokens,
        create_input_phrases,
        first_matching_step,
        unnest_match_candidates,
        extract_match_candidate_details,
        filter_to_top50_candidates,
        neighbouring_suburb_match,
        compute_similarity,
        rank_by_similarity,
    ],
)

pipeline = QueryPipeline(
    con=test_con,
    steps=[
        clean_addresses,
        create_address_numerics,
        create_address_alpha_tokens,
        create_input_phrases,
        first_matching_step,
        unnest_match_candidates,
        extract_match_candidate_details,
        filter_to_top50_candidates,
        neighbouring_suburb_match,
        compute_similarity,
        rank_by_similarity,
        select_current,
    ],
)

pipeline = QueryPipeline(
    con=test_con,
    steps=[
        clean_addresses,
        create_address_numerics,
        create_address_alpha_tokens,
        create_input_phrases,
        first_matching_step,
        unnest_match_candidates,
        extract_match_candidate_details,
        filter_to_top50_candidates,
        neighbouring_suburb_match,
        compute_similarity,
        rank_by_similarity,
        select_current,
        rejoin_all_inputs,
    ],
)

# teardown (same order pytest would do)
next(con_gen, None)
next(pc_gen, None)
