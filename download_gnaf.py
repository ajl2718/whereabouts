import requests
import shutil
from tqdm.auto import tqdm
import yaml
import os
import zipfile
from lxml import html

# load config file to get name of DB
# and URL of GNAF
with open('gnaf_details.yml', 'r') as setup_details:
    try:
        details = yaml.safe_load(setup_details)
    except yaml.YAMLError as exc:
        print(exc)

# details of GNAF
db_name = details['gnaf']['db_name']
gnaf_folder = details['gnaf']['folder']

# create the data folder if not already there
try:
    os.mkdir(gnaf_folder)
except OSError:
    print (f"Folder {gnaf_folder} already exists")
else:
    print (f"Successfully created the folder {gnaf_folder}")

# find the url of the zip where latest GNAF is located
url_gnaf_main = 'https://data.gov.au/data/dataset/geocoded-national-address-file-g-naf'
page = requests.get(url_gnaf_main)
tree = html.fromstring(page.text)
url_path = './/div[@class="dropdown btn-group"]/ul/li/a[@target="_blank"]/@href'

# get the zip file corresponding to GDA2020 GNAF
url_gnaf_latest = [filename for filename in tree.xpath(url_path) if 'gda2020' in filename][0]

# download the GNAF
print(f"Downloading most recent GNAF: {url_gnaf_latest}")
with requests.get(url_gnaf_latest, stream=True) as r:    
    total_length = int(r.headers.get("Content-Length"))
    with tqdm.wrapattr(r.raw, "read", total=total_length, desc="") as raw:
        with open(f"{gnaf_folder}/{os.path.basename(r.url)}", 'wb') as output:
            shutil.copyfileobj(raw, output)

# extract the data
print("Extracting data...")
with zipfile.ZipFile(f'{gnaf_folder}/{os.path.basename(url_gnaf_latest)}', 'r') as zip_ref:
    zip_ref.extractall(gnaf_folder)

# remove the zip file
os.remove(f'{gnaf_folder}/{os.path.basename(url_gnaf_latest)}')

print("Successfully downloaded and extracted latest GNAF")