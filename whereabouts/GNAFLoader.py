from __future__ import annotations

import duckdb

from .AddressLoader import AddressLoader
from .constants import MAX_PHRASE_CHUNKS
from .matching_queries.addrtext_with_detail import build_address_detail_pipeline
from .matching_queries.database import cleanup_pipeline, inverted_index_pipeline
from .matching_queries.phrases import build_phrase_pipeline


class GNAFLoader(AddressLoader):
    """Legacy G-NAF interface backed by the shared database-building pipelines."""

    def __init__(self, db_name: str) -> None:
        self.db = db_name
        self.con = duckdb.connect(database=db_name)

    def load_gnaf_data(
        self, gnaf_path: str, state_names: list[str] | None = None
    ) -> None:
        details = {
            "schema": {
                "addr_id": "ADDRESS_DETAIL_PID",
                "full_address": "ADDRESS_LABEL",
                "address_site_name": "ADDRESS_SITE_NAME",
                "locality_name": "LOCALITY_NAME",
                "postcode": "POSTCODE",
                "state": "STATE",
                "latitude": "LATITUDE",
                "longitude": "LONGITUDE",
            },
            "data": {"filepath": gnaf_path, "sep": "|", "format": "csv"},
        }
        states = state_names if state_names is not None else ["VIC"]
        for state in states:
            self.load_data(details, [state])

    def create_final_address_table(self) -> None:
        build_address_detail_pipeline(self.con, include_state=False).execute_as_table(
            "addrtext_with_detail"
        )

    def create_phrases(self, phrases: list[str] | None = None) -> None:
        phrases = phrases if phrases is not None else ["standard"]
        if "standard" in phrases:
            print("Creating phrases...")
            pipeline = build_phrase_pipeline(self.con, include_numeric_skip=False)
            for n in range(MAX_PHRASE_CHUNKS):
                print(f"Creating phrases for chunk {n}...")
                pipeline.execute_into_table("phrase", [n])
        if "trigram" in phrases:
            super().create_phrases(["trigram"])

    def create_inverted_index(self, phrases: list[str] | None = None) -> None:
        phrases = phrases if phrases is not None else ["standard"]
        print("Creating inverted index...")
        if "standard" in phrases:
            inverted_index_pipeline(self.con, "standard").execute_direct()

    def clean_database(self, phrases: list[str]) -> None:
        cleanup_pipeline(self.con, phrases, legacy=True).execute_direct()
