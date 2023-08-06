# original query
con.execute("""
CREATE VIEW ADDRESS_VIEW
AS
SELECT
AD.ADDRESS_DETAIL_PID as ADDRESS_DETAIL_PID,
AD.STREET_LOCALITY_PID as STREET_LOCALITY_PID,
AD.LOCALITY_PID as LOCALITY_PID,
AD.BUILDING_NAME as BUILDING_NAME,
AD.LOT_NUMBER_PREFIX as LOT_NUMBER_PREFIX,
AD.LOT_NUMBER as LOT_NUMBER,
AD.LOT_NUMBER_SUFFIX as LOT_NUMBER_SUFFIX,
FTA.NAME as FLAT_TYPE,
AD.FLAT_NUMBER_PREFIX as FLAT_NUMBER_PREFIX,
AD.FLAT_NUMBER as FLAT_NUMBER,
AD.FLAT_NUMBER_SUFFIX as FLAT_NUMBER_SUFFIX,
LTA.NAME as LEVEL_TYPE,
AD.LEVEL_NUMBER_PREFIX as LEVEL_NUMBER_PREFIX,
AD.LEVEL_NUMBER as LEVEL_NUMBER,
AD.LEVEL_NUMBER_SUFFIX as LEVEL_NUMBER_SUFFIX,
AD.NUMBER_FIRST_PREFIX as NUMBER_FIRST_PREFIX,
AD.NUMBER_FIRST as NUMBER_FIRST,
AD.NUMBER_FIRST_SUFFIX as NUMBER_FIRST_SUFFIX,
AD.NUMBER_LAST_PREFIX as NUMBER_LAST_PREFIX,
AD.NUMBER_LAST as NUMBER_LAST,
AD.NUMBER_LAST_SUFFIX as NUMBER_LAST_SUFFIX,
SL.STREET_NAME as STREET_NAME,
SL.STREET_CLASS_CODE as STREET_CLASS_CODE,
SCA.NAME as STREET_CLASS_TYPE,
SL.STREET_TYPE_CODE as STREET_TYPE_CODE,
SL.STREET_SUFFIX_CODE as STREET_SUFFIX_CODE,
SSA.NAME as STREET_SUFFIX_TYPE,
L.LOCALITY_NAME as LOCALITY_NAME,
ST.STATE_ABBREVIATION as STATE_ABBREVIATION,
AD.POSTCODE as POSTCODE,
ADG.LATITUDE as LATITUDE,
ADG.LONGITUDE as LONGITUDE,
GTA.NAME as GEOCODE_TYPE,
AD.CONFIDENCE as CONFIDENCE,
AD.ALIAS_PRINCIPAL as ALIAS_PRINCIPAL,
AD.PRIMARY_SECONDARY as PRIMARY_SECONDARY,
AD.LEGAL_PARCEL_ID as LEGAL_PARCEL_ID,
AD.DATE_CREATED as DATE_CREATED
FROM
ADDRESS_DETAIL AD 
LEFT JOIN FLAT_TYPE_AUT FTA ON AD.FLAT_TYPE_CODE=FTA.CODE
LEFT JOIN LEVEL_TYPE_AUT LTA ON AD.LEVEL_TYPE_CODE=LTA.CODE
JOIN STREET_LOCALITY SL ON AD.STREET_LOCALITY_PID=SL.STREET_LOCALITY_PID
LEFT JOIN STREET_SUFFIX_AUT SSA ON SL.STREET_SUFFIX_CODE=SSA.CODE
LEFT JOIN STREET_CLASS_AUT SCA ON SL.STREET_CLASS_CODE=SCA.CODE 
LEFT JOIN STREET_TYPE_AUT STA ON SL.STREET_TYPE_CODE=STA.CODE
JOIN LOCALITY L ON AD.LOCALITY_PID = L.LOCALITY_PID
JOIN ADDRESS_DEFAULT_GEOCODE ADG ON AD.ADDRESS_DETAIL_PID=ADG.ADDRESS_DETAIL_PID
LEFT JOIN GEOCODE_TYPE_AUT GTA ON ADG.GEOCODE_TYPE_CODE=GTA.CODE
LEFT JOIN GEOCODED_LEVEL_TYPE_AUT GLTA ON AD.LEVEL_GEOCODED_CODE=GLTA.CODE
JOIN STATE ST ON L.STATE_PID=ST.STATE_PID
WHERE 
AD.CONFIDENCE > -1""")

con.execute("""
CREATE VIEW ADDRESS_VIEW
AS
SELECT
AD.ADDRESS_DETAIL_PID as ADDRESS_DETAIL_PID,
AD.STREET_LOCALITY_PID as STREET_LOCALITY_PID,
AD.LOCALITY_PID as LOCALITY_PID,
AD.BUILDING_NAME as BUILDING_NAME,
AD.LOT_NUMBER_PREFIX as LOT_NUMBER_PREFIX,
AD.LOT_NUMBER as LOT_NUMBER,
AD.LOT_NUMBER_SUFFIX as LOT_NUMBER_SUFFIX,
FTA.NAME as FLAT_TYPE,
AD.FLAT_NUMBER_PREFIX as FLAT_NUMBER_PREFIX,
AD.FLAT_NUMBER as FLAT_NUMBER,
AD.FLAT_NUMBER_SUFFIX as FLAT_NUMBER_SUFFIX,
LTA.NAME as LEVEL_TYPE,
AD.LEVEL_NUMBER_PREFIX as LEVEL_NUMBER_PREFIX,
AD.LEVEL_NUMBER as LEVEL_NUMBER,
AD.LEVEL_NUMBER_SUFFIX as LEVEL_NUMBER_SUFFIX,
AD.NUMBER_FIRST_PREFIX as NUMBER_FIRST_PREFIX,
AD.NUMBER_FIRST as NUMBER_FIRST,
AD.NUMBER_FIRST_SUFFIX as NUMBER_FIRST_SUFFIX,
AD.NUMBER_LAST_PREFIX as NUMBER_LAST_PREFIX,
AD.NUMBER_LAST as NUMBER_LAST,
AD.NUMBER_LAST_SUFFIX as NUMBER_LAST_SUFFIX,
SL.STREET_NAME as STREET_NAME,
SL.STREET_CLASS_CODE as STREET_CLASS_CODE,
SCA.NAME as STREET_CLASS_TYPE,
SL.STREET_TYPE_CODE as STREET_TYPE_CODE,
SL.STREET_SUFFIX_CODE as STREET_SUFFIX_CODE,
SSA.NAME as STREET_SUFFIX_TYPE,
L.LOCALITY_NAME as LOCALITY_NAME,
ST.STATE_ABBREVIATION as STATE_ABBREVIATION,
AD.POSTCODE as POSTCODE,
ADG.LATITUDE as LATITUDE,
ADG.LONGITUDE as LONGITUDE,
GTA.NAME as GEOCODE_TYPE,
AD.CONFIDENCE as CONFIDENCE,
AD.ALIAS_PRINCIPAL as ALIAS_PRINCIPAL,
AD.PRIMARY_SECONDARY as PRIMARY_SECONDARY,
AD.LEGAL_PARCEL_ID as LEGAL_PARCEL_ID,
AD.DATE_CREATED as DATE_CREATED
FROM
ADDRESS_DETAIL AD 
LEFT JOIN FLAT_TYPE_AUT FTA ON AD.FLAT_TYPE_CODE=FTA.CODE
LEFT JOIN LEVEL_TYPE_AUT LTA ON AD.LEVEL_TYPE_CODE=LTA.CODE
JOIN STREET_LOCALITY SL ON AD.STREET_LOCALITY_PID=SL.STREET_LOCALITY_PID
LEFT JOIN STREET_SUFFIX_AUT SSA ON SL.STREET_SUFFIX_CODE=SSA.CODE
LEFT JOIN STREET_CLASS_AUT SCA ON SL.STREET_CLASS_CODE=SCA.CODE 
LEFT JOIN STREET_TYPE_AUT STA ON SL.STREET_TYPE_CODE=STA.CODE
JOIN LOCALITY L ON AD.LOCALITY_PID = L.LOCALITY_PID
JOIN ADDRESS_DEFAULT_GEOCODE ADG ON AD.ADDRESS_DETAIL_PID=ADG.ADDRESS_DETAIL_PID
LEFT JOIN GEOCODE_TYPE_AUT GTA ON ADG.GEOCODE_TYPE_CODE=GTA.CODE
LEFT JOIN GEOCODED_LEVEL_TYPE_AUT GLTA ON AD.LEVEL_GEOCODED_CODE=GLTA.CODE
JOIN STATE ST ON L.STATE_PID=ST.STATE_PID
WHERE 
AD.CONFIDENCE > -1""")

db.execute("""
with phraseinverted2 as (
    select tokenphrase tokenphrase, array_agg(addr_id) addr_ids, count(1) frequency
    from phrase
    group by tokenphrase
),
test_blah as (
    select tokenphrase, addr_ids, frequency, row_number() over () row_num
    from phraseinverted2
)
select * from test_blah
where row_num == 1243;
""").df()

# use window functions to iteratively add in inverted phrases.
db.execute("""
with table_temp as (
    select *, row_number() over () row_num
    from phrase
)
select * from table_temp
where row_num % 1000000 == 0;
""").df()
           
db.execute("""
insert into addrtext
with address_detail_with_row_num as (
    select 
    *,
    row_number() over () row_num
    from address_view where address_view.state_abbreviation == $1
),
address_detail_subset as (
    select * from address_detail_with_row_num
    where row_num % 10 == $2
)
select
address_detail_pid as addr_id,
(
    trim(regexp_replace
    (
        ifnull(building_name, '') || ' ' ||
        ifnull(cast(lot_number_prefix as text), '') || '' ||
        ifnull(cast(lot_number as text), '') || '' ||
        ifnull(cast(lot_number_suffix as text), '') || ' ' ||
        ifnull(flat_type, '') || ' ' ||
        ifnull(cast(flat_number_prefix as text), '') || '' ||
        ifnull(cast(flat_number as text), '') || '' ||
        ifnull(cast(flat_number_suffix as text), '') || ' ' ||
        ifnull(level_type, '') || ' ' ||
        ifnull(cast(level_number_prefix as text), '') || '' ||
        ifnull(cast(level_number as text), '') || '' ||
        ifnull(cast(level_number_suffix as text), '') || ' ' ||
        ifnull(cast(number_first_prefix as text), '') || '' ||
        ifnull(cast(number_first as text), '') || '' ||
        ifnull(cast(number_first_suffix as text), '') || ' ' ||
        ifnull(cast(number_last_prefix as text), '') || '' ||
        ifnull(cast(number_last as text), '') || '' ||
        ifnull(cast(number_last_suffix as text), '') || ' ' ||
        ifnull(street_name, '') || ' ' ||
        ifnull(street_type_code, '') || ' ' ||
        ifnull(locality_name, '') || ' ' ||
        ifnull(street_suffix_type, '') || ' ' ||
        ifnull(state_abbreviation, '') || ' ' ||
        ifnull(cast(postcode as text), ''),
        '[\s]+', ' ', 'g')
    )
) addr
from address_detail_subset;
""", ["SA", 0])
           
db.execute("""
insert into addrtext
select
address_detail_pid as addr_id,
(
    trim(regexp_replace
    (
        ifnull(building_name, '') || ' ' ||
        ifnull(cast(lot_number_prefix as text), '') || '' ||
        ifnull(cast(lot_number as text), '') || '' ||
        ifnull(cast(lot_number_suffix as text), '') || ' ' ||
        ifnull(flat_type, '') || ' ' ||
        ifnull(cast(flat_number_prefix as text), '') || '' ||
        ifnull(cast(flat_number as text), '') || '' ||
        ifnull(cast(flat_number_suffix as text), '') || ' ' ||
        ifnull(level_type, '') || ' ' ||
        ifnull(cast(level_number_prefix as text), '') || '' ||
        ifnull(cast(level_number as text), '') || '' ||
        ifnull(cast(level_number_suffix as text), '') || ' ' ||
        ifnull(cast(number_first_prefix as text), '') || '' ||
        ifnull(cast(number_first as text), '') || '' ||
        ifnull(cast(number_first_suffix as text), '') || ' ' ||
        ifnull(cast(number_last_prefix as text), '') || '' ||
        ifnull(cast(number_last as text), '') || '' ||
        ifnull(cast(number_last_suffix as text), '') || ' ' ||
        ifnull(street_name, '') || ' ' ||
        ifnull(street_type_code, '') || ' ' ||
        ifnull(locality_name, '') || ' ' ||
        ifnull(street_suffix_type, '') || ' ' ||
        ifnull(state_abbreviation, '') || ' ' ||
        ifnull(cast(postcode as text), ''),
        '[\s]+', ' ', 'g')
    )
) addr
from
address_view a where a.state_abbreviation = 'SA';
""")

db.execute("""
create table phraseinverted2 as 
SELECT tokenphrase,array_agg(addr_id),count(1)
FROM phrase
GROUP BY tokenphrase;
""")

db.execute("""
CREATE TABLE trigramphrase -- Compute 2-word trigram phrases
(addr_id varchar not null,
trigramphrase text not null
);

CREATE TABLE trigramphraseinverted -- Compute trigram inverted index
(trigramphrase text not null,
addr_ids varchar[] not null,
frequency bigint not null);
""")

db.execute("""
with tokens_pre as (
select addr_id, unnest(str_split(addr, ' ')) token from addrtext 
),
tokens as (
select addr_id, token, row_number() over (partition by addr_id) row_num from tokens_pre
order by 
addr_id, row_num
)
select * from tokens limit 10;
""")
           
db.execute("""
insert into trigramphrase
with tokens_pre as (
select addr_id, unnest(str_split(addr, ' ')) token from addrtext 
),
tokens as (
select addr_id, token, row_number() over (partition by addr_id) row_num from tokens_pre
order by 
addr_id, row_num
),
trigrams as (
select addr_id, row_num, token, substr(token, n1, 3) trigram 
from tokens
where trigram != ''
and
strlen(trigram) >= 3
order by addr_id, row_num
),
trigramphrases as 
(
select t1.addr_id, t1.trigram || ' ' || t2.trigram trigramphrase
from trigrams t1
left join trigrams t2
on (t1.addr_id, t1.row_num)=(t2.addr_id, t2.row_num-1)
where trigramphrase is not null
)
select addr_id, substr(md5(trigramphrase), 1, 6) md5phrase from trigramphrases;
""")

db.execute("""
with phrase_nums as (
    select addr_id, tokenphrase, row_number() over (partition by addr_id) counter
    from phrase order by addr_id
),
tokens_pre as (
    select addr_id, unnest(str_split(tokenphrase, ' ')) token, counter
    from phrase_nums order by addr_id, counter 
)
select addr_id, token, counter
from tokens_pre
limit 10;
""")

db.execute("""
CREATE TABLE phrase -- Compute 2-word phrase tokens
(addr_id varchar not null,
tokenphrase text not null);

CREATE TABLE phraseinverted -- Compute inverted index
(tokenphrase text not null,
addr_ids varchar[] not null,
frequency bigint not null);
""")

db.execute("""
create table addrtext_with_numerics as (
    with addrtext_with_tokens as (
        select 
        addr_id, addr, unnest(str_split(addr, ' ')) token
        from addrtext
    ),
    addrtext_with_tokens_unnest as (
        select addr_id, addr, token from 
        addrtext_with_tokens
        where regexp_matches(token, '[0-9]+')    
    )
    select addr_id, addr, array_agg(token) numeric_tokens
    from addrtext_with_tokens_unnest
    group by addr_id, addr
)
""")

db.execute("""
create table input_addresses(address_id integer, address varchar);
""")

db.execute("""
insert into input_addresses
values (1, '4 / 19 rathmins st fairfield'), 
(2, '8 mcnae st monee ponds'),
(3, '13 wilkinson st buroood east'),
(4, '34 / 121 exhibtin st melbourne');
""")