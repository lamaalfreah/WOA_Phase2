"""
Re-run the G1 query against live OpenAlex and explain every difference from
the submitted snapshot (retrieved 2026-10-04, data cutoff 2026-10-04).

Run from the project root:
    python scripts/compare_live_to_snapshot.py

Uses exactly the snapshot query (cites:W2290883490, publication_year
2016-2026, cursor paging) and asks only for the fields needed to compare.
Nothing in data/raw, data/core or data/clean is changed; the result goes to
data/rerun/<today>/:
    g1_reconciliation.txt          summary
    g1_live_vs_snapshot.csv        one row per differing OpenAlex ID
"""
import csv
import time

import requests

from snapshot_config import CUTOFF, SNAPSHOT_DATES, TODAY, rerun_dir, with_mailto

SEED_ID = "W2290883490"
BASE_URL = "https://api.openalex.org/works"
FILTER = f"cites:{SEED_ID},publication_year:2016-2026"
SNAPSHOT_FILE = "data/clean/g1_clean.csv"
SELECT = "id,publication_date,created_date,type,publication_year"


def get(params):
    for attempt in range(6):
        r = requests.get(BASE_URL, params=with_mailto(params), timeout=60)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
    raise RuntimeError("OpenAlex request failed after retries")


# ---------------------------------------------------------------- live query
live = {}
params = {"filter": FILTER, "select": SELECT, "per_page": 200, "cursor": "*"}
while True:
    data = get(params)
    for w in data["results"]:
        live[w["id"].replace("https://openalex.org/", "")] = w
    cursor = data["meta"].get("next_cursor")
    if not cursor or not data["results"]:
        break
    params["cursor"] = cursor
    time.sleep(0.2)

seed = requests.get(f"{BASE_URL}/{SEED_ID}", params=with_mailto({}), timeout=60).json()

# ---------------------------------------------------------------- snapshot
with open(SNAPSHOT_FILE, encoding="utf-8-sig") as f:
    snap = {r["openalex_id"]: r for r in csv.DictReader(f)}

# ---------------------------------------------------------------- compare
rows = []
for wid in sorted(set(snap) - set(live)):
    r = snap[wid]
    rows.append({"openalex_id": wid, "status": "in snapshot, no longer returned by OpenAlex",
                 "publication_type": r["publication_type"], "publication_year": r["publication_year"],
                 "created_date": r.get("openalex_created_date", ""), "in_core_analysis": r.get("in_core_analysis", "")})

for wid in sorted(set(live) - set(snap)):
    w = live[wid]
    created = (w.get("created_date") or "")[:10]
    pub = w.get("publication_date") or ""
    if created > CUTOFF or pub > CUTOFF:
        status = f"new: added to OpenAlex or published after the {CUTOFF} cutoff (excluded by rule C1)"
    else:
        status = f"new: existed by {CUTOFF} but its citation to the seed appeared in OpenAlex later"
    rows.append({"openalex_id": wid, "status": status, "publication_type": w.get("type", ""),
                 "publication_year": w.get("publication_year", ""), "created_date": created, "in_core_analysis": ""})

out = rerun_dir()
with open(out / "g1_live_vs_snapshot.csv", "w", newline="", encoding="utf-8-sig") as f:
    wr = csv.DictWriter(f, fieldnames=["openalex_id", "status", "publication_type", "publication_year",
                                       "created_date", "in_core_analysis"])
    wr.writeheader()
    wr.writerows(rows)

gone = [r for r in rows if r["status"].startswith("in snapshot")]
new_after = [r for r in rows if "excluded by rule C1" in r["status"]]
new_late = [r for r in rows if "appeared in OpenAlex later" in r["status"]]
live_within = len(live) - len(new_after)
gone_types = {}
for r in gone:
    gone_types[r["publication_type"]] = gone_types.get(r["publication_type"], 0) + 1
gone_core = sum(1 for r in gone if str(r["in_core_analysis"]) == "1")

summary = f"""G1 live re-run vs submitted snapshot
Re-run date: {TODAY}
Snapshot retrieval date: {SNAPSHOT_DATES['G1']}   Data cutoff: {CUTOFF}
Query: {BASE_URL}?filter={FILTER}&per_page=200&cursor=*

Snapshot records:                              {len(snap)}
Live records returned today:                   {len(live)}
  of which added/published after the cutoff:   {len(new_after)}  (excluded by rule C1)
Live records within the cutoff:                {live_within}

Difference explained:
  in snapshot, no longer returned by OpenAlex: {len(gone)}  by type: {gone_types}; in core analysis: {gone_core}
  existed by the cutoff, citation link added later: {len(new_late)}
  check: {len(snap)} - {len(gone)} + {len(new_late)} = {len(snap) - len(gone) + len(new_late)} (live within cutoff = {live_within})

Seed cited_by_count today: {seed.get('cited_by_count')}  (14692 on {SNAPSHOT_DATES['G1']})

The submitted results are computed from the saved snapshot files, not from
live OpenAlex. Every differing ID is listed in g1_live_vs_snapshot.csv.
"""
(out / "g1_reconciliation.txt").write_text(summary, encoding="utf-8")
print(summary)
