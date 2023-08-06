with input_addresses_with_numerics as (
    with tokens as 
    (
        select 
        address_id, 
        trim(regexp_replace(regexp_replace(upper(address), '[^A-Z0-9]+', ' '), '  ', ' ')) address,
        unnest(string_to_array(trim(regexp_replace(regexp_replace(upper(address), '[^A-Z0-9]+', ' '), '  ', ' ')), ' ')) as token
        from input_addresses
    )
    select address_id, address, array_agg(token) numeric_tokens 
    from tokens
    where regexp_matches(token, '[0-9]+')
    group by address_id, address
),
input_phrases AS (
    with tokens_pre1 as 
    (
        select address_id, unnest(string_to_array(regexp_replace(trim(address), '[^A-Z0-9]+', ' ', 'g'), ' ')) token
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
    then unnest(['']) 
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
    t3.addr, 
    case when t3.addr is not null then
    jaro_winkler_similarity(t2.address, t3.addr)
    else 0.0 end as similarity 
    from input_proposed_match t1
    left join input_addresses_with_numerics t2 on t1.address_id1=t2.address_id
    left join addrtext_with_numerics t3 on t1.address_id2=t3.addr_id
),
match_ranked as (
select row_number() over (partition by address_id1 order by similarity desc) rank,
address_id1, 
address_id2, 
address, 
input_numerics,
match_numerics,
addr address_matched,
LOCALITY_NAME suburb, 
POSTCODE postcode,
LATITUDE latitude,
LONGITUDE longitude,
similarity 
from match
left join address_view t4 on match.address_id2=t4.ADDRESS_DETAIL_PID
)
select 
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
where case 
when array_length(t1.input_numerics) == 1 then 
(rank=1 and list_contains(t1.input_numerics, t1.match_numerics[1]))
when array_length(t1.input_numerics) == 2 then
(rank=1 and list_contains(t1.input_numerics, t1.match_numerics[1]) and list_contains(t1.input_numerics, t1.match_numerics[2]))
when array_length(t1.input_numerics) == 3 then
(rank=1 and list_contains(t1.input_numerics, t1.match_numerics[1]) and list_contains(t1.input_numerics, t1.match_numerics[2]) and list_contains(t1.input_numerics, t1.match_numerics[3]))
end
order by address_id1;
-- include unmatched addresses in results