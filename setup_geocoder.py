# set up the GNAF database
import yaml
from whereabouts.GNAFLoader import GNAFLoader

gnafloader = GNAFLoader('gnaf_au')

with open('setup.yml', 'r') as setup_details:
    try:
        details = yaml.safe_load(setup_details)
    except yaml.YAMLError as exc:
        print(exc)

# details of GNAF
db_name = details['gnaf'][0]['db_name']
gnaf_folder = details['gnaf'][2]['folder']
states = details['geocoder'][1]['states']

# path to the auth and the state psv files
gnaf_path = '/home/alex/Desktop/Data/G-NAF Core/G-NAF Core MAY 2023/Standard/GNAF_CORE_subset.parquet'

print("Create geocoder tables")
gnafloader.create_geocoder_tables()
for state in states:
    print(f"Importing date for {state}")
    gnafloader.load_gnaf_data(gnaf_path, state_names=[state])

gnafloader.create_final_address_table()

print("Create standard phrases")
gnafloader.create_phrases()
gnafloader.create_inverted_index()

# trigram phrases
print("Create trigram phrases")
gnafloader.create_phrases(['trigram'])