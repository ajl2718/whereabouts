import duckdb

# create a list of neighbouring suburbs to any given suburb
db = duckdb.connect("whereabouts/models/au_vic_sm.db")
