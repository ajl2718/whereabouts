from duckdb import DuckDBPyConnection

from ..utils import list_overlap, numeric_overlap, ngram_jaccard, multiset_jaccard, IOU


def register_functions(con: DuckDBPyConnection):
    con.create_function('list_overlap', list_overlap)
    con.create_function('numeric_overlap', numeric_overlap)
    con.create_function('multiset_jaccard', multiset_jaccard)
    con.create_function('ngram_jaccard', ngram_jaccard)
    con.create_function('IOU', IOU)


def load_libraries(con: DuckDBPyConnection):
    # Load any necessary extensions here if needed
    con.execute("""
            INSTALL splink_udfs FROM community;
            LOAD splink_udfs;
            """)
