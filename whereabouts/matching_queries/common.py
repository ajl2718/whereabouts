from duckdb import DuckDBPyConnection

from ..utils import list_overlap, numeric_overlap, numeric_overlap2, ngram_jaccard, multiset_jaccard, IOU, IOU_min


def register_functions(con: DuckDBPyConnection):
    con.create_function('list_overlap', list_overlap)
    con.create_function('numeric_overlap', numeric_overlap)
    con.create_function('numeric_overlap2', numeric_overlap2)
    con.create_function('multiset_jaccard', multiset_jaccard)
    con.create_function('ngram_jaccard', ngram_jaccard)
    con.create_function('IOU', IOU)
    con.create_function("IOU_min", IOU_min)


def load_libraries(con: DuckDBPyConnection):
    # Load any necessary extensions here if needed
    con.execute("""
            INSTALL splink_udfs FROM community;
            LOAD splink_udfs;
            """)
