import csv
import random
from collections import defaultdict
from pathlib import Path

INPUT_FILE = Path("data/core/g1_with_field_ids.csv")

OUTPUT_SAMPLE = Path(
    "data/core/g1_stratified_sample_500.csv"
)

OUTPUT_SUMMARY = Path(
    "data/logs/g1_stratified_sample_summary.txt"
)

SAMPLE_SIZE = 500
RANDOM_SEED = 20261004

random.seed(RANDOM_SEED)


# -------------------------------------------------
# 1. Read G1
# -------------------------------------------------

with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

print(f"Total G1 records: {len(rows)}")


# -------------------------------------------------
# 2. Build strata = year x field
# -------------------------------------------------

strata = defaultdict(list)

for row in rows:

    year = row["publication_year"].strip()

    field = row["field"].strip()

    if not field:
        field = "Unknown"

    key = (year, field)

    strata[key].append(row)


print(f"Total strata: {len(strata)}")


# -------------------------------------------------
# 3. Allocate one record to every stratum first
# -------------------------------------------------

selected = []

remaining_pool = []

for key, group in strata.items():

    chosen = random.choice(group)

    selected.append(chosen)

    # remaining records from this stratum
    for row in group:
        if row["openalex_id"] != chosen["openalex_id"]:
            remaining_pool.append(row)


print(
    f"One-per-stratum allocation: "
    f"{len(selected)} records"
)


# -------------------------------------------------
# 4. Fill remaining sample proportionally
# -------------------------------------------------

remaining_needed = SAMPLE_SIZE - len(selected)

if remaining_needed < 0:
    raise ValueError(
        "SAMPLE_SIZE is smaller than number of strata."
    )

if remaining_needed > len(remaining_pool):
    remaining_needed = len(remaining_pool)

extra_sample = random.sample(
    remaining_pool,
    remaining_needed
)

selected.extend(extra_sample)


# -------------------------------------------------
# 5. Ensure uniqueness
# -------------------------------------------------

unique_selected = {}

for row in selected:
    unique_selected[row["openalex_id"]] = row

selected = list(unique_selected.values())


print(f"Final sample size: {len(selected)}")


# -------------------------------------------------
# 6. Save frozen sample
# -------------------------------------------------

fieldnames = list(selected[0].keys())

with open(
    OUTPUT_SAMPLE,
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames
    )

    writer.writeheader()
    writer.writerows(selected)


# -------------------------------------------------
# 7. Create summary
# -------------------------------------------------

year_counts = defaultdict(int)
field_counts = defaultdict(int)

for row in selected:

    year = row["publication_year"].strip()

    field = row["field"].strip() or "Unknown"

    year_counts[year] += 1
    field_counts[field] += 1


summary_lines = []

summary_lines.append(
    "G1 Frozen Stratified Sample"
)

summary_lines.append("")
summary_lines.append(
    f"Total G1 records: {len(rows)}"
)

summary_lines.append(
    f"Requested sample size: {SAMPLE_SIZE}"
)

summary_lines.append(
    f"Final sample size: {len(selected)}"
)

summary_lines.append(
    f"Random seed: {RANDOM_SEED}"
)

summary_lines.append(
    f"Number of year-field strata: {len(strata)}"
)

summary_lines.append("")
summary_lines.append(
    "Stratification variables:"
)

summary_lines.append(
    "- publication year"
)

summary_lines.append(
    "- OpenAlex field"
)

summary_lines.append("")

summary_lines.append(
    "Sampling rule:"
)

summary_lines.append(
    "At least one record was selected from every "
    "non-empty year-field stratum, then the remaining "
    "sample slots were filled randomly from the "
    "remaining G1 records using a fixed random seed."
)

summary_lines.append("")
summary_lines.append("Sample by year:")

for year in sorted(year_counts):
    summary_lines.append(
        f"{year}: {year_counts[year]}"
    )

summary_lines.append("")
summary_lines.append("Sample by field:")

for field in sorted(field_counts):
    summary_lines.append(
        f"{field}: {field_counts[field]}"
    )


summary = "\n".join(summary_lines)


with open(
    OUTPUT_SUMMARY,
    "w",
    encoding="utf-8"
) as f:

    f.write(summary)


print()
print(summary)
print()
print(f"Sample saved to: {OUTPUT_SAMPLE}")
print(f"Summary saved to: {OUTPUT_SUMMARY}")