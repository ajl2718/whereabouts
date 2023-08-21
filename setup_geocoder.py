# set up the GNAF database
import yaml
from whereabouts.GNAFLoader import GNAFLoader

with open('setup.yml', 'r') as setup_details:
    try:
        details = yaml.safe_load(setup_details)
    except yaml.YAMLError as exc:
        print(exc)

# details of GNAF
db_name = details['gnaf'][0]['db_name']
gnaf_folder = details['gnaf'][2]['folder']
gnaf_path = details['gnaf'][3]['filepath']
states = details['geocoder'][1]['states']
matchers = details['geocoder'][0]['matchers']

gnafloader = GNAFLoader(db_name)

print("Create geocoder tables")
gnafloader.create_geocoder_tables()
for state in states:
    gnafloader.load_gnaf_data(gnaf_path, state_names=[state])

gnafloader.create_final_address_table()

if 'standard' in matchers:
    print("Create standard phrases")
    gnafloader.create_phrases()
    gnafloader.create_inverted_index()

# trigram phrases
if 'trigram' in matchers:
    print("Create trigram phrases")
    gnafloader.create_phrases(['trigram'])

print("Cleaning database")
gnafloader.clean_database(phrases=['standard'])

print("Exporting database")
gnafloader.export_database('gnaf_geocoder')

#print("Importing database")
#gnafloader.import_database('gnaf_geocoder')