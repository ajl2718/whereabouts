import subprocess 
import requests 

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
        subprocess.run(["curl", "-o", f'whereabouts/models/{model_name}', data_path]) 
    else:
        print(f"Model {model_name} not found")
    