from .standard import create_matching_query
from .common import register_functions, load_libraries
from .addrtext_with_detail import build_address_detail_pipeline
from .skipphrase import create_matching_query as create_skipphrase_query
from .trigram import create_matching_query as create_trigram_query
from duckdb import DuckDBPyConnection
from ..QueryPipeline import QueryPipeline


def create_matching_pipeline(
    con: DuckDBPyConnection, how: str = "standard", top_n: int = 1
) -> QueryPipeline:
    if how == "standard":
        return create_matching_query(con)
    if how == "skipphrase":
        return create_skipphrase_query(con, top_n)
    if how == "trigram":
        return create_trigram_query(con, top_n)
    raise ValueError(f"Invalid geocoding algorithm: {how}")


__all__ = [
    "create_matching_query",
    "register_functions",
    "load_libraries",
    "build_address_detail_pipeline",
    "create_matching_pipeline",
    "create_skipphrase_query",
    "create_trigram_query",
]
