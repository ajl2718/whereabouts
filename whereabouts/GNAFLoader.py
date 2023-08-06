from pathlib import Path 
import duckdb
from scipy.spatial import KDTree
import pickle
import os

CREATE_TABLES = Path('queries/create_tables_duckdb.sql').read_text()
ADDRESS_VIEW = Path('queries/address_view.sql').read_text()
MAKE_ADDRESSES = Path('queries/make_addresses.sql').read_text()
MAKE_ADDRESSES = Path('queries/create_addrtext.sql').read_text()
MAKE_ADDRESSES2 = Path('queries/create_addrtext2.sql').read_text()
MAKE_ADDRESSES3 = Path('queries/create_addrtext3.sql').read_text()
MAKE_ADDRESSES4 = Path('queries/create_addrtext4.sql').read_text()
DO_MATCH_BASIC = Path("queries/geocoder_query_standard.sql").read_text() # threshold 500 - for fast matching

CREATE_GEOCODER_TABLES = Path("queries/create_geocoder_tables.sql").read_text()

CREATE_PHRASES = Path("queries/create_phrases2.sql").read_text()
INVERTED_INDEX = Path("queries/phrase_inverted.sql").read_text()
CREATE_INDEXES = Path("queries/create_indexes.sql").read_text()

CREATE_TRIGRAM_PHRASES = Path("queries/create_trigramphrases.sql").read_text()

class GNAFLoader:
    def __init__(self, db_name):
        self.db = db_name
        self.con = duckdb.connect(database=db_name)

    def load_data_subset_standard(self, gnaf_path, state_name='VIC'):
        error_tables = [] # any tables that could not be loading

        all_files_standard = os.listdir(f'{gnaf_path}/Standard')
        all_files_state = [filename for filename in all_files_standard if filename.startswith(state_name)]
        
        for filename in all_files_state:
            # the table name from the filename (removing irrelevant strings)
            table_name = '_'.join(filename.split('_')[1:])[:-8]
            full_path = f'{gnaf_path}/Standard/{filename}'
            print(f'Loading state-specific data into {table_name}')
            try:
                self.con.execute(f'insert into {table_name} select * from read_csv_auto("{full_path}")')
            except:
                error_tables.append(table_name)
                print(f"Could not load data for {table_name}")
                next

        if error_tables:
            print(f"Failed to load data from tables: {' '.join(error_tables)}")

    def load_data_authority(self, gnaf_path):
        error_tables = [] # any tables that could not be loading

        # load the AUT tables (these are required independent of the state)
        all_files_aut = os.listdir(f'{gnaf_path}/Authority Code')

        for filename in all_files_aut:
            table_name = '_'.join(filename.split('_')[2:-1])
            full_path = f'{gnaf_path}/Authority Code/{filename}'
            print(f'Loading authority code tables for {table_name}')
            try:
                self.con.execute(f'insert into {table_name} select * from read_csv_auto("{full_path}", header=True, delim="|")')
            except:
                error_tables.append(table_name)
                print(f"Could not load data from {table_name}")
            next

        if error_tables:
            print(f"Failed to load data from tables: {' '.join(error_tables)}")

    def load_data(self, gnaf_path, state_names=['VIC']):     
        # load authority code tables
        print("Loading authority code tables")
        self.load_data_authority(gnaf_path)
           
        # load data in tables
        print("Loading data into database tables")
        for state_name in state_names:
            print(f'Loading data for state: {state_name}')
            self.load_data_subset_standard(gnaf_path, state_name)

    def create_address_view(self):
        self.con.execute(ADDRESS_VIEW)

    def create_addresses(self, state="VIC"):
        print(f'Creating the address table for {state}...')
        self.con.execute(MAKE_ADDRESSES, [state])

    # get around the memory issues?
    def create_addresses_in_chunks(self, state="VIC"):
        print(f"Creating address table for {state}")
        for n in range(0, 10):
            print(f"Chunk: {n}")
            self.con.execute(MAKE_ADDRESSES2, [state, n])

    def create_final_address_table(self):
        self.con.execute(MAKE_ADDRESSES3)
        self.con.execute(MAKE_ADDRESSES4)
        
    def create_geocoder_tables(self):
        print("Creating geocoder tables...")
        self.con.execute(CREATE_TABLES)
        self.con.execute(CREATE_GEOCODER_TABLES)
        
    def create_phrases(self, phrases=['standard']):
        if 'standard' in phrases:
            print('Creating phrases...')
            # create the phrases in chunks to prevent memory errors
            # this still takes a looooong time
            for n in range(100): # change based on size of db
                print(f'Creating phrases for chunk {n}...')
                self.con.execute(CREATE_PHRASES, [n])
        if 'trigram' in phrases:
            print("Creating trigram phrases...")
            for n in range(100):
                print(f'Creating trigram phrases for chunk {n}...')
                self.con.execute(CREATE_TRIGRAM_PHRASES, [n])

    def create_inverted_index(self, phrases=['standard']):
        # how to do this in a way that prevents memory issues
        print('Creating inverted index...')
        # create inverted index
        if 'standard' in phrases:
            self.con.execute(INVERTED_INDEX)
            self.con.execute(CREATE_INDEXES)

    def create_kdtree(self, tree_path):
        """
        Create a KD-Tree data structure from the reference data in GNAF

        Args
        ----
        tree_path (str): where to put the data structure to

        """
        
        print("Creating KD-Tree for reverse geocoding...")
        
        # extract address texts and lat, long coords from db
        self.reference_data = self.con.execute("""
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

        # create kdtree
        tree = KDTree(self.reference_data[['latitude', 'longitude']].values)
        pickle.dump(tree, open(tree_path, 'wb'))