import sys
from .utils import setup_geocoder, remove_database, download

USAGE = """\
Usage: python -m whereabouts <command> [options]

Commands:
  setup_geocoder <config_path>              Build a geocoder database from a config file
  download <db_name>                        Download a pre-built geocoder database
  remove_database <db_name>                 Remove an installed database
  list_databases                            List installed databases
  benchmark <db_name> <csv_path> [options]  Benchmark geocoder against a test set

Benchmark options:
  --how <algorithm>       Matching algorithm: standard, skipphrase, trigram (default: standard)
  --threshold <float>     Similarity threshold (default: 0.5)
  --input-col <name>      CSV column for input addresses (default: input_address)
  --expected-col <name>   CSV column for expected matches (default: best_match)
  --output-csv <path>     Write per-row results to a CSV file
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    command = sys.argv[1]

    if command in ("setup_geocoder", "remove_database", "download") and len(sys.argv) < 3:
        print(USAGE)
        sys.exit(1)

    if command == "setup_geocoder":
        config_path = sys.argv[2]
        setup_geocoder(config_path)
    elif command == "remove_database":
        db_name = sys.argv[2]
        remove_database(db_name)
    elif command == "download":
        db_name = sys.argv[2]
        download(db_name, 'saunteringcat/whereabouts-db')
    elif command == "list_databases":
        from .utils import list_databases
        list_databases()
    elif command == "benchmark":
        if len(sys.argv) < 4:
            print("Usage: python -m whereabouts benchmark <db_name> <csv_path> [--how standard] [--threshold 0.5]")
            sys.exit(1)
        _run_benchmark_cli(sys.argv[2:])
    else:
        print(f'Unknown command: {command}')
        print(USAGE)
        sys.exit(1)


def _run_benchmark_cli(args: list[str]) -> None:
    from .benchmark import run_benchmark

    db_name = args[0]
    csv_path = args[1]
    how = "standard"
    threshold = 0.5
    input_col = "input_address"
    expected_col = "best_match"
    output_csv = None

    i = 2
    while i < len(args):
        if args[i] == "--how" and i + 1 < len(args):
            how = args[i + 1]
            i += 2
        elif args[i] == "--threshold" and i + 1 < len(args):
            threshold = float(args[i + 1])
            i += 2
        elif args[i] == "--input-col" and i + 1 < len(args):
            input_col = args[i + 1]
            i += 2
        elif args[i] == "--expected-col" and i + 1 < len(args):
            expected_col = args[i + 1]
            i += 2
        elif args[i] == "--output-csv" and i + 1 < len(args):
            output_csv = args[i + 1]
            i += 2
        else:
            print(f"Unknown option: {args[i]}")
            sys.exit(1)

    result = run_benchmark(
        db_name=db_name,
        csv_path=csv_path,
        how=how,
        threshold=threshold,
        input_col=input_col,
        expected_col=expected_col,
    )
    print(result.summary())

    if output_csv:
        written = result.to_csv(output_csv)
        print(f"\nResults written to {written}")


if __name__ == "__main__":
    main()