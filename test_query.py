import duckdb
import pandas as pd 
con = duckdb.connect('gnaf_vic')

# create a table with the address info
con.execute("""
create table input_addresses_test (
address_id integer,
address varchar);""")

# load in the flat_type_aut data
source_folder = f'/home/alex/Desktop/Data/GNAF/G-NAF/G-NAF MAY 2023/Authority Code'
filename = 'Authority_Code_FLAT_TYPE_AUT_psv.psv'
full_path = f'{source_folder}/{filename}'

con.execute("""
CREATE TABLE FLAT_TYPE_AUT (
 code varchar(7) PRIMARY KEY NOT NULL,
 name varchar(50) NOT NULL,
 description varchar(30)
);
""")
            
con.execute(f'insert into FLAT_TYPE_AUT select * from read_csv_auto("{full_path}", header=True, delim="|")')
     

con.execute("""
CREATE TABLE ADDRESS_ALIAS (
 address_alias_pid varchar(15) PRIMARY KEY NOT NULL,
 date_created date NOT NULL,
 date_retired date,
 principal_pid varchar(15) REFERENCES ADDRESS_DETAIL(address_detail_pid) NOT NULL,
 alias_pid varchar(15) REFERENCES ADDRESS_DETAIL(address_detail_pid) NOT NULL,
 alias_type_code varchar(10) REFERENCES ADDRESS_ALIAS_TYPE_AUT(code) NOT NULL,
 alias_comment varchar(200) 
);
""")

# debugging the issue with creating the address view in duckdb v0.8.0            
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
SL.STREET_TYPE_CODE as STREET_TYPE_CODE,
SL.STREET_SUFFIX_CODE as STREET_SUFFIX_CODE,
SSA.NAME as STREET_SUFFIX_TYPE,
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
JOIN ADDRESS_DEFAULT_GEOCODE ADG ON AD.ADDRESS_DETAIL_PID=ADG.ADDRESS_DETAIL_PID
LEFT JOIN GEOCODE_TYPE_AUT GTA ON ADG.GEOCODE_TYPE_CODE=GTA.CODE
LEFT JOIN GEOCODED_LEVEL_TYPE_AUT GLTA ON AD.LEVEL_GEOCODED_CODE=GLTA.CODE
WHERE 
AD.CONFIDENCE > -1;
""")

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
LEFT JOIN LEVEL_TYPE_AUT LTA ON AD.LEVEL_TYPE_CODE=LTA.CODE
JOIN STREET_LOCALITY SL ON AD.STREET_LOCALITY_PID=SL.STREET_LOCALITY_PID
LEFT JOIN STREET_SUFFIX_AUT SSA ON SL.STREET_SUFFIX_CODE=SSA.CODE
LEFT JOIN STREET_CLASS_AUT SCA ON SL.STREET_CLASS_CODE=SCA.CODE 
LEFT JOIN STREET_TYPE_AUT STA ON SL.STREET_TYPE_CODE=STA.CODE
JOIN LOCALITY L ON AD.LOCALITY_PID = L.LOCALITY_PID
JOIN ADDRESS_DEFAULT_GEOCODE ADG ON AD.ADDRESS_DETAIL_PID=ADG.ADDRESS_DETAIL_PID
LEFT JOIN GEOCODE_TYPE_AUT GTA ON ADG.GEOCODE_TYPE_CODE=GTA.CODE
LEFT JOIN GEOCODED_LEVEL_TYPE_AUT GLTA ON AD.LEVEL_GEOCODED_CODE=GLTA.CODE
WHERE 
AD.CONFIDENCE > -1;
""")
            
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
AD.FLAT_NUMBER_PREFIX as FLAT_NUMBER_PREFIX,
AD.FLAT_NUMBER as FLAT_NUMBER,
AD.FLAT_NUMBER_SUFFIX as FLAT_NUMBER_SUFFIX,
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
JOIN STREET_LOCALITY SL ON AD.STREET_LOCALITY_PID=SL.STREET_LOCALITY_PID
LEFT JOIN STREET_CLASS_AUT SCA ON SL.STREET_CLASS_CODE=SCA.CODE 
LEFT JOIN STREET_TYPE_AUT STA ON SL.STREET_TYPE_CODE=STA.CODE
JOIN LOCALITY L ON AD.LOCALITY_PID = L.LOCALITY_PID
JOIN ADDRESS_DEFAULT_GEOCODE ADG ON AD.ADDRESS_DETAIL_PID=ADG.ADDRESS_DETAIL_PID
LEFT JOIN GEOCODE_TYPE_AUT GTA ON ADG.GEOCODE_TYPE_CODE=GTA.CODE
LEFT JOIN GEOCODED_LEVEL_TYPE_AUT GLTA ON AD.LEVEL_GEOCODED_CODE=GLTA.CODE
JOIN STATE ST ON L.STATE_PID=ST.STATE_PID
WHERE 
AD.CONFIDENCE > -1
""")

# seems to be due to the flat_type code being empty for some addresses
con.execute("""
CREATE VIEW ADDRESS_VIEW
AS
SELECT
AD.ADDRESS_DETAIL_PID as ADDRESS_DETAIL_PID,
AD.STREET_LOCALITY_PID as STREET_LOCALITY_PID,
AD.LOCALITY_PID as LOCALITY_PID,
AD.BUILDING_NAME as BUILDING_NAME,
AD.LOT_NUMBER_PREFIX as LOT_NUMBER_PREFIX
FROM
ADDRESS_DETAIL AD 
JOIN LOCALITY L ON AD.LOCALITY_PID = L.LOCALITY_PID
JOIN STREET_LOCALITY SL ON AD.STREET_LOCALITY_PID=SL.STREET_LOCALITY_PID
WHERE 
AD.CONFIDENCE > -1;
""")

con.execute("""
CREATE TABLE ADDRESS_DETAIL_SMALL
AS
SELECT 
LOCALITY_PID, ADDRESS_DETAIL_PID, FLAT_TYPE_CODE, STREET_LOCALITY_PID
FROM 
ADDRESS_DETAIL 
LIMIT 1;
""")
            
con.execute("""
CREATE TABLE STREET_LOCALITY_SMALL 
AS
SELECT STREET_LOCALITY_PID FROM STREET_LOCALITY
WHERE STREET_LOCALITY_PID=='VIC2036492';
""")
            
con.execute("""
CREATE TABLE LOCALITY_SMALL 
AS
SELECT locality_pid, locality_name 
FROM LOCALITY
where
locality_pid = 'loc42e60600a8c9';
""")        

# this causes an error 'logical index column 3 out of range' - fixed
con.execute("""
CREATE VIEW ADDRESS_VIEW
AS
SELECT
AD.ADDRESS_DETAIL_PID as ADDRESS_DETAIL_PID,
AD.STREET_LOCALITY_PID as STREET_LOCALITY_PID
FROM
ADDRESS_DETAIL_SMALL AD 
JOIN LOCALITY_SMALL L ON AD.LOCALITY_PID = L.LOCALITY_PID
LEFT JOIN FLAT_TYPE_AUT FTA ON AD.FLAT_TYPE_CODE=FTA.CODE
JOIN STREET_LOCALITY_SMALL SL ON AD.STREET_LOCALITY_PID=SL.STREET_LOCALITY_PID
""")

# this does work
#             
con.execute("""
CREATE VIEW ADDRESS_VIEW
AS
SELECT
AD.ADDRESS_DETAIL_PID as ADDRESS_DETAIL_PID,
AD.STREET_LOCALITY_PID as STREET_LOCALITY_PID
FROM
ADDRESS_DETAIL AD 
JOIN LOCALITY L ON AD.LOCALITY_PID = L.LOCALITY_PID
LEFT JOIN FLAT_TYPE_AUT FTA ON AD.FLAT_TYPE_CODE=FTA.CODE
LEFT JOIN STREET_LOCALITY SL ON AD.STREET_LOCALITY_PID=SL.STREET_LOCALITY_PID
""")
            
con.execute("""
CREATE VIEW ADDRESS_VIEW_TEST
AS
SELECT
AD.ADDRESS_DETAIL_PID as ADDRESS_DETAIL_PID,
AD.STREET_LOCALITY_PID as STREET_LOCALITY_PID
FROM
ADDRESS_DETAIL_SMALL AD 
JOIN LOCALITY L ON AD.LOCALITY_PID = L.LOCALITY_PID
LEFT JOIN FLAT_TYPE_AUT FTA ON AD.FLAT_TYPE_CODE=FTA.CODE
""")

# but this works        
con.execute("""
create VIEW address_view_test_2
as 
select 
ad.address_detail_pid as address_detail_pid,
ad.street_locality_pid as street_locality_pid
from address_view_test AD
JOIN STREET_LOCALITY_SMALL SL ON AD.STREET_LOCALITY_PID=SL.STREET_LOCALITY_PID
""")

# joining on empty table            
                    
# no error with this
con.execute("""
CREATE VIEW ADDRESS_VIEW
AS
SELECT
AD.ADDRESS_DETAIL_PID as ADDRESS_DETAIL_PID,
AD.STREET_LOCALITY_PID as STREET_LOCALITY_PID
FROM
ADDRESS_DETAIL_SMALL AD 
JOIN LOCALITY L ON AD.LOCALITY_PID = L.LOCALITY_PID
JOIN STREET_LOCALITY_SMALL SL ON AD.STREET_LOCALITY_PID=SL.STREET_LOCALITY_PID
""")



# no error if one of the joins removed
con.execute("""
CREATE VIEW ADDRESS_VIEW
AS
SELECT
AD.ADDRESS_DETAIL_PID as ADDRESS_DETAIL_PID,
AD.STREET_LOCALITY_PID as STREET_LOCALITY_PID,
AD.LOCALITY_PID as LOCALITY_PID,
AD.BUILDING_NAME as BUILDING_NAME,
AD.LOT_NUMBER_PREFIX as LOT_NUMBER_PREFIX
FROM
ADDRESS_DETAIL AD 
JOIN LOCALITY L ON AD.LOCALITY_PID = L.LOCALITY_PID
LEFT JOIN FLAT_TYPE_AUT FTA ON AD.FLAT_TYPE_CODE=FTA.CODE
JOIN STREET_LOCALITY SL ON AD.STREET_LOCALITY_PID=SL.STREET_LOCALITY_PID
WHERE 
AD.CONFIDENCE > -1;
""")
            
con.execute("""
CREATE VIEW ADDRESS_VIEW
AS
SELECT
AD.ADDRESS_DETAIL_PID as ADDRESS_DETAIL_PID,
AD.STREET_LOCALITY_PID as STREET_LOCALITY_PID,
AD.LOCALITY_PID as LOCALITY_PID,
AD.BUILDING_NAME as BUILDING_NAME,
AD.LOT_NUMBER_PREFIX as LOT_NUMBER_PREFIX
FROM
ADDRESS_DETAIL AD 
LEFT JOIN FLAT_TYPE_AUT FTA ON AD.FLAT_TYPE_CODE=FTA.CODE
JOIN STREET_LOCALITY SL ON AD.STREET_LOCALITY_PID=SL.STREET_LOCALITY_PID
JOIN LOCALITY L ON AD.LOCALITY_PID = L.LOCALITY_PID
WHERE 
AD.CONFIDENCE > -1;
""")
            
# issue with the locality table
con.execute("""
with input_addresses_with_row_num as (
select address_id, address, row_number() over () row_num from input_addresses_test
)
select * from input_addresses_with_row_num
where row_num % 4 == ?;
""", [1]).df()
            
# test the concatenation of two tables
#con.execute("create table test_table (phrase varchar, ids varchar[]);")

con.execute("insert into phraseinverted values ('28 CHARLES', ['GAVIC410804993', 'GAVIC421993674', 'GAVIC421993675', 'GAVIC420776534', 'GAVIC423992406', 'GAVIC419911669', 'GAVIC421997227', 'GAVIC419725167'], 8);")

df = pd.DataFrame(data={'address_id': [1, 2, 3, 4, 5, 6, 7, 8], 
                        'address': ['4 / 19 rathmins st fairfield', 
                                    '10 melburn rd gisborne', 
                                    '8 mcnay st moonee pond', 
                                    '13 wilkinson st burwood east', 
                                    '64 lansdown st east st kilda', 
                                    '34 / 121 exhibition st melbourne', 
                                    '780 elizabeth st melburne', 
                                    '84 barkly st calrton north']})

con.execute("INSERT INTO input_addresses_test SELECT * FROM df")
con.execute("drop table if exists input_addresses;")

query_matcher_test = """
with input_phrase_matched_pre as (
    SELECT l.tokenphrase, l.address_id AS address_id1, r.addr_ids AS address_ids2
    FROM input_phrases_test AS l 
    LEFT JOIN phraseinverted AS r 
    ON l.tokenphrase=r.tokenphrase AND r.frequency < 2500
),
input_phrase_matched as (
    select address_id1, tokenphrase, unnest(address_ids2) address_id2
    from input_phrase_matched_pre
)
select 
address_id1, 
tokenphrase, 
array_agg(address_id2) addr_ids2, 
count(1) from input_phrase_matched
group by (address_id1, tokenphrase);
"""

# also for standard query: use the street and locality tables to generate phrases rather than addrtext
# reduces the computation and storage requirements

# number + trigram + trigram -> phrase
# trigram inputs
input_query = """
with tokens as (
    select 
    address_id, 
    str_split(address, ' ') tokens
    from input_addresses_test
)
select address_id, tokens[1] from tokens;
"""

query0 = """
create table seqs(n1 integer, n2 integer);
"""

query = """
insert into seqs
values
(1, 3), 
(2, 3), 
(3, 3), 
(4, 3), 
(5, 3), 
(6, 3), 
(7, 3), 
(8, 3),
(9, 3),
(10, 3),
(11, 3),
(12, 3),
(13, 3);
"""

# trigrams from input_addresses_test
# should make these composed of triplets (number, token, token)
query4 = """
with tokens_pre as (
select address_id, unnest(str_split(address, ' ')) token from input_addresses_test
),
tokens as (
select address_id, token, row_number() over (partition by address_id) row_num from tokens_pre
order by 
address_id, row_num
),
trigrams as (
select address_id, row_num, token, substr(token, n1, 3) trigram from tokens, seqs
where trigram != ''
and
strlen(trigram) >= 2
order by address_id, row_num
),
trigramphrases as 
(
select t1.address_id, t1.trigram || ' ' || t2.trigram trigramphrase
from trigrams t1
left join trigrams t2
on (t1.address_id, t1.row_num)=(t2.address_id, t2.row_num-1)
where trigramphrase is not null
)
select address_id, trigramphrase md5phrase from trigramphrases;
"""

con.execute(input_query).df()

query_trigrams_test = 
"""
with input_trigrams as (
    select 
    address_detail_pid,
    number_first, 
    substr(street_name, 1, 3) street_trigram, 
    substr(locality_name, 1, 3) locality_trigram
    from address_view
    union
    select 
    address_detail_pid,
    number_first, 
    substr(street_name, 2, 3) street_trigram, 
    substr(locality_name, 2, 3) locality_trigram
    from address_view
    union
    select 
    address_detail_pid,
    number_first, 
    substr(street_name, 1, 3) street_trigram, 
    substr(locality_name, 4, 3) locality_trigram
    from address_view
),
trigramphrases as (
    select 
    address_detail_pid,
    substr(md5(number_first || ' | ' || street_trigram || ' | ' || locality_trigram), 1, 5) phrase
    from trigrams
)
"""

query = """
with trigrams as (
    select 
    address_detail_pid,
    number_first, 
    substr(street_name, 1, 3) street_trigram, 
    substr(locality_name, 1, 3) locality_trigram
    from address_view
    union
    select 
    address_detail_pid,
    number_first, 
    substr(street_name, 2, 3) street_trigram, 
    substr(locality_name, 2, 3) locality_trigram
    from address_view
    union
    select 
    address_detail_pid,
    number_first, 
    substr(street_name, 1, 3) street_trigram, 
    substr(locality_name, 4, 3) locality_trigram
    from address_view
),
trigramphrases as (
    select 
    address_detail_pid,
    substr(md5(number_first || ' | ' || street_trigram || ' | ' || locality_trigram), 1, 5) phrase
    from trigrams
)
select count(phrase) freq, phrase
from
trigramphrases
group by phrase
order by freq desc
"""

con.execute(query).df()

# for reverse geocoding: get the address text and corresponding lat lng values
texts = db.execute("""
select 
at.addr_id address_id,
at.addr address,
av.latitude latitude,
av.longitude longitude
from 
addrtext at
inner join
address_view av
on at.addr_id = av.address_detail_pid;
""").df()


db.execute("""
create table addrtext as
select distinct addr_id, addr
from addrtext_pre;
""")