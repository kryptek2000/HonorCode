"""CSV batch export for gradebook-adjacent workflows."""

import csv

from .compare import compare
from .features import extract

COLUMNS = ["student", "submission", "score", "band", "n_flags", "top_flags"]


def rows_for(baseline, submissions, bands=None, top_n=3):
    """Score many submissions against one baseline.

    submissions: list of (label, text). Returns a list of row dicts
    with scores formatted to 3 decimals (display only).
    """
    rows = []
    for label, text in submissions:
        result = compare(extract(text), baseline, bands=bands)
        top = ";".join(f["feature"] for f in result["flags"][:top_n])
        rows.append({
            "student": baseline.get("student", "?"),
            "submission": label,
            "score": "%.3f" % result["score"],
            "band": result["band"],
            "n_flags": len(result["flags"]),
            "top_flags": top,
        })
    return rows


def write_csv(rows, path):
    """Write rows to CSV with a stable header."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
