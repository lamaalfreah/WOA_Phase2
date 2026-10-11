import csv
import json
from pathlib import Path

import requests


SEED_ID = "W2290883490"

INPUT_FILE = Path("data/intermediate/g1_extracted.csv")
OUTPUT_FILE = Path("data/intermediate/g1_with_self_citation.csv")
SEED_INFO_FILE = Path("data/raw/seed_work_info.json")


# -------------------------------------------------
# 1. Fetch the original WOA paper from OpenAlex
# -------------------------------------------------

seed_url = f"https://api.openalex.org/works/{SEED_ID}"

# Use the seed record saved on 2026-10-04 if present (reproducible run);
# download it only if it is missing.
if SEED_INFO_FILE.exists():
    with open(SEED_INFO_FILE, "r", encoding="utf-8") as f:
        seed_work = json.load(f)
    print(f"Using saved seed record: {SEED_INFO_FILE}")
else:
    response = requests.get(seed_url, timeout=60)
    response.raise_for_status()
    seed_work = response.json()
    SEED_INFO_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SEED_INFO_FILE, "w", encoding="utf-8") as f:
        json.dump(seed_work, f, ensure_ascii=False, indent=2)


# -------------------------------------------------
# 2. Get seed-paper author IDs
# -------------------------------------------------

seed_authors = {}

for authorship in seed_work.get("authorships", []):
    author = authorship.get("author") or {}

    author_id = (author.get("id") or "").replace(
        "https://openalex.org/", ""
    )

    author_name = author.get("display_name") or ""

    if author_id:
        seed_authors[author_id] = author_name


print("Seed paper:")
print(seed_work.get("title"))

print("\nSeed authors:")
for author_id, author_name in seed_authors.items():
    print(f"- {author_name}: {author_id}")


seed_author_ids = set(seed_authors.keys())


# -------------------------------------------------
# 3. Read G1
# -------------------------------------------------

with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    fieldnames = list(reader.fieldnames)


# Add the new columns
if "self_citation_flag" not in fieldnames:
    fieldnames.append("self_citation_flag")

if "matched_seed_authors" not in fieldnames:
    fieldnames.append("matched_seed_authors")


# -------------------------------------------------
# 4. Compare each paper's author IDs with seed IDs
# -------------------------------------------------

self_citation_count = 0

for row in rows:

    citing_author_ids = {
        author_id.strip()
        for author_id in row.get("author_ids", "").split(";")
        if author_id.strip()
    }

    matched_ids = citing_author_ids.intersection(seed_author_ids)

    if matched_ids:
        row["self_citation_flag"] = "True"

        matched_names = [
            seed_authors[author_id]
            for author_id in sorted(matched_ids)
        ]

        row["matched_seed_authors"] = "; ".join(matched_names)

        self_citation_count += 1

    else:
        row["self_citation_flag"] = "False"
        row["matched_seed_authors"] = ""


# -------------------------------------------------
# 5. Save a NEW file
# -------------------------------------------------

with open(
    OUTPUT_FILE,
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.DictWriter(f, fieldnames=fieldnames)

    writer.writeheader()
    writer.writerows(rows)


# -------------------------------------------------
# 6. Summary
# -------------------------------------------------

print("\nFinished.")
print(f"Total G1 records: {len(rows)}")
print(f"Self-citation records: {self_citation_count}")
print(
    f"Non-self-citation records: "
    f"{len(rows) - self_citation_count}"
)
print(f"Saved to: {OUTPUT_FILE}")