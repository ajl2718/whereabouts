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

# folder where data is located
# gnaf_folders = os.listdir(f'{gnaf_folder}/G-NAF')
# data_folder = [folder_name for folder_name in gnaf_folders if 'G-NAF' in folder_name][0]

# path to the auth and the state psv files
gnaf_path = '/home/alex/Desktop/Data/GNAF/G-NAF/G-NAF MAY 2023'
gnaf_path = '/home/alex/Desktop/Data/G-NAF Core/G-NAF Core MAY 2023/Standard/GNAF_CORE_subset.parquet'
gnafloader.create_geocoder_tables()
gnafloader.load_gnaf_data(gnaf_path, state_names=['SA'])
##gnafloader.load_data(gnaf_path, states)
#gnafloader.create_address_view()

##for state in states:
#    gnafloader.create_addresses_in_chunks(state)
#gnafloader.create_addresses()
gnafloader.create_final_address_table()

#for state in states:
 #   gnafloader.create_addresses(state)

gnafloader.create_phrases()
gnafloader.create_inverted_index()

# trigram phrases
gnafloader.create_phrases(['trigram'])

# drop phrase table since no longer needed
