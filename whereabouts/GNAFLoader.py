from pathlib import Path 
import duckdb
from scipy.spatial import KDTree
import pickle

MAKE_ADDRESSES = Path('whereabouts/queries/create_addrtext.sql').read_text()
DO_MATCH_BASIC = Path("whereabouts/queries/geocoder_query_standard.sql").read_text() # threshold 500 - for fast matching

CREATE_GEOCODER_TABLES = Path("whereabouts/queries/create_geocoder_tables.sql").read_text()

CREATE_PHRASES = Path("whereabouts/queries/create_phrases.sql").read_text()
INVERTED_INDEX = Path("whereabouts/queries/phrase_inverted.sql").read_text()
CREATE_INDEXES = Path("whereabouts/queries/create_indexes.sql").read_text()

CREATE_TRIGRAM_PHRASES = Path("whereabouts/queries/create_trigramphrases.sql").read_text()

TRIGRAM_STEP1 = Path("whereabouts/queries/create_trigram_index_step1.sql").read_text()
TRIGRAM_STEP2 = Path("whereabouts/queries/create_trigram_index_step2.sql").read_text()
TRIGRAM_STEP3 = Path("whereabouts/queries/create_trigram_index_step3.sql").read_text()
TRIGRAM_STEP4 = Path("whereabouts/queries/create_trigram_index_step4.sql").read_text()

class GNAFLoader:
    def __init__(self, db_name):
        self.db = db_name
        self.con = duckdb.connect(database=db_name)

    def load_gnaf_data(self, gnaf_path, state_names=['VIC']):
        for state_name in state_names:
            print(f"Loading data for {state_name}")
            query = f"""
            insert into addrtext 
            select 
            ADDRESS_DETAIL_PID addr_id, 
            ADDRESS_LABEL address_label,
            ADDRESS_SITE_NAME address_site_name,
            LOCALITY_NAME locality_name,
            POSTCODE postcode,
            STATE state,
            LATITUDE latitude,
            LONGITUDE 
            from
            read_csv_auto('{gnaf_path}', delim='|')
            where state='{state_name}'
            """
            self.con.execute(query)

    def create_final_address_table(self):
        self.con.execute(MAKE_ADDRESSES)
        
    def create_geocoder_tables(self):
        print("Creating geocoder tables...")
      #  self.con.execute(CREATE_TABLES)
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
            print("Add row number to phrase inverted index...")
            self.con.execute(TRIGRAM_STEP1)
            print("Creating trigram inverted phrases. Step 1...")
            for n in range(100):
                print(f'Creating trigram phrases for chunk {n}...')
                self.con.execute(TRIGRAM_STEP2, [n])
            print("Creating trigram inverted phrases. Step 2...")
            self.con.execute(TRIGRAM_STEP3)
            print("Creating trigram inverted phrases. Step 3...")
            for n in range(100):
                print(f'Creating trigram phrases for chunk {n}...')
                self.con.execute(TRIGRAM_STEP4, [n])

    def create_inverted_index(self, phrases=['standard']):
        # how to do this in a way that prevents memory issues
        print('Creating inverted index...')
        # create inverted index
        if 'standard' in phrases:
            self.con.execute(INVERTED_INDEX)
            self.con.execute(CREATE_INDEXES)

    def clean_database(self, phrases):
        """
        Once geocoder tables have been created, remove unncessary tables from DB
        to clear up space. Note that DuckDB currently does not free up the space
        so the database has to be exported with tables and then loaded back again
        """
        
        self.con.execute("""
        drop table addrtext;
        drop table skipphrase;
        drop table skipphraseinverted;
        """)

        if 'standard' in phrases:
            self.con.execute("""
            drop table phrase;
            """)
        if 'trigram' in phrases:
            self.con.execute("""
            drop table trigramphrase;
            drop table tg_distinct;
            drop table trigramphraseinverted;
            drop table trigramphraseinverted2;
            """)

    def export_database(self, db_path):
        """
        Export the database to the specified folder

        Args
        ----
        db_path (str): name of folder to export db to
        """
        self.con.execute(f"export database '{db_path}' (format parquet);")

    def import_database(self, db_path):
        """
        Import database from specified folders

        Args
        -----
        db_path (str): path where database files and queries are located
        """
        self.con.execute(f"import database '{db_path}'")

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