"""
Geocoder Validator — FastAPI backend
Run with:  uv run python geocoder_server.py
"""

import io
import os
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from whereabouts.utils import list_overlap, multiset_jaccard, numeric_overlap, numeric_overlap2, ngram_jaccard

QUERIES_DIR = Path(__file__).parent.parent / "whereabouts" / "queries"
MODELS_DIR  = Path(__file__).parent.parent / "whereabouts" / "models"
HTML_FILE   = Path(__file__).parent / "geocoder_ui.html"

app = FastAPI()


# ── helpers ──────────────────────────────────────────────────────────────────

def _clean(obj):
    """Recursively replace NaN/NaT with None and numpy scalars with Python natives."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    # np.floating covers float16/32/64 regardless of whether they subclass Python float
    if isinstance(obj, (float, np.floating)):
        return None if np.isnan(obj) else float(obj)
    # Convert other numpy scalars (int, bool, str…) to Python natives
    if isinstance(obj, np.generic):
        return obj.item()
    # Catch pandas NA / NaT / None
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return obj


def _connect(db_name: str) -> duckdb.DuckDBPyConnection:
    db_path = MODELS_DIR / f"{db_name}.db"
    if not db_path.exists():
        raise HTTPException(400, f"Database not found: {db_name}")
    con = duckdb.connect()
    con.execute(f"ATTACH DATABASE '{db_path}' AS remote;")
    for fn, name in [
        (list_overlap,     "list_overlap"),
        (multiset_jaccard, "multiset_jaccard"),
        (numeric_overlap,  "numeric_overlap"),
        (numeric_overlap2, "numeric_overlap2"),
        (ngram_jaccard,    "ngram_jaccard"),
    ]:
        try:
            con.create_function(name, fn)
        except Exception:
            pass
    return con


# ── routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_FILE.read_text()


@app.get("/api/databases")
def list_databases():
    return sorted(f[:-3] for f in os.listdir(MODELS_DIR) if f.endswith(".db"))


@app.get("/api/queries")
def list_queries():
    return sorted(
        f for f in os.listdir(QUERIES_DIR)
        if f.startswith("geocoder_query") and f.endswith(".sql")
    )


@app.get("/api/queries/{filename}")
def get_query(filename: str):
    path = QUERIES_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Query not found")
    return {"sql": path.read_text()}


class SaveQueryRequest(BaseModel):
    name: str
    sql: str

@app.post("/api/queries")
def save_query(req: SaveQueryRequest):
    safe = req.name.strip().replace(" ", "_")
    if not safe:
        raise HTTPException(400, "Name is empty")
    filename = f"geocoder_query_{safe}.sql"
    (QUERIES_DIR / filename).write_text(req.sql)
    return {"filename": filename}


class GeocodeRequest(BaseModel):
    database: str
    sql: str
    csv: str          # raw CSV text

@app.post("/api/geocode")
def geocode(req: GeocodeRequest):
    df_input = pd.read_csv(io.StringIO(req.csv))
    if "input_address" not in df_input.columns:
        raise HTTPException(400, "CSV is missing required column: input_address")

    has_correct = "correct_match" in df_input.columns
    addresses   = df_input["input_address"].tolist()

    con = _connect(req.database)
    input_df = pd.DataFrame(
        {"address_id": range(1, len(addresses) + 1), "address": addresses}
    )
    input_df["address"] = input_df["address"].astype(object)
    con.execute("DROP TABLE IF EXISTS input_addresses;")
    con.execute("CREATE TABLE input_addresses (address_id INTEGER, address VARCHAR);")
    con.execute("INSERT INTO input_addresses SELECT * FROM input_df;")

    sql = req.sql.replace("?", "1")
    t0 = time.perf_counter()
    try:
        raw = con.execute(sql).df()
    except Exception as exc:
        con.close()
        raise HTTPException(400, str(exc))
    elapsed = time.perf_counter() - t0

    con.execute("DROP TABLE IF EXISTS input_addresses;")
    con.close()

    geocoded = raw.get("address_matched", pd.Series(dtype=str))
    geocoded_vals = (
        geocoded.tolist() if len(geocoded) == len(df_input) else [None] * len(df_input)
    )

    rows = []
    n_correct = 0
    for i, addr_row in df_input.iterrows():
        g = geocoded_vals[i] if i < len(geocoded_vals) else None
        auto = None
        if has_correct:
            cm = str(addr_row["correct_match"] or "").upper().strip()
            gr = str(g or "").upper().strip()
            auto = (cm == gr) if cm else None
            if auto:
                n_correct += 1
        rows.append({
            "input_address":  addr_row["input_address"],
            "correct_match":  addr_row.get("correct_match") if has_correct else None,
            "geocoded_result": g,
            "auto":           auto,
        })

    return _clean({
        "rows":        rows,
        "total":       len(rows),
        "n_correct":   n_correct if has_correct else None,
        "accuracy":    round(n_correct / len(rows) * 100, 1) if has_correct and rows else None,
        "elapsed":     round(elapsed, 3),
        "has_correct": has_correct,
    })


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
