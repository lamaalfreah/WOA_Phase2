import csv
from collections import defaultdict
from pathlib import Path

INPUT_FILE = Path(
    "data/core/g1_with_field_ids.csv"
)

OUTPUT_FILE = Path(
    "data/intermediate/field_year_counts_with_ids.csv"
)

counts = defaultdict(lambda: {
    "field_name": "",
    "with_self": 0,
    "without_self": 0
})


with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:

    reader = csv.DictReader(f)

    for row in reader:

        year = row["publication_year"].strip()
        field_id = row["field_id"].strip()
        field_name = row["field"].strip()

        self_flag = row[
            "self_citation_flag"
        ].strip()

        if not year:
            continue

        # Keep missing field separately
        if not field_id:
            field_id = "UNKNOWN"
            field_name = "Unknown"

        key = (year, field_id)

        counts[key]["field_name"] = field_name
        counts[key]["with_self"] += 1

        if self_flag != "True":
            counts[key]["without_self"] += 1


with open(
    OUTPUT_FILE,
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    fields = [
        "year",
        "field_id",
        "field",
        "count_with_self",
        "count_without_self",
        "year_status"
    ]

    writer = csv.DictWriter(
        f,
        fieldnames=fields
    )

    writer.writeheader()

    for (year, field_id), values in sorted(
        counts.items(),
        key=lambda x: (
            int(x[0][0]),
            x[1]["field_name"]
        )
    ):

        writer.writerow({
            "year": year,
            "field_id": field_id,
            "field": values["field_name"],
            "count_with_self":
                values["with_self"],
            "count_without_self":
                values["without_self"],
            "year_status":
                "partial"
                if year == "2026"
                else "complete"
        })


print(
    f"Done. Created {len(counts)} field-year rows."
)

print(f"Saved to: {OUTPUT_FILE}")