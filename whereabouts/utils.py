from __future__ import annotations

import os
import importlib.resources
from time import time

import joblib
import requests
import yaml
from tqdm import tqdm

from .AddressLoader import AddressLoader

def get_unmatched(results: list[dict], threshold: float) -> tuple[list[dict], list[dict]]:
    """
    Filter results into matched and unmatched based on a similarity threshold.

    Parameters
    ----------
    results : list of dict
        A list of dictionaries where each dictionary contains a 'similarity' key.
    threshold : float
        The similarity threshold to determine if a result is matched.

    Returns
    -------
    matched : list of dict
        Results with similarity >= threshold.
    unmatched : list of dict
        Results with similarity < threshold.
    """
    matched = []
    unmatched = []
    for result in results:
        if result['similarity'] >= threshold:
            matched.append(result)
        else:
            unmatched.append(result)

    return matched, unmatched


def order_matches(matches: list[dict]) -> list[dict]:
    """
    Given a list of results, order by the address_id value.

    Parameters
    ----------
    matches : list of dict
        Results of matcher method.

    Returns
    -------
    matches_sorted : list of dict
        The ordered list of addresses.
    """
    # sort by id ascending and similarity descending (for case where multiple matches per id)
    matches_sorted = sorted(matches, key=lambda k: (k['address_id'], -k['similarity'])) 
    return matches_sorted

def filter_to_single_response(matches: list[dict]) -> list[dict]:
    """
    Filter a list of matches to keep only the highest similarity result per address_id.

    Parameters
    ----------
    matches : list of dict
        A list of dicts ordered by address_id (ascending) and similarity (descending).

    Returns
    -------
    matches_single_address_id : list of dict
        List of addresses filtered to the max similarity value for each address_id.
    """
    matches_single_address_id = []
    address_ids = []
    for match in matches:
        if match['address_id'] in address_ids:
            pass 
        else:
            matches_single_address_id.append(match)
            address_ids.append(match['address_id'])
    return matches_single_address_id

def setup_geocoder(config_file: str) -> None:
    """
    Set up the database tables for geocoding using a configuration file.

    Parameters
    ----------
    config_file : str
        Path to the .yml file with the configuration details.
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
    except (KeyError, TypeError) as e:
        print(f"Some details missing from configuration file: {e}")
        return


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
    #    addressloader.create_inverted_index()

    print("Cleaning database")
    if 'trigram' in matchers:
        addressloader.clean_database(phrases=['standard', 'trigram'])
    else:
        addressloader.clean_database(phrases=['standard'])

    print("Exporting database")
    addressloader.export_database(db_folder)

    # delete the old db file
    try:
        os.remove(db_name)
    except OSError as e:
        print(f"Could not remove database {db_name}: {e}")

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

def remove_database(db_name: str) -> None:
    """
    Remove a database from the folder of databases.

    Parameters
    ----------
    db_name : str
        Name of the database.
    """
    path_to_model = importlib.resources.files('whereabouts') / 'models'
    path_to_model = str(path_to_model)
    all_dbs = os.listdir(path_to_model)
    if f'{db_name}.db' in all_dbs:
        os.remove(f'{path_to_model}/{db_name}.db')
    else:
        print(f"Could not find database with name {db_name}")

def list_databases() -> None:
    """
    List all the reference databases that have been installed.
    """
    path_to_models = importlib.resources.files('whereabouts') / 'models'
    path_to_models = str(path_to_models)
    all_dbs = [filename[:-3] for filename in os.listdir(path_to_models) if filename.endswith('.db')]
    print('The following reference databases are installed')
    for db in all_dbs:
        print(db)

def download(db_name: str, repo_id: str) -> None:
    """
    Download a DuckDB database from the Hugging Face Hub.

    Parameters
    ----------
    db_name : str
        The name of the database to download.
    repo_id : str
        Hugging Face repo ID.
    """
    try:    
        # the path to download the file from
        filename = f"{db_name.split('.')[0]}.joblib"
        url = f'https://huggingface.co/{repo_id}/resolve/main/{filename}'
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))

        # define the path and filename for the output file
        output_filename = f"{db_name}.db"
        path_to_model = importlib.resources.files('whereabouts') / 'models'
        path_to_model = str(path_to_model)
        
        # write the file in chunks so that we can see the progress bar update
        # write as joblib
        with open(f'{filename}', 'wb') as file, tqdm(desc=filename, total=total_size, unit='B', unit_scale=True, unit_divisor=1024) as bar:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    file.write(chunk)
                    bar.update(len(chunk))    
        # load the joblib file and convert to duckdb
        joblib_file = joblib.load(f'{filename}', 'rb')
        with open(f'{path_to_model}/{output_filename}', 'wb') as f:
            f.write(joblib_file)
        # delete the .joblib file
        os.remove(f'{filename}')
    except Exception as e:
        print(f"Could not download {db_name}: {e}")

def convert_db(filename: str) -> None:
    """
    Convert a DuckDB database to joblib format for Hugging Face upload.

    Parameters
    ----------
    filename : str
        Name of the DuckDB file to convert.
    """
    try:
        output_filename = os.path.join(os.getcwd(), f"{filename[:-3]}.joblib")
        input_filename = os.path.join(os.getcwd(), f"{filename}")
        with open(input_filename, 'rb') as f:
            data = f.read()
        joblib.dump(data, output_filename)
        print(f"Converted '{input_filename}' to '{output_filename}' successfully.")
    except Exception as e:
        print(f"Could not convert duckdb database to joblib: {e}")

def list_overlap(list1: list[str], 
                 list2: list[str], 
                 threshold: float) -> bool:
    """
    Compare the number of numeric tokens common to input and candidate addresses.

    Parameters
    ----------
    list1 : list of str
        Numeric tokens in one address.
    list2 : list of str
        Numeric tokens in another address.
    threshold : float
        The threshold that the intersection must satisfy.

    Returns
    -------
    bool
        True if the intersection of the number of numeric tokens is above threshold.
    """
    if list1 is None: # in case where there are no numeric tokens in input
        return False
    if list2:
        intersection = len(set(list1).intersection(set(list2))) / len(list1)
        if intersection >= threshold:
            return True
        else:
            return False
    else:
        return False
    
def numeric_overlap(input_numerics: list[str],
                    candidate_numerics: list[str]) -> float:
    """
    Compute the fraction of numeric tokens in the input that appear in the candidate.

    Parameters
    ----------
    input_numerics : list of str
        Numeric tokens from the input address.
    candidate_numerics : list of str
        Numeric tokens from the candidate address.

    Returns
    -------
    float
        Fraction of input numeric tokens found in the candidate.
    """
    num_overlap = len(set(input_numerics).intersection(set(candidate_numerics)))
    fraction_overlap = num_overlap / len(set(input_numerics))
    return fraction_overlap

def ngram_jaccard(input_address: str, candidate_address: str) -> float:
    """
    Compute the Jaccard similarity between input and candidate address using n-grams.

    Parameters
    ----------
    input_address : str
        The address to be compared.
    candidate_address : str
        The candidate address to compare the input address against.

    Returns
    -------
    jaccard_distance : float
        The Jaccard similarity (based on unigrams and bigrams) between the two addresses.
    """
    # bigrams
    bigrams_input = [input_address[n:n+2] for n in range(0, len(input_address) - 1)]
    bigrams_candidate = [candidate_address[n:n+2] for n in range(0, len(candidate_address) - 1)]
    # unigrams
    unigrams_input = [input_address[n:n+1] for n in range(0, len(input_address))]
    unigrams_candidate = [candidate_address[n:n+1] for n in range(0, len(candidate_address))]
    ngrams_input_set = set(bigrams_input).union(unigrams_input)
    ngrams_candidate_set = set(bigrams_candidate).union(unigrams_candidate)
    jaccard_distance = len(ngrams_input_set.intersection(ngrams_candidate_set)) / len(ngrams_input_set.union(ngrams_candidate_set))
    return jaccard_distance

