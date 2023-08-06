db.execute("""
create table input_addresses(address_id integer, address varchar);
""")
           
db.execute("""
insert into input_addresses
values
(1, '4/19 rathmins st fairfield'),
(2, '8 mcnae st monee ponds'),
(3, '13 wilkinson stburood east'),
(4, '34/ 121 exhibitino st melbourne'),
(5, '8 mcnay st monee ponds')
""")
           
db.execute("""
create table input_addresses_with_numerics as
with tokens as 
(
    select 
    address_id, 
    trim(regexp_replace(regexp_replace(upper(address), '[^A-Z0-9]+', ' '), '  ', ' ')) address,
    unnest(
        string_to_array(
            trim(regexp_replace(regexp_replace(upper(address), '[^A-Z0-9]+', ' '), '  ', ' ')), ' ')) as token
    from input_addresses
)
select address_id, address, array_agg(token) numeric_tokens 
from tokens
where regexp_matches(token, '[0-9]+')
group by address_id, address
""")

db.execute("""
create table input_phrases AS (
    with tokens_pre1 as 
    (
        select 
        address_id, 
        unnest(string_to_array(regexp_replace(trim(address), '[^A-Z0-9]+', ' ', 'g'), ' ')) token, 
        numeric_tokens
        from input_addresses_with_numerics
    ),
    tokens_pre2 as 
    (
        select 
        address_id, 
        row_number() over () row_num, 
        token,
        numeric_tokens
        from tokens_pre1
    ),
    tokens as 
    (
        select 
        address_id, 
        row_number() over (partition by address_id order by row_num) row_num, 
        numeric_tokens,
        token 
        from tokens_pre2
    )
    select t1.address_id, t1.token || ' ' || t2.token tokenphrase, t1.numeric_tokens
    from tokens t1
    left join tokens t2
    on (t1.address_id, t1.row_num)=(t2.address_id, t2.row_num-1)
    where tokenphrase is not null
);
""")
           
db.execute("""
create table input_phrase_matched_lists as (
    SELECT l.tokenphrase, l.numeric_tokens, l.address_id AS address_id1, r.addr_ids AS address_ids2
    FROM input_phrases AS l 
    LEFT JOIN phraseinverted AS r 
    ON l.tokenphrase=r.tokenphrase AND r.frequency < 1000
);
""")


db.execute("""
create table input_phrase_matched_pre as (
    select 
    address_id1, 
    tokenphrase, 
    case when address_ids2 is null 
    then unnest(['']) 
    else unnest(address_ids2) end address_id2,
    numeric_tokens
    from input_phrase_matched_lists
)""")
           
db.execute("""
create table input_phrase_matched as (
    select 
    address_id1, tokenphrase, numeric_tokens, array_agg(address_id2) address_ids2, count(1) 
    from input_phrase_matched_pre
    group by (address_id1, tokenphrase, numeric_tokens)
)""")
           
db.execute("""
create table input_proposed_match as (
    select
    distinct address_id1, 
    unnest(address_ids2) address_id2
    from input_phrase_matched
)""")

db.execute("""
create table match AS (
    select t1.address_id1 as address_id1, t1.address_id2 as address_id2, 
    t2.address as address, t2.numeric_tokens, t3.addr, t3.token numeric_tokens,
    case when t3.addr is not null then
    jaro_winkler_similarity(t2.address, t3.addr)
    else 0.0 end as similarity 
    from input_proposed_match t1
    left join input_addresses_with_numerics t2 on t1.address_id1=t2.address_id
    left join addrtext_with_numerics t3 on t1.address_id2=t3.addr_id
)""")

# numeric constraint should have numeric tokens in one joined to numeric tokens in another 
# have same number of rows as first numeric token column
db.execute("""
create table match_ranked as (
select row_number() over (partition by address_id1 order by similarity desc) rank,
address_id1, 
address_id2, 
address, 
addr address_matched,
LOCALITY_NAME suburb, 
POSTCODE postcode,
LATITUDE latitude,
LONGITUDE longitude,
similarity 
from match
left join address_view t4 on match.address_id2=t4.ADDRESS_DETAIL_PID
)""")

db.execute("""
select addr_id, addr, array_agg(token) numeric_tokens
from addrtext_with_numerics
group by addr_id, addr
limit 10;
""")      
#
db.execute("""
create table testnums2 as (
values
('a1', [1, 19]),
('a2', [4, 3078]),
('a3', ['']),
('a4', [4, 7])
);
""")
           
db.execute("""
create table testnums2_r as (
values
('a1', [1, 19, 3078]),
('a2', [4]),
('a3', [3056]),
('a4', [5, 8])
);
""")

# this is better
db.execute("""
select t1.col0, t1.col1, t2.col0, t2.col1
from testnums2 t1
left join testnums2_r t2
on t1.col0 = t2.col0
where case 
when array_length(t1.col1) == 1 then 
(list_contains(t1.col1, t2.col1[1]))
when array_length(t1.col1) == 2 then
(list_contains(t1.col1, t2.col1[1]) and list_contains(t1.col1, t2.col1[2]))
when array_length(t1.col1) == 3 then
(list_contains(t1.col1, t2.col1[1]) and list_contains(t1.col1, t2.col1[2]) and list_contains(t1.col1, t2.col1[3]))
end; 
""")

# when one list integers is a subset of another
db.execute("""
create table testnums as (
values 
('a1', '1'),
('a1', '19'),
('a2', '4'),
('a2', '3078'),
('a3', ''),
('a4', '5'),
('a4', '7')
)
""")
           
db.execute("""
select t1.col0, t1.col1, t2.col0, t2.col1
from testnums2 t1
left join testnums2_r t2
on t1.col0=t2.col0 where starts_with(t2.col1, t1.col1)
""")
           
db.execute("""
create table testnums_r as (
values
('a1', '1'),
('a1', '19'),
('a1', '3078'),
('a2', '4'),
('a3', '3056'),
('a4', '5'),
('a4', '8')
)
""")
           
# find which idvalues have numeric tokens that are subsets of corresponding testnums_r entries
db.execute("""
with testnums_counts as (
    select t1.col0, count(t1.col0) num
    from testnums t1
    group by t1.col0
),
numjoins as (
    select t1.col0, t1.col1, t2.col1
    from testnums t1
    inner join testnums_r t2
    on (t1.col1, t1.col0)=(t2.col1, t2.col0)
),
num_joins_counts as (
    select t3.col0, count(t3.col0) num
    from numjoins t3
    group by t3.col0
)
select t1.col0
from testnums_counts t1
inner join num_joins_counts t2
on (t1.col0, t1.num)=(t2.col0, t2.num)
""")           

## select address_id1, address_id2, address, addr, similarity from match_ranked where rank=1;
db.execute("select * from match_ranked where rank=1 order by address_id1;").df()
## need to include the numeric constraint
## include unmatched addresses in results

db.execute("""
create table addrtext (
addr_id varchar,
addr varchar
);
""")

db.execute('drop table input_addresses')
db.execute('drop table input_addresses_with_numerics')
db.execute('drop table input_phrases')
db.execute('drop table input_phrase_matched_lists')
db.execute('drop table input_phrase_matched_pre')
db.execute('drop table input_phrase_matched')
db.execute('drop table input_proposed_match')
db.execute('drop table match')
db.execute('drop table match_ranked')