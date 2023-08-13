create table addrtext as 
select * from
read_parquet('/home/alex/Desktop/Data/G-NAF Core/G-NAF Core MAY 2023/Standard/GNAF_CORE_subset.parquet')
where state='VIC'