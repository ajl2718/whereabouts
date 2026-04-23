with input_addresses_with_numerics as (
    with input_addresses_cleaned as (
        select
        address_id,
        trim(regexp_replace(regexp_replace(upper(address), '[^A-ZÀÂĀÆÇÉÈÊËÎÏÔŌŒÙÛÜŸ0-9ĄĆĘŁŃÓŚŹŻ]+', ' ', 'g'), '[ ]+', ' ')) address
        from input_addresses
    ),
    tokens as
    (
        select
        address_id,
        address,
        unnest(string_to_array(address, ' ')) as token
        from input_addresses_cleaned
    ),
    addresses_grouped as (
        select address_id, address, array_agg(token) numeric_tokens
        from tokens
        where regexp_matches(token, '[0-9]+[A-ZÀÂĀÆÇÉÈÊËÎÏÔŌŒÙÛÜŸĄĆĘŁŃÓŚŹŻ]{0,1}')
        group by address_id, address
    )
    select t2.address_id, t2.address, t1.numeric_tokens
    from input_addresses_cleaned t2
    left join addresses_grouped t1
    on t2.address_id=t1.address_id
),
input_phrases AS (
    -- Fix: materialize the token array once so generate_subscripts and unnest are
    -- guaranteed to operate on the same array, giving deterministic positional alignment.
    -- Address is already cleaned from input_addresses_with_numerics, so no regex needed.
    with token_arrays as (
        select address_id, string_to_array(address, ' ') as arr
        from input_addresses_with_numerics
    ),
    tokens as (
        select
        address_id,
        unnest(arr) as token,
        generate_subscripts(arr, 1) as row_num
        from token_arrays
    )
    select t1.address_id, t1.token || ' ' || t2.token tokenphrase
    from tokens t1
    left join tokens t2
    on (t1.address_id, t1.row_num)=(t2.address_id, t2.row_num-1)
    where tokenphrase is not null
),
input_phrase_matched_lists as (
    SELECT l.address_id AS address_id1, r.addr_ids AS address_ids2
    FROM input_phrases AS l
    LEFT JOIN remote.phraseinverted AS r
    ON l.tokenphrase=r.tokenphrase AND r.frequency < 1000
),
-- Fix: collapse the redundant unnest -> reaggregate -> unnest cycle into a single step
input_proposed_match as (
    select distinct address_id1, unnest(address_ids2) address_id2
    from input_phrase_matched_lists
    where address_ids2 is not null
),
-- Fix: select suburb/postcode/lat/lng from t3 here to avoid joining addrtext_with_detail twice
match AS (
    select
    t1.address_id1 as address_id1,
    t1.address_id2 as address_id2,
    t2.address as address,
    t2.numeric_tokens input_numerics,
    t3.numeric_tokens match_numerics,
    t3.addr address_matched,
    t3.suburb suburb,
    t3.POSTCODE postcode,
    t3.LATITUDE latitude,
    t3.LONGITUDE longitude,
    case when t3.addr is not null then
    ngram_jaccard(t2.address, t3.addr) * multiset_jaccard(t2.numeric_tokens, t3.numeric_tokens)
    else 0.0 end as similarity
    from input_proposed_match t1
    left join input_addresses_with_numerics t2 on t1.address_id1=t2.address_id
    left join remote.addrtext_with_detail t3 on t1.address_id2=t3.addr_id
),
-- Fix: remove redundant nested CTE (match_ranked_pre)
match_ranked as (
    select * from match
    where list_overlap(input_numerics, match_numerics, 0.5)
),
matches_final as (
    select
    -- Fix: add address_id2 as tiebreaker so equal-similarity candidates are ranked
    -- deterministically rather than arbitrarily, preventing run-to-run variation
    row_number() over (partition by address_id1 order by similarity desc, address_id2 asc) rank,
    address_id1,
    address_id2,
    address,
    address_matched,
    suburb,
    postcode,
    latitude,
    longitude,
    similarity  -- Fix: removed trailing comma
    from match_ranked
    order by address_id1
)
select t1.address_id, t1.address,
t2.address_id2, t2.address_matched, t2.suburb, t2.postcode, t2.latitude, t2.longitude, t2.similarity
from input_addresses_with_numerics t1
left join matches_final t2
on t1.address_id=t2.address_id1
where (rank<=?) or (rank is null) -- select top matches
order by address_id; -- Deal with null case
