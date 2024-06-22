# Structure the GNAF core file so that it is easier to load into duckdb
import duckdb 

# location of gnaf core file
data_folder = 'G-NAFCore_MAY24_AUSTRALIA_GDA2020_PSV_107/G-NAF Core/G-NAF Core MAY 2024/Standard'
filename_in = f'{data_folder}/GNAF_CORE.psv'
filename_out = f'{data_folder}/GNAF_CORE_processed.parquet'

# columns required
columns = ', '.join(
    ['ADDRESS_LABEL', 
     'ADDRESS_SITE_NAME', 
     'LOCALITY_NAME',
     'STATE', 
     'POSTCODE', 
     'LONGITUDE', 
     'LATITUDE']
     )

# extract relevant columns
# include an integer identifer
# write to new file
data_extract_query = f"""
COPY 
(
    with gnaf_core_smaller as (
        select 
        row_number() over () ADDRESS_DETAIL_PID,
        {columns}
        from 
        read_csv('{filename_in}', sep='|')
    )
    select * from gnaf_core_smaller
)
TO '{filename_out}'
(FORMAT 'parquet');
"""

# run the query to create the new dataset
duckdb.sql(data_extract_query)