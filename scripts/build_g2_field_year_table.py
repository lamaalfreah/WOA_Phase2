import csv
from collections import defaultdict
from pathlib import Path


INPUT_FILE = Path("data/clean/g2_clean.csv")
OUTPUT_FILE = Path("data/clean/g2_field_year_core.csv")


def is_true(value):
    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "y"
    }


with open(
    INPUT_FILE,
    "r",
    encoding="utf-8-sig"
) as f:
    rows = list(csv.DictReader(f))


counts = defaultdict(
    lambda: {
        "with_seed_author": 0,
        "without_seed_author": 0
    }
)


for row in rows:

    # Only use records included in the core analysis.
    if not is_true(row.get("in_core_analysis", "")):
        continue

    year = (
        row.get("publication_year", "")
        .strip()
    )

    field = (
        row.get("field_analysis", "")
        .strip()
    )

    if not field:
        field = "Unknown"

    key = (year, field)

    counts[key]["with_seed_author"] += 1

    if not is_true(
        row.get("seed_author_flag", "")
    ):
        counts[key][
            "without_seed_author"
        ] += 1


output_rows = []

for (year, field), values in sorted(
    counts.items(),
    key=lambda x: (
        str(x[0][0]),
        str(x[0][1])
    )
):
    with_seed = values[
        "with_seed_author"
    ]

    without_seed = values[
        "without_seed_author"
    ]

    output_rows.append({
        "publication_year": year,
        "field": field,
        "g2_count_with_seed_author":
            with_seed,
        "g2_count_without_seed_author":
            without_seed,
        "seed_author_difference":
            with_seed - without_seed,
        "year_status":
            (
                "partial"
                if str(year) == "2026"
                else "complete"
            )
    })


fieldnames = [
    "publication_year",
    "field",
    "g2_count_with_seed_author",
    "g2_count_without_seed_author",
    "seed_author_difference",
    "year_status"
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


total_with = sum(
    row["g2_count_with_seed_author"]
    for row in output_rows
)

total_without = sum(
    row["g2_count_without_seed_author"]
    for row in output_rows
)

print(
    "G2 field-year table created."
)
print(
    f"Rows: {len(output_rows)}"
)
print(
    f"Core G2 with seed-author works: "
    f"{total_with}"
)
print(
    f"Core G2 without seed-author works: "
    f"{total_without}"
)
print(
    f"Difference: "
    f"{total_with - total_without}"
)
print(
    f"Saved to: {OUTPUT_FILE}"
)
