import csv
import json
import time
from datetime import date
from pathlib import Path

import requests

from snapshot_config import CUTOFF, with_mailto, within_cutoff


RETRIEVAL_DATE = date.today().isoformat()

SAMPLE_FILE = Path(
    "data/core/g1_stratified_sample_500.csv"
)

FULL_G1_FILE = Path(
    "data/intermediate/g1_with_self_citation.csv"
)

SEED_ID = "W2290883490"
BASE_URL = "https://api.openalex.org/works"

BATCH_SIZE = 25
PER_PAGE = 100
MAX_RETRIES = 6

# Every live rerun is isolated from the submitted snapshot.
RERUN_DIR = Path("data/rerun") / RETRIEVAL_DATE
PAGES_DIR = RERUN_DIR / "pages"

RERUN_DIR.mkdir(parents=True, exist_ok=True)
PAGES_DIR.mkdir(parents=True, exist_ok=True)

RAW_OUTPUT = RERUN_DIR / "g2_stratified_raw.json"
G2_OUTPUT = RERUN_DIR / "g2_extracted.csv"
LINKS_OUTPUT = RERUN_DIR / "g2_parent_links.csv"
SUMMARY_OUTPUT = RERUN_DIR / "g2_collection_summary.txt"


def normalize_openalex_id(value):
    return (value or "").replace(
        "https://openalex.org/",
        ""
    )


# -------------------------------------------------
# Load full G1 IDs
# -------------------------------------------------

with open(
    FULL_G1_FILE,
    "r",
    encoding="utf-8-sig"
) as f:
    full_g1_rows = list(csv.DictReader(f))

full_g1_ids = {
    row["openalex_id"].strip()
    for row in full_g1_rows
    if row.get("openalex_id", "").strip()
}

print(f"Full G1 IDs: {len(full_g1_ids)}")


# -------------------------------------------------
# Load frozen G1 sample
# -------------------------------------------------

with open(
    SAMPLE_FILE,
    "r",
    encoding="utf-8-sig"
) as f:
    sample_rows = list(csv.DictReader(f))

sample_ids = [
    row["openalex_id"].strip()
    for row in sample_rows
    if row.get("openalex_id", "").strip()
]

sample_id_set = set(sample_ids)

print(f"Frozen G1 sample IDs: {len(sample_ids)}")


# -------------------------------------------------
# Fetch helper with retry
# -------------------------------------------------

def get_with_retry(params):
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                BASE_URL,
                params=with_mailto(params),
                timeout=60
            )

            if response.status_code == 200:
                return response

            if (
                response.status_code == 429
                or response.status_code >= 500
            ):
                wait = 2 ** attempt

                print(
                    f"Temporary error "
                    f"{response.status_code}. "
                    f"Retrying in {wait}s..."
                )

                time.sleep(wait)
                continue

            response.raise_for_status()

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError
        ):
            wait = 2 ** attempt

            print(
                "Connection/timeout error. "
                f"Retrying in {wait}s..."
            )

            time.sleep(wait)

    raise RuntimeError(
        "OpenAlex request failed after retries."
    )


# -------------------------------------------------
# Fetch citing records in batches
# -------------------------------------------------

all_reached = {}

batches = [
    sample_ids[i:i + BATCH_SIZE]
    for i in range(0, len(sample_ids), BATCH_SIZE)
]

print(f"Total batches: {len(batches)}")
print(f"Rerun directory: {RERUN_DIR}")
print(f"JSON page cache: {PAGES_DIR}")


for batch_number, batch_ids in enumerate(
    batches,
    start=1
):
    print(
        f"\nFetching batch "
        f"{batch_number}/{len(batches)}"
    )

    joined_ids = "|".join(batch_ids)

    params = {
        "filter": (
            f"cites:{joined_ids},"
            "publication_year:2016-2026"
        ),
        "per_page": PER_PAGE,
        "cursor": "*"
    }

    batch_count = 0
    page_number = 1

    while True:
        response = get_with_retry(params)
        data = response.json()

        # Save the complete OpenAlex response page
        # before any filtering or transformation.
        page_file = (
            PAGES_DIR
            / (
                f"g2_batch_{batch_number:02d}_"
                f"page_{page_number:04d}.json"
            )
        )

        with open(
            page_file,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )

        results = data.get("results", [])

        for work in results:
            work_id = normalize_openalex_id(
                work.get("id")
            )

            if not work_id:
                continue

            # Apply the declared data cutoff only
            # after the raw response has been cached.
            if not within_cutoff(work):
                continue

            all_reached[work_id] = work
            batch_count += 1

        next_cursor = (
            data.get("meta", {})
            .get("next_cursor")
        )

        print(
            f"Batch {batch_number}, "
            f"page {page_number}: "
            f"{len(results)} records"
        )

        if not next_cursor or not results:
            break

        params["cursor"] = next_cursor
        page_number += 1

        time.sleep(0.25)

    print(
        f"Batch records encountered: "
        f"{batch_count}"
    )

    print(
        f"Unique reached so far: "
        f"{len(all_reached)}"
    )


# -------------------------------------------------
# Remove complete G1 to define G2
# -------------------------------------------------

all_reached_ids = set(all_reached.keys())

g2_ids = all_reached_ids - full_g1_ids
g2_ids.discard(SEED_ID)

print()
print(
    f"All unique works reached: "
    f"{len(all_reached_ids)}"
)

print(
    f"New G2 works after removing G1: "
    f"{len(g2_ids)}"
)


# -------------------------------------------------
# Save combined raw G2 records
# -------------------------------------------------

raw_g2_records = [
    all_reached[g2_id]
    for g2_id in sorted(g2_ids)
]

raw_output = {
    "retrieval_date": RETRIEVAL_DATE,
    "data_cutoff": CUTOFF,
    "database": "OpenAlex",
    "seed_id": SEED_ID,
    "g1_full_count": len(full_g1_ids),
    "g1_sample_count": len(sample_ids),
    "batch_size": BATCH_SIZE,
    "g2_unique_count": len(g2_ids),
    "page_cache_directory": str(PAGES_DIR),
    "results": raw_g2_records
}

with open(
    RAW_OUTPUT,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        raw_output,
        f,
        ensure_ascii=False,
        indent=2
    )


# -------------------------------------------------
# Extract G2 metadata
# -------------------------------------------------

fieldnames = [
    "openalex_id",
    "doi",
    "title",
    "publication_year",
    "venue",
    "field",
    "field_id",
    "subfield",
    "domain",
    "keywords",
    "citation_count",
    "authors",
    "author_ids",
    "publication_type",
    "language",
    "generation",
    "retrieval_date",
    "year_status"
]


with open(
    G2_OUTPUT,
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:
    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames
    )

    writer.writeheader()

    for g2_id in sorted(g2_ids):
        work = all_reached[g2_id]

        topic = work.get("primary_topic") or {}

        field_obj = topic.get("field") or {}
        subfield_obj = topic.get("subfield") or {}
        domain_obj = topic.get("domain") or {}

        primary_location = (
            work.get("primary_location")
            or {}
        )

        source = (
            primary_location.get("source")
            or {}
        )

        authorships = (
            work.get("authorships")
            or []
        )

        author_names = []
        author_ids = []

        for authorship in authorships:
            author = (
                authorship.get("author")
                or {}
            )

            name = (
                author.get("display_name")
                or ""
            )

            aid = normalize_openalex_id(
                author.get("id")
            )

            if name:
                author_names.append(name)

            if aid:
                author_ids.append(aid)

        keywords = "; ".join(
            kw.get("display_name", "")
            for kw in (
                work.get("keywords")
                or []
            )
            if kw.get("display_name")
        )

        year = (
            work.get("publication_year")
            or ""
        )

        field_id = str(
            field_obj.get("id")
            or ""
        ).replace(
            "https://openalex.org/fields/",
            ""
        )

        writer.writerow({
            "openalex_id": g2_id,
            "doi": work.get("doi") or "",
            "title": work.get("title") or "",
            "publication_year": year,
            "venue": (
                source.get("display_name")
                or ""
            ),
            "field": (
                field_obj.get("display_name")
                or ""
            ),
            "field_id": field_id,
            "subfield": (
                subfield_obj.get("display_name")
                or ""
            ),
            "domain": (
                domain_obj.get("display_name")
                or ""
            ),
            "keywords": keywords,
            "citation_count": (
                work.get("cited_by_count")
                or 0
            ),
            "authors": "; ".join(
                author_names
            ),
            "author_ids": "; ".join(
                author_ids
            ),
            "publication_type": (
                work.get("type")
                or ""
            ),
            "language": (
                work.get("language")
                or ""
            ),
            "generation": "G2",
            "retrieval_date": RETRIEVAL_DATE,
            "year_status": (
                "partial"
                if year == 2026
                else "complete"
            )
        })


# -------------------------------------------------
# Recover parent links
# -------------------------------------------------

link_rows = []

for g2_id in sorted(g2_ids):
    work = all_reached[g2_id]

    references = {
        normalize_openalex_id(ref)
        for ref in (
            work.get("referenced_works")
            or []
        )
    }

    matched_parents = (
        references.intersection(
            sample_id_set
        )
    )

    for parent_id in sorted(
        matched_parents
    ):
        link_rows.append({
            "g2_id": g2_id,
            "parent_g1_id": parent_id
        })


with open(
    LINKS_OUTPUT,
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "g2_id",
            "parent_g1_id"
        ]
    )

    writer.writeheader()
    writer.writerows(link_rows)


# -------------------------------------------------
# Summary
# -------------------------------------------------

summary = f"""
G2 Collection from Frozen Stratified G1 Sample

Retrieval date:
{RETRIEVAL_DATE}

Data cutoff:
{CUTOFF}

Full G1 size:
{len(full_g1_ids)}

Frozen stratified G1 sample size:
{len(sample_ids)}

Unique works reached through sampled G1:
{len(all_reached_ids)}

Unique G2 records after removing all G1:
{len(g2_ids)}

G2-parent citation links:
{len(link_rows)}

Definition:
G2 contains works reached by following citations
to the frozen sampled G1 records, after removing
all records already present in the complete G1 set.

JSON pages:
{PAGES_DIR}

Files:
{RAW_OUTPUT}
{G2_OUTPUT}
{LINKS_OUTPUT}
"""


with open(
    SUMMARY_OUTPUT,
    "w",
    encoding="utf-8"
) as f:
    f.write(summary)


print(summary)
print("Finished.")
