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
    with tokens_pre1 as 
    (
        select address_id, unnest(string_to_array(regexp_replace(trim(address), '[^A-ZÀÂĀÆÇÉÈÊËÎÏÔŌŒÙÛÜŸ0-9ĄĆĘŁŃÓŚŹŻ]+', ' ', 'g'), ' ')) token
        from input_addresses_with_numerics
    ),
    tokens_pre2 as 
    (
        select address_id, row_number() over () row_num, token
        from tokens_pre1
    ),
    tokens as 
    (
        select address_id, row_number() over (partition by address_id order by row_num) row_num, token from tokens_pre2
    )
    select t1.address_id, t1.token || ' ' || t2.token tokenphrase
    from tokens t1
    left join tokens t2
    on (t1.address_id, t1.row_num)=(t2.address_id, t2.row_num-1)
    where tokenphrase is not null
),
input_phrase_matched_lists as (
    SELECT l.tokenphrase, l.address_id AS address_id1, r.addr_ids AS address_ids2
    FROM input_phrases AS l 
    LEFT JOIN phraseinverted AS r 
    ON l.tokenphrase=r.tokenphrase AND r.frequency < 1000
),
input_phrase_matched_pre as (
    select 
    address_id1, 
    tokenphrase, 
    case when address_ids2 is null 
    then unnest([-1]) 
    else unnest(address_ids2) end address_id2
    from input_phrase_matched_lists
),
input_phrase_matched as ( -- this is clunky
    select 
    address_id1, tokenphrase, array_agg(address_id2) address_ids2, count(1) 
    from input_phrase_matched_pre
    group by (address_id1, tokenphrase)
),
input_proposed_match as (
    select
    distinct address_id1, 
    unnest(address_ids2) address_id2
    from input_phrase_matched
),
match AS (
    select 
    t1.address_id1 as address_id1, 
    t1.address_id2 as address_id2, 
    t2.address as address, 
    t2.numeric_tokens input_numerics, 
    t3.numeric_tokens match_numerics,
    t3.addr address_matched, 
    case when t3.addr is not null then
    ngram_jaccard(t2.address, t3.addr) * numeric_overlap(t2.numeric_tokens, t3.numeric_tokens)
 --   jaro_similarity(t2.address, t3.addr) * numeric_overlap(t2.numeric_tokens, t3.numeric_tokens)
    else 0.0 end as similarity 
    from input_proposed_match t1
    left join input_addresses_with_numerics t2 on t1.address_id1=t2.address_id
    left join addrtext_with_detail t3 on t1.address_id2=t3.addr_id
),
match_ranked as (
    with match_ranked_pre as (
        select
        address_id1, 
        address_id2, 
        match.address,
        address_matched, 
        input_numerics,
        match_numerics,
        suburb suburb, 
        POSTCODE postcode,
        LATITUDE latitude,
        LONGITUDE longitude,
        similarity 
        from match
        left join addrtext_with_detail t4 on match.address_id2=t4.addr_id
    )
    select * from match_ranked_pre where
    list_overlap(input_numerics, match_numerics, 0.5) -- 
),
matches_final as (     
    select 
    row_number() over (partition by address_id1 order by similarity desc) rank,
    address_id1,
    address_id2,
    address,
    address_matched,
    suburb,
    postcode,
    latitude,
    longitude,
    similarity,
    from match_ranked t1
    order by address_id1
)
select t1.address_id, t1.address,
t2.address_id2, t2.address_matched, t2.suburb, t2.postcode, t2.latitude, t2.longitude, t2.similarity
from input_addresses_with_numerics t1
left join matches_final t2
on t1.address_id=t2.address_id1
where (rank=1) or (rank is null)
order by address_id; -- Deal with null case