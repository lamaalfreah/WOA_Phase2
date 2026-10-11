import csv
import json
import random
import time
from pathlib import Path

import requests

from snapshot_config import safe_output, with_mailto


# -----------------------------
# Settings
# -----------------------------

G1_FILE = Path("data/intermediate/g1_with_self_citation.csv")

OUTPUT_RAW = safe_output("data/raw/g2_pilot_raw_2026-10-04.json")
OUTPUT_SUMMARY = safe_output("data/logs/g2_pilot_summary.txt")
OUTPUT_SAMPLE = safe_output("data/logs/g2_pilot_sample.csv")

BASE_URL = "https://api.openalex.org/works"

SEED_ID = "W2290883490"

SAMPLE_SIZE = 100
RANDOM_SEED = 20261004

BATCH_SIZE = 25
PER_PAGE = 100


# -----------------------------
# Read G1
# -----------------------------

with open(G1_FILE, "r", encoding="utf-8-sig") as f:
    g1_rows = list(csv.DictReader(f))

g1_ids = {
    row["openalex_id"].strip()
    for row in g1_rows
    if row["openalex_id"].strip()
}

print(f"Total G1 IDs: {len(g1_ids)}")


# -----------------------------
# Freeze pilot sample
# -----------------------------

random.seed(RANDOM_SEED)

sample_rows = random.sample(
    g1_rows,
    min(SAMPLE_SIZE, len(g1_rows))
)

sample_ids = [
    row["openalex_id"].strip()
    for row in sample_rows
]

print(f"Pilot sample size: {len(sample_ids)}")
print(f"Random seed: {RANDOM_SEED}")


# Save exact sample
with open(
    OUTPUT_SAMPLE,
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    fieldnames = [
        "openalex_id",
        "title",
        "publication_year",
        "field"
    ]

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames
    )

    writer.writeheader()

    for row in sample_rows:
        writer.writerow({
            "openalex_id": row["openalex_id"],
            "title": row["title"],
            "publication_year": row["publication_year"],
            "field": row["field"]
        })


# -----------------------------
# Helper: query one batch
# -----------------------------

def fetch_batch_citers(batch_ids):

    joined_ids = "|".join(batch_ids)

    params = {
        "filter": f"cites:{joined_ids},publication_year:2016-2026",
        "per_page": PER_PAGE,
        "cursor": "*"
    }

    found = []

    while True:

        response = requests.get(
            BASE_URL,
            params=with_mailto(params),
            timeout=60
        )

        # Retry temporary OpenAlex errors
        if response.status_code == 429 or response.status_code >= 500:

            print(
                f"Temporary error {response.status_code}. "
                "Waiting 3 seconds..."
            )

            time.sleep(3)
            continue

        response.raise_for_status()

        data = response.json()

        results = data.get("results", [])

        for work in results:

            work_id = (work.get("id") or "").replace(
                "https://openalex.org/", ""
            )

            if work_id:
                found.append(work_id)

        next_cursor = data.get(
            "meta",
            {}
        ).get("next_cursor")

        if not next_cursor or not results:
            break

        params["cursor"] = next_cursor

        time.sleep(0.2)

    return found


# -----------------------------
# Query pilot G2
# -----------------------------

all_reached_ids = set()

batches = [
    sample_ids[i:i + BATCH_SIZE]
    for i in range(0, len(sample_ids), BATCH_SIZE)
]

for index, batch in enumerate(batches, start=1):

    print(
        f"Fetching pilot batch "
        f"{index}/{len(batches)}..."
    )

    batch_results = fetch_batch_citers(batch)

    before = len(all_reached_ids)

    all_reached_ids.update(batch_results)

    added = len(all_reached_ids) - before

    print(
        f"  Retrieved in batch: {len(batch_results)}"
    )

    print(
        f"  New unique reached works: {added}"
    )

    print(
        f"  Total unique reached so far: "
        f"{len(all_reached_ids)}"
    )


# -----------------------------
# Separate actual new G2
# -----------------------------

# Remove anything already in G1
new_g2_ids = all_reached_ids - g1_ids

# Seed itself should not appear, but remove defensively
new_g2_ids.discard(SEED_ID)


# -----------------------------
# Save raw pilot result
# -----------------------------

pilot_output = {
    "retrieval_date": "2026-10-04",
    "sample_size": len(sample_ids),
    "random_seed": RANDOM_SEED,
    "batch_size": BATCH_SIZE,
    "sample_g1_ids": sample_ids,
    "all_unique_reached_ids": sorted(all_reached_ids),
    "new_g2_ids_after_removing_g1": sorted(new_g2_ids),
    "all_unique_reached_count": len(all_reached_ids),
    "new_g2_count": len(new_g2_ids)
}

with open(
    OUTPUT_RAW,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        pilot_output,
        f,
        ensure_ascii=False,
        indent=2
    )


# -----------------------------
# Simple feasibility estimate
# -----------------------------

avg_new_g2_per_sampled_g1 = (
    len(new_g2_ids) / len(sample_ids)
)

rough_full_scale_estimate = (
    avg_new_g2_per_sampled_g1 *
    len(g1_ids)
)


summary = f"""
G2 Pilot Feasibility Check

Retrieval date: 2026-10-04

Total G1 records:
{len(g1_ids)}

Pilot G1 sample size:
{len(sample_ids)}

Random seed:
{RANDOM_SEED}

Batch size:
{BATCH_SIZE}

Unique works reached through pilot G1 sample:
{len(all_reached_ids)}

New G2 works after removing existing G1:
{len(new_g2_ids)}

Average new G2 works per sampled G1:
{avg_new_g2_per_sampled_g1:.2f}

Very rough full-scale estimate:
{rough_full_scale_estimate:.0f}

Important note:
The full-scale estimate is only a feasibility indicator.
It is not the final G2 size because citing sets overlap heavily.
The final G2 count must be based on unique OpenAlex IDs after
complete retrieval and deduplication.
"""


with open(
    OUTPUT_SUMMARY,
    "w",
    encoding="utf-8"
) as f:
    f.write(summary)


print(summary)

print(f"Pilot raw result saved to: {OUTPUT_RAW}")
print(f"Frozen sample saved to: {OUTPUT_SAMPLE}")
print(f"Summary saved to: {OUTPUT_SUMMARY}")