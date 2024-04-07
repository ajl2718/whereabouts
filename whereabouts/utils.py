import subprocess 
import requests 
import yaml
import os
from .AddressLoader import AddressLoader
import importlib.resources
from time import time

def get_unmatched(results, threshold):
    """
    Given results (outputs from Matcher), filter out those that are correctly matched and
    those that are not.
    """
    # unmatched are those below threshold in similarity value
    # get the id values of the unmatched (so we can correctly order at the end)
    matched, unmatched = [], []
    for result in results:
        if result['similarity'] >= threshold:
            matched.append(result)
        else:
            unmatched.append(result)
    return matched, unmatched

def order_matches(matches):
    """
    Given a list of results order by the address_id value
    """
    matches_sorted = sorted(matches, key=lambda k: k['address_id']) 
    return matches_sorted


def download(model_name):
    """
    Download a database for geocoding addresses in a particular part of the world

    Args
    ----
    model_name (str): name of database to download
    """
    # URL of location of metadata for all models
    base_url = "https://raw.githubusercontent.com/ajl2718/whereabouts/main/model_metadata"
    metadata_url = f"{base_url}/all_models.json"
    # get all the model names from the reference json file
    all_models = requests.get(metadata_url).json()['models']
    if model_name in all_models:
        model_metadata_url = f'{base_url}/{model_name}.json'
        model_metadata = requests.get(model_metadata_url).json()
        print(f"Downloading data for {model_name}")
        data_path = model_metadata['download_url']
        subprocess.run(["curl", "-o", f'whereabouts/models/{model_name}.db', data_path]) 
    else:
        print(f"Model {model_name} not found")


def setup_geocoder(config_file):
    """
    Given a configuration file containing details of the reference data and the type of
    geocoding algorithm to use, setup the database tables for doing geocoding with the 
    reference data

    Args
    ----
    configuration (str): path to the .yml file with the configuration details
    """
    # open the config file
    with open(config_file, 'r') as setup_details:
        try:
            details = yaml.safe_load(setup_details)
        except yaml.YAMLError as exc:
            print(exc)

    try:            
        # get all the info from the config file
        db_name = details['data']['db_name']
        db_folder = details['data']['folder']
        states = details['geocoder']['states']
        matchers = details['geocoder']['matchers']
    except:
        print("Some details missing from configuration file")


    t1 = time()
    print("Creating reference database")
    # create the database
    db_name += '.db'
    addressloader = AddressLoader(db_name)
    
    print("Create geocoder tables")
    addressloader.create_geocoder_tables()
    if states:
        for state in states:
            addressloader.load_data(details, state_names=[state])
    else:
        addressloader.load_data(details, state_names=[])

    addressloader.create_final_address_table()

    if 'standard' in matchers:
        print("Create standard phrases")
        addressloader.create_phrases()
        addressloader.create_inverted_index()

    if 'skipphrase' in matchers:
        print("Create skipphrases")
        addressloader.create_phrases(['skipphrase'])
        addressloader.create_inverted_index(['skipphrase'])

    # trigram phrases
    if 'trigram' in matchers:
        print("Create trigram phrases")
        addressloader.create_phrases(['trigram'])

    print("Cleaning database")
    if 'trigram' in matchers:
        addressloader.clean_database(phrases=['standard', 'trigram'])
    else:
        addressloader.clean_database(phrases=['standard'])

    print("Exporting database")
    addressloader.export_database(db_folder)

    # delete the old db file
    os.remove(db_name)

    print("Importing database")
    del(addressloader)
    path_to_model = importlib.resources.files('whereabouts') / 'models'
    path_to_model = str(path_to_model)

    addressloader = AddressLoader(f'{path_to_model}/{db_name}')
    addressloader.import_database(db_folder)
    
    # remove all files created in export of db
    for filename in os.listdir(db_folder):
        os.remove(f'{db_folder}/{filename}')
    os.rmdir(db_folder)
    t2 = time()
    printf(f'Created reference database in {t2-t1}s.')

def remove_database(db_name):
    """
    Remove a database from the folder of databases

    db_name (str): title of database (without the extension of folder path)
    """
    path_to_model = importlib.resources.files('whereabouts') / 'models'
    path_to_model = str(path_to_model)
    all_dbs = os.listdir(path_to_model)
    if f'{db_name}.db' in all_dbs:
        os.remove(f'{path_to_model}/{db_name}.db')
    else:
        print(f"Could not database with name {db_name}")

def list_databases():
    """
    List all the reference databases that have been installed
    """
    path_to_models = importlib.resources.files('whereabouts') / 'models'
    path_to_models = str(path_to_models)
    all_dbs = [filename[:-4] for filename in os.listdir(path_to_models) if filename.endswith('.db')]
    print('The following reference databases are installed')
    for db in all_dbs:
        print(db)
