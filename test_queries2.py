import duckdb

con = duckdb.connect('gnaf_au')
         
# create some example tables to understand the basics (oh dear...)
con.execute("""
create table person as (
values 
(1, 'albo', 'AU', 1),
(2, 'vladimir', 'RU', 1),
(3, 'lula', 'BR', 2),
(4, 'dan', 'AU', 2),
(5, 'chris', 'AU', 2),
(6, 'joe', 'US', 2),
(7, 'yabovsky', 'QT', 2)
);
""")
            
con.execute("""
create table country as (
values
('AU', 'Australia'),
('RU', 'Russia'),
('BR', 'Brazil'),
('US', 'United States')
)
""")

con.execute("""
create table height_code as (
values
(1, 'short'),
(2, 'tall')
)
""")      

# create an empty table
con.execute("""
create table person_code(person_id integer, person_badness varchar);
""")

# now do some joins
# join means inner join
con.execute("""
create view person_country as 
select 
p.col0 as person_id, 
p.col1 as person_name, 
p.col2 as country_code,
from person p
join person_code pc on p.col0=pc.person_id
""")


# create minimal example that gives error