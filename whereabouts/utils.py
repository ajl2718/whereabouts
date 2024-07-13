import yaml
import os
from .AddressLoader import AddressLoader
import importlib.resources
from time import time
import joblib
from huggingface_hub import hf_hub_download

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
    print(f'Created reference database in {t2-t1}s.')

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
    all_dbs = [filename[:-3] for filename in os.listdir(path_to_models) if filename.endswith('.db')]
    print('The following reference databases are installed')
    for db in all_dbs:
        print(db)

def download(filename, repo_id):
    """
    Download a duckdb database from the huggingface hub

    Args
    ----
    filename (str): the name of the file to download
    repo_id (str): huggingface repo ID
    """

    try:        
        model = joblib.load(
            hf_hub_download(repo_id=repo_id, filename=f"{filename}.joblib")
        )

        output_filename = f'{filename.split('.')[0]}.db'
        path_to_model = importlib.resources.files('whereabouts') / 'models'
        path_to_model = str(path_to_model)

        with open(f'{path_to_model}/{output_filename}', 'wb') as f:
            f.write(model)
        try:
            os.remove(f'{filename}.joblib')
        except:
            pass
    except:
        print(f"Could not download {filename}")

def convert_db(filename):
    """
    Convert duckdb database to joblib format for huggingface upload

    Args
    ----
    filename (str): name of the file to upload
    """
    try:
        output_filename = f'{filename[:-3]}.joblib'
        with open(filename, 'rb') as f:
            data = f.read()
        joblib.dump(data, output_filename)
    except:
        print(f"Could not convert duckdb database to joblib")