# Create all tables and population them with GNAF data
# Also create the table in the format that is required by whereabouts
# Alex Lee
# 17 05 24
import os
import polars as pl 
import numpy as np

def drop_all_tables(db):
    table_names = db.execute('show tables;').df().name.values
    for table_name in table_names:
        if 'view' in table_name: # this is horrible
            db.execute(f'drop view {table_name}')
        else:
            db.execute(f'drop table {table_name}')

def create_all_tables(db, create_tables_file):
    with open(create_tables_file, 'r') as f:
        standard_query = f.read()
    db.execute(standard_query)

def load_state_data(db, folder, state_name):
    # all standard filenames for a given state
    filenames_state = [filename for filename in os.listdir(folder) if state_name in filename]
    # load each of the files into the corresponding table
    for filename in filenames_state:
        table_name = '_'.join(filename.split('_')[1:-1])
        print(f"Loading data for table: {table_name}")
        filename = f'{folder}/{state_name}_{table_name}_psv.psv'
        db.execute(f"insert into {table_name} select * from read_csv('{filename}', delim='|')")

def load_auth_data(db, folder):
    filenames_auth = os.listdir(folder)
    for filename in filenames_auth:
        table_name = '_'.join(filename.split('_')[2:-1])
        filename = f'{folder}/Authority_Code_{table_name}_psv.psv'
        db.execute(f"insert into {table_name} select * from read_csv('{filename}', delim='|')")

def create_view(db, view_file):
    with open(view_file, 'r') as f:
        view_query = f.read()
    db.execute(view_query)

def create_full_address_table(db, query_file):
    with open(query_file, 'r') as f:
        full_address_query = f.read()
    db.execute(full_address_query)


def gnaf_schema_valid(columns_in, columns_compare):
    """
    Check that the columns in the schema match

    Args
    ----
    columns_in (list of str): columns in the input
    columns_compare (list of str): columns to compare with

    Return
    ------
    valid (bool): True if columns are equal, False otherwise
    """
    return set(columns_compare).issubset(set(columns_in))

def process_gnaf_core(filename_in, filename_out):
    """
    Load the GNAF CORE (e.g., from https://geoscape.com.au/data/g-naf-core/)
    and create a parquet file that is suitable for use in whereabouts

    Basically reads a subset of the columns and produces an integer for the
    row number.

    Args
    ----
    filename_in (str): path of gnaf core to read process
    filename_out (str): path of processed file to write (should be parquet)
    """
    try:
        df = pl.scan_csv(filename_in, separator='|')
        columns = ['ADDRESS_LABEL', 
               'ADDRESS_SITE_NAME', 
               'BUILDING_NAME', 
               'LOCALITY_NAME', 
               'STATE', 
               'POSTCODE', 
               'LATITUDE', 
               'LONGITUDE']
        if gnaf_schema_valid(df.columns, columns):
            df2 = df.select(pl.col(columns)).collect()
            df2 = df2.with_columns(
                row_num=np.arange(df2.shape[0])
            )
            df2.write_parquet(filename_out)
            return True
        else:
            print("Schema invalid")
            return False
    except:
        print(f'Could not load filename {filename_in}')
        return False