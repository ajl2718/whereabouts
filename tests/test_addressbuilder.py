from whereabouts.AddressLoader import AddressLoader
from whereabouts.utils import setup_geocoder
import yaml 
import numpy as np
import pytest
import os


@pytest.mark.order(1)
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

@pytest.mark.order(2)
def test_db_creation():
    db_name = 'db_test.db'
    addressloader = AddressLoader(db_name)
    assert addressloader.con.execute('show tables;').df().shape[0] == 0

@pytest.mark.order(3)
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

@pytest.mark.order(4)
def test_load_data():
    db_name = 'db_test.db'
    addressloader = AddressLoader(db_name)
    config_file = 'tests/setup_example.yml'
    with open(config_file, 'r') as setup_details:
        details = yaml.safe_load(setup_details)
    addressloader.load_data(details, state_names=[])
    assert addressloader.con.execute('select * from addrtext').df().shape[0] == 18687
    assert addressloader.con.execute('select * from addrtext').df().shape[1] == 8

@pytest.mark.order(5)
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


@pytest.mark.order(6)
def test_create_standard_phrases():
    db_name = 'db_test.db'
    addressloader = AddressLoader(db_name)
    addressloader.create_phrases()
    assert addressloader.con.execute('select count(*) from phrase').df().values[0, 0] == 114827
    assert addressloader.con.execute('select * from phrase limit 3;').df().shape[1] == 2

# test create inverted index
def test_create_inverted_index():
    db_name = 'db_test.db'
    addressloader = AddressLoader(db_name)
    addressloader.create_inverted_index()
    assert addressloader.con.execute('select * from phraseinverted').df().shape[1] == 3
    assert addressloader.con.execute('select count(*) from phraseinverted').df().values[0, 0] == 17149

# test clean database
def test_clean_database():
    db_name = 'db_test.db'
    addressloader = AddressLoader(db_name)
    addressloader.clean_database(phrases=['standard'])
    # check that only a few of the tables remain
    assert addressloader.con.execute('show tables;').df().shape[0] == 7

# test export database
def test_export_db():
    db_name = 'db_test.db'
    addressloader = AddressLoader(db_name)
    addressloader.export_database('db_test')
    assert 'db_test' in os.listdir('.')
    os.remove('db_test.db')
    for filename in os.listdir('db_test'):
        os.remove(f'db_test/{filename}')
    os.rmdir('db_test')