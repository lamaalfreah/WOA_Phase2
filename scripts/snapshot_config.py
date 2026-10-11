"""Shared settings that freeze the study at its declared data cutoff.

The submitted dataset is the snapshot retrieved on 4 October 2026 (G1) and
6 October 2026 (G2). OpenAlex changes every day and its free API cannot
return the database "as it was" on a past date (the to_created_date filter
needs a paid plan), so any live re-run is handled like this:

1. The query string is exactly the one used for the snapshot.
2. Every returned work created in OpenAlex, or published, after CUTOFF is
   dropped (created_date / publication_date are fields of each record).
3. Output never overwrites the snapshot: it goes to data/rerun/<today>/.
4. scripts/compare_live_to_snapshot.py lists every difference by ID.
"""
from datetime import date
from pathlib import Path

CUTOFF = "2026-10-04"
SNAPSHOT_DATES = {"G1": "2026-10-04", "G2": "2026-10-06"}

# OpenAlex asks API users to add an e-mail address (polite pool).
# Put the group's KSU e-mail here before any live run.
MAILTO = ""

TODAY = date.today().isoformat()


def rerun_dir():
    d = Path("data/rerun") / TODAY
    d.mkdir(parents=True, exist_ok=True)
    return d


def safe_output(path):
    """Return `path` during the original retrieval; for any later run, or if
    the file already exists, return data/rerun/<today>/<name> instead, so a
    re-run can never overwrite the snapshot."""
    path = Path(path)
    if path.exists() or TODAY > max(SNAPSHOT_DATES.values()):
        new = rerun_dir() / path.name
        print(f"Snapshot file {path} exists - writing re-run output to {new}")
        return new
    return path


def within_cutoff(work):
    created = (work.get("created_date") or "")[:10]
    published = work.get("publication_date") or ""
    return created <= CUTOFF and published <= CUTOFF


def with_mailto(params):
    if MAILTO:
        params = dict(params)
        params["mailto"] = MAILTO
    return params
