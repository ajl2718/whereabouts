import yaml
import os
from whereabouts.AddressLoader import AddressLoader

with open('setup.yml', 'r') as setup_details:
    try:
        details = yaml.safe_load(setup_details)
    except yaml.YAMLError as exc:
        print(exc)

db_name = details['data']['db_name']
db_folder = details['data']['folder']
data_path = details['data']['filepath']

states = details['geocoder']['states']
matchers = details['geocoder']['matchers']

addressloader = AddressLoader(db_name)

print("Create geocoder tables")
addressloader.create_geocoder_tables()
for state in states:
    addressloader.load_data('setup.yml', state_names=[state])

addressloader.create_final_address_table()

if 'standard' in matchers:
    print("Create standard phrases")
    addressloader.create_phrases()
    addressloader.create_inverted_index()

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
addressloader.export_database('gnaf_geocoder')

# delete the old db file
os.remove(db_name)

print("Importing database")
addressloader = AddressLoader(db_name)
addressloader.import_database('gnaf_geocoder')