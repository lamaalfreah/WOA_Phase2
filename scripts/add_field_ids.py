import csv
import json
from pathlib import Path

RAW_FILE = Path("data/raw/g1_raw_2026-10-04.json")
INPUT_FILE = Path("data/intermediate/g1_with_self_citation.csv")
OUTPUT_FILE = Path("data/core/g1_with_field_ids.csv")

print("Loading raw OpenAlex data...")

with open(RAW_FILE, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

field_map = {}

for work in raw_data["results"]:

    work_id = (work.get("id") or "").replace(
        "https://openalex.org/", ""
    )

    primary_topic = work.get("primary_topic") or {}
    field = primary_topic.get("field") or {}

    field_id = str(field.get("id") or "")
    field_id = field_id.replace(
        "https://openalex.org/fields/", ""
    )

    field_name = field.get("display_name") or ""

    field_map[work_id] = {
        "field_id": field_id,
        "field_name": field_name
    }


with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    fieldnames = list(reader.fieldnames)

if "field_id" not in fieldnames:
    fieldnames.insert(
        fieldnames.index("field") + 1,
        "field_id"
    )


missing_field_ids = 0

for row in rows:

    work_id = row["openalex_id"]

    info = field_map.get(work_id, {})

    field_id = info.get("field_id", "")

    row["field_id"] = field_id

    if not field_id:
        missing_field_ids += 1


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
    writer.writerows(rows)


print("Done.")
print(f"Total records: {len(rows)}")
print(f"Missing field IDs: {missing_field_ids}")
print(f"Saved to: {OUTPUT_FILE}")