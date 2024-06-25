import sys
from .utils import setup_geocoder, remove_database, download

def main():
    if len(sys.argv) < 3:
        print("Usage: python -m whereabouts setup_geocoder <config_path> or python -m whereabouts download <db_name>")
        sys.exit(1)

    command = sys.argv[1]
    if command == "setup_geocoder":
        config_path = sys.argv[2]
        setup_geocoder(config_path)
    if command == "remove_database":
        db_name = sys.argv[2]
        remove_database(db_name)
    if command == "download":
        db_name = sys.argv[2]
        download(db_name, 'saunteringcat/whereabouts-db')
    else:
        print(f'Unknown command: {command}')

if __name__ == "__main__":
    main()