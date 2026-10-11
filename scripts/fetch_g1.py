import json
import time
from datetime import date
from pathlib import Path

import requests

from snapshot_config import CUTOFF, safe_output, with_mailto, within_cutoff


SEED_ID = "W2290883490"
START_YEAR = 2016
END_YEAR = 2026
PER_PAGE = 100

BASE_URL = "https://api.openalex.org/works"

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RETRIEVAL_DATE = date.today().isoformat()

# A live rerun keeps every complete OpenAlex response page here.
PAGES_DIR = Path("data/rerun") / RETRIEVAL_DATE / "pages"
PAGES_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = safe_output(
    OUTPUT_DIR / f"g1_raw_{RETRIEVAL_DATE}.json"
)

params = {
    "filter": (
        f"cites:{SEED_ID},"
        f"publication_year:{START_YEAR}-{END_YEAR}"
    ),
    "per_page": PER_PAGE,
    "cursor": "*",
}

all_results = []
page_number = 1

print("Starting G1 retrieval...")
print(f"Seed ID: {SEED_ID}")
print(f"Years: {START_YEAR}-{END_YEAR}")
print(f"Page cache: {PAGES_DIR}")

while True:
    print(f"Fetching page {page_number}...")

    response = requests.get(
        BASE_URL,
        params=with_mailto(params),
        timeout=60,
    )
    response.raise_for_status()

    data = response.json()

    # Save the complete response before extracting or filtering anything.
    page_file = safe_output(
        PAGES_DIR / f"g1_page_{page_number:04d}.json"
    )

    with open(page_file, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )

    results = data.get("results", [])
    meta = data.get("meta", {})

    if page_number == 1:
        print(
            f"OpenAlex reports "
            f"{meta.get('count')} matching works."
        )

    all_results.extend(results)

    print(
        f"Downloaded {len(results)} records "
        f"(total so far: {len(all_results)})"
    )
    print(f"Saved page: {page_file}")

    next_cursor = meta.get("next_cursor")

    if not next_cursor or not results:
        break

    params["cursor"] = next_cursor
    page_number += 1

    time.sleep(0.2)


# Apply the declared data cutoff.
returned_count = len(all_results)

after_cutoff = [
    work["id"]
    for work in all_results
    if not within_cutoff(work)
]

all_results = [
    work
    for work in all_results
    if within_cutoff(work)
]

print(
    f"OpenAlex returned {returned_count}; "
    f"{len(after_cutoff)} created or published "
    f"after {CUTOFF} were dropped."
)

output_data = {
    "retrieval_date": RETRIEVAL_DATE,
    "data_cutoff": CUTOFF,
    "returned_before_cutoff_rule": returned_count,
    "dropped_after_cutoff": after_cutoff,
    "database": "OpenAlex",
    "seed_id": SEED_ID,
    "publication_year_range": (
        f"{START_YEAR}-{END_YEAR}"
    ),
    "query_filter": params["filter"],
    "record_count": len(all_results),
    "page_cache_directory": str(PAGES_DIR),
    "pages_saved": page_number,
    "results": all_results,
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(
        output_data,
        f,
        ensure_ascii=False,
        indent=2,
    )

print()
print("Finished.")
print(f"Total records saved: {len(all_results)}")
print(f"Pages saved: {page_number}")
print(f"Page cache: {PAGES_DIR}")
print(f"Combined output: {OUTPUT_FILE}")
