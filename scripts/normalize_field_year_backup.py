import csv
import time
from pathlib import Path

import requests

from snapshot_config import with_mailto

# Field totals already retrieved on 2026-10-04 are read from LOG_FILE, so a
# re-run reproduces the submitted table without new API queries.


INPUT_FILE = Path(
    "data/intermediate/field_year_counts_with_ids.csv"
)

OUTPUT_FILE = Path(
    "data/core/field_year_normalized.csv"
)

LOG_FILE = Path(
    "data/logs/normalization_query_log.csv"
)

BASE_URL = "https://api.openalex.org/works"

MAX_RETRIES = 6


def fetch_count_with_retry(year, field_id):
    filter_string = (
        f"publication_year:{year},"
        f"primary_topic.field.id:{field_id}"
    )

    params = {
        "filter": filter_string,
        "per_page": 1
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                BASE_URL,
                params=with_mailto(params),
                timeout=60
            )

            # Success
            if response.status_code == 200:
                data = response.json()
                return (
                    data["meta"]["count"],
                    response.url
                )

            # Temporary server/rate-limit errors
            if response.status_code == 429 or response.status_code >= 500:
                wait_seconds = 2 ** attempt

                print(
                    f"Temporary error {response.status_code}. "
                    f"Retrying in {wait_seconds}s..."
                )

                time.sleep(wait_seconds)
                continue

            # Other errors: stop
            response.raise_for_status()

        except requests.exceptions.Timeout:
            wait_seconds = 2 ** attempt

            print(
                f"Request timed out. "
                f"Retrying in {wait_seconds}s..."
            )

            time.sleep(wait_seconds)

        except requests.exceptions.ConnectionError:
            wait_seconds = 2 ** attempt

            print(
                f"Connection error. "
                f"Retrying in {wait_seconds}s..."
            )

            time.sleep(wait_seconds)

    raise RuntimeError(
        f"Failed after {MAX_RETRIES} retries: "
        f"year={year}, field_id={field_id}"
    )


# -----------------------------------------
# Read input
# -----------------------------------------

with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))


# -----------------------------------------
# Load already completed queries if present
# -----------------------------------------

completed = {}

if LOG_FILE.exists():
    with open(LOG_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            key = (
                row["year"],
                row["field_id"]
            )

            completed[key] = row


print(f"Previously completed queries: {len(completed)}")


# -----------------------------------------
# Prepare log file
# -----------------------------------------

log_fields = [
    "year",
    "field_id",
    "field",
    "query",
    "total_openalex_field_output"
]

if not LOG_FILE.exists():
    with open(
        LOG_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=log_fields
        )

        writer.writeheader()


output_rows = []


# -----------------------------------------
# Process field-year combinations
# -----------------------------------------

for index, row in enumerate(rows, start=1):

    year = row["year"]
    field_id = row["field_id"]
    field_name = row["field"]

    key = (year, field_id)

    print(
        f"[{index}/{len(rows)}] "
        f"{year} - {field_name}"
    )


    # Unknown fields cannot be normalized
    if field_id == "UNKNOWN":

        total_field_output = ""
        normalized_with = ""
        normalized_without = ""

        query = (
            "NOT QUERIED - "
            "missing field classification"
        )


    # Already retrieved previously
    elif key in completed:

        saved = completed[key]

        total_field_output = int(
            saved["total_openalex_field_output"]
        )

        query = saved["query"]

        count_with = int(
            row["count_with_self"]
        )

        count_without = int(
            row["count_without_self"]
        )

        normalized_with = (
            count_with / total_field_output
            if total_field_output > 0
            else ""
        )

        normalized_without = (
            count_without / total_field_output
            if total_field_output > 0
            else ""
        )

        print("  Already completed - using cached result.")


    # New query
    else:

        total_field_output, query = fetch_count_with_retry(
            year,
            field_id
        )

        count_with = int(
            row["count_with_self"]
        )

        count_without = int(
            row["count_without_self"]
        )

        normalized_with = (
            count_with / total_field_output
            if total_field_output > 0
            else ""
        )

        normalized_without = (
            count_without / total_field_output
            if total_field_output > 0
            else ""
        )

        # Save immediately to log
        log_row = {
            "year": year,
            "field_id": field_id,
            "field": field_name,
            "query": query,
            "total_openalex_field_output":
                total_field_output
        }

        with open(
            LOG_FILE,
            "a",
            newline="",
            encoding="utf-8-sig"
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=log_fields
            )

            writer.writerow(log_row)

        completed[key] = log_row

        # Small delay between successful calls
        time.sleep(0.3)


    new_row = dict(row)

    new_row[
        "total_openalex_field_output"
    ] = total_field_output

    new_row[
        "normalized_share_with_self"
    ] = normalized_with

    new_row[
        "normalized_share_without_self"
    ] = normalized_without

    output_rows.append(new_row)


# -----------------------------------------
# Save final normalized dataset
# -----------------------------------------

fieldnames = list(rows[0].keys()) + [
    "total_openalex_field_output",
    "normalized_share_with_self",
    "normalized_share_without_self"
]


with open(
    OUTPUT_FILE,
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames
    )

    writer.writeheader()
    writer.writerows(output_rows)


print()
print("Normalization finished.")
print(f"Rows processed: {len(output_rows)}")
print(f"Saved to: {OUTPUT_FILE}")
print(f"Query log: {LOG_FILE}")