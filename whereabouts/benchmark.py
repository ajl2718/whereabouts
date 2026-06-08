from __future__ import annotations

import importlib.resources
from dataclasses import dataclass, field
from pathlib import Path
from time import time

import pandas as pd

_RESULTS_DIR = Path(str(importlib.resources.files("whereabouts"))) / "benchmark_results"

from .Matcher import Matcher

# ANSI colour codes
_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"
_BOLD = "\033[1m"


def _normalize(s: str | None) -> str:
    """Lowercase and collapse whitespace for comparison."""
    if s is None:
        return ""
    return " ".join(str(s).lower().split())


@dataclass
class BenchmarkResult:
    """Results from a geocoding benchmark run."""

    total: int
    matched: int
    unmatched: int
    match_rate: float
    elapsed_seconds: float
    rows: list[dict] = field(default_factory=list)

    def to_csv(self, path: str | Path | None = None) -> Path:
        """Write the per-row benchmark results to a CSV file.

        Parameters
        ----------
        path : str, Path, or None
            Destination file path. If ``None``, a timestamped file is
            written to ``whereabouts/benchmark_results/``.

        Returns
        -------
        Path
            The path the CSV was written to.
        """
        if path is None:
            from datetime import datetime

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = _RESULTS_DIR / f"benchmark_{stamp}.csv"
        else:
            path = Path(path)
            # Plain filename (no directory component) goes into the default results folder
            if path.parent == Path("."):
                path = _RESULTS_DIR / path

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(self.rows)
        df.to_csv(path, index=False)
        return path

    def summary(self, colour: bool = True) -> str:
        g, r, rst, b = (_GREEN, _RED, _RESET, _BOLD) if colour else ("", "", "", "")

        lines = [
            f"{b}Benchmark Results{rst}",
            "-" * 40,
            f"Total addresses:   {self.total}",
            f"Correctly matched: {g}{self.matched}{rst}",
            f"Unmatched:         {r}{self.unmatched}{rst}",
            f"Match rate:        {self.match_rate:.2%}",
            f"Time:              {self.elapsed_seconds:.2f}s",
        ]
        if self.rows:
            lines.append("")
            lines.append(f"{'Input':<50}{'Got':<50}Expected")
            lines.append("-" * 150)
            for row in self.rows:
                inp = (row["input_address"] or "")[:48]
                got = (row["matched_address"] or "")[:48]
                exp = (row["expected_address"] or "")[:48]
                clr = g if row["correct"] else r
                line = f"{inp:<50}{got:<50}{exp}"
                lines.append(f"{clr}{line}{rst}")
        return "\n".join(lines)


def run_benchmark(
    db_name: str,
    csv_path: str,
    how: str = "standard",
    threshold: float = 0.5,
    input_col: str = "input_address",
    expected_col: str = "best_match",
) -> BenchmarkResult:
    """Run a geocoding benchmark against a CSV file of address pairs.

    Parameters
    ----------
    db_name : str
        Name of the geocoder database (or path/URL).
    csv_path : str
        Path to a CSV with input and expected address columns.
    how : str
        Matching algorithm (``standard``, ``skipphrase``, or ``trigram``).
    threshold : float
        Similarity threshold for the matcher.
    input_col : str
        Column name for the input addresses.
    expected_col : str
        Column name for the expected matched addresses.

    Returns
    -------
    BenchmarkResult
    """
    df = pd.read_csv(csv_path)

    if input_col not in df.columns:
        raise ValueError(f"Column '{input_col}' not found in {csv_path}")
    if expected_col not in df.columns:
        raise ValueError(f"Column '{expected_col}' not found in {csv_path}")

    addresses = df[input_col].tolist()
    expected = df[expected_col].tolist()

    matcher = Matcher(db_name, how=how, threshold=threshold)

    t_start = time()
    results = matcher.geocode(addresses)
    elapsed = time() - t_start

    matcher.close()

    rows: list[dict] = []
    matched = 0

    for addr_in, result, addr_expected in zip(addresses, results, expected):
        addr_matched = result.get("address_matched")
        correct = _normalize(addr_matched) == _normalize(addr_expected)
        if correct:
            matched += 1
        row = {
            "input_address": str(addr_in) if addr_in is not None else "",
            "matched_address": str(addr_matched) if addr_matched is not None else "",
            "expected_address": str(addr_expected) if addr_expected is not None else "",
            "correct": correct,
        }
        rows.append(row)

    total = len(addresses)
    return BenchmarkResult(
        total=total,
        matched=matched,
        unmatched=total - matched,
        match_rate=matched / total if total else 0.0,
        elapsed_seconds=elapsed,
        rows=rows,
    )
