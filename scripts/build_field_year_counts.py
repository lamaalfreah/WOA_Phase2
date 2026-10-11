import csv
from collections import defaultdict
from pathlib import Path

INPUT_FILE = Path("data/intermediate/g1_with_self_citation.csv")
OUTPUT_FILE = Path("data/intermediate/field_year_counts.csv")

counts = defaultdict(lambda: {
    "with_self": 0,
    "without_self": 0
})

with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)

    for row in reader:
        year = row.get("publication_year", "").strip()
        field = row.get("field", "").strip()
        self_flag = row.get("self_citation_flag", "").strip()

        # Skip rows with no usable year
        if not year:
            continue

        # Keep missing field explicitly as Unknown
        if not field:
            field = "Unknown"

        key = (year, field)

        counts[key]["with_self"] += 1

        if self_flag != "True":
            counts[key]["without_self"] += 1


OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
    fieldnames = [
        "year",
        "field",
        "count_with_self",
        "count_without_self",
        "year_status"
    ]

    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()

    for (year, field), values in sorted(
        counts.items(),
        key=lambda x: (int(x[0][0]), x[0][1])
    ):
        writer.writerow({
            "year": year,
            "field": field,
            "count_with_self": values["with_self"],
            "count_without_self": values["without_self"],
            "year_status": (
                "partial" if year == "2026" else "complete"
            )
        })


print(f"Done. Created {len(counts)} field-year rows.")
print(f"Saved to: {OUTPUT_FILE}")