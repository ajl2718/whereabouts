from whereabouts.AddressLoader import AddressLoader
from whereabouts.utils import setup_geocoder
import yaml 
import numpy as np

# test functions for creating the address db
#def test_address_loader():
#    db_name = 'testdb.db'
#    addressloader = AddressLoader(db_name)

def test_config_loader():
    config_file = 'tests/setup_example.yml'

    with open(config_file, 'r') as setup_details:
        details = yaml.safe_load(setup_details)

    assert details['data']['db_name'] == 'db_test'
    assert details['data']['folder'] == 'geodb'
    assert details['data']['filepath'] == 'tests/test_data3056.parquet'

    assert details['geocoder']['states'] == [] 
    assert details['geocoder']['matchers'] == ['standard', 'trigram']

    assert details['schema']['addr_id'] == 'row_num'
    assert details['schema']['address_label'] == 'ADDRESS_LABEL'
    assert details['schema']['address_site_name'] == 'ADDRESS_SITE_NAME'
    assert details['schema']['locality_name'] == 'LOCALITY_NAME'
    assert details['schema']['postcode'] == 'POSTCODE'
    assert details['schema']['state'] == 'STATE'
    assert details['schema']['latitude'] == 'LATITUDE'
    assert details['schema']['longitude'] == 'LONGITUDE'

def test_db_creation():
    db_name = 'db_test.db'
    addressloader = AddressLoader(db_name)
    assert addressloader.con.execute('show tables;').df().shape[0] == 0

def test_table_creation():
    db_name = 'db_test.db'
    table_names = np.array(['addrtext', 
                            'numbers', 
                            'phrase', 
                            'phraseinverted', 
                            'skipphrase',
                            'skipphraseinverted', 
                            'trigramphrase', 
                            'trigramphraseinverted'], 
                            dtype='object')
    
    addressloader = AddressLoader(db_name)
    addressloader.create_geocoder_tables()
    assert addressloader.con.execute('show tables;').df().shape[0] == 8
    assert (addressloader.con.execute('show tables;').df().name.values == table_names).all()

def test_load_data():
    db_name = 'db_test.db'
    addressloader = AddressLoader(db_name)
    config_file = 'tests/setup_example.yml'
    with open(config_file, 'r') as setup_details:
        details = yaml.safe_load(setup_details)
    addressloader.load_data(details, state_names=[])
    assert addressloader.con.execute('select * from addrtext').df().shape[0] == 18687
    assert addressloader.con.execute('select * from addrtext').df().shape[1] == 8

def test_create_final_address_table():
    db_name = 'db_test.db'
    colnames_full_addresses = np.array(['addr_id', 
                                        'addr', 
                                        'numeric_tokens', 
                                        'ADDRESS_LABEL', 
                                        'suburb',
                                        'POSTCODE', 
                                        'LATITUDE', 
                                        'LONGITUDE'])
    
    addressloader = AddressLoader(db_name)
    addressloader.create_final_address_table()
    assert addressloader.con.execute('show tables;').df().shape[0]
    assert addressloader.con.execute('select * from addrtext_with_detail').df().shape[0] == 18687
    assert addressloader.con.execute('select * from addrtext_with_detail').df().shape[1] == 8
    assert (addressloader.con.execute('select * from addrtext_with_detail').df().columns == colnames_full_addresses).all()

def test_create_standard_phrases():
    db_name = 'db_test.db'
    addressloader = AddressLoader(db_name)
    #addressloader.create_phrases()

# test create inverted index
# test create trigram phrases
# test create trigram index
# test clean database
# test export database
# test import database