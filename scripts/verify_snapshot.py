import csv
from pathlib import Path

G1_FILE = Path("data/core/g1_with_field_ids.csv")
G2_FILE = Path("data/core/g2_extracted.csv")
G2_LINKS_FILE = Path("data/core/g2_parent_links.csv")
NORMALIZED_FILE = Path("data/core/field_year_normalized.csv")

EXPECTED = {
    "g1_records": 14638,
    "g1_self_citations": 261,
    "g2_records": 9332,
    "g2_parent_links": 9725,
    "normalized_rows": 198,
}


def read_csv(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    print("WOA Phase 2 - Saved Snapshot Verification")
    print("=" * 45)

    g1 = read_csv(G1_FILE)
    g2 = read_csv(G2_FILE)
    links = read_csv(G2_LINKS_FILE)
    normalized = read_csv(NORMALIZED_FILE)

    g1_ids = [row["openalex_id"].strip() for row in g1]
    g2_ids = [row["openalex_id"].strip() for row in g2]

    g1_unique = set(g1_ids)
    g2_unique = set(g2_ids)

    self_citations = sum(
        row.get("self_citation_flag", "").strip() == "True"
        for row in g1
    )

    linked_g2_ids = {
        row["g2_id"].strip()
        for row in links
        if row.get("g2_id", "").strip()
    }

    checks = {
        "G1 records": (len(g1), EXPECTED["g1_records"]),
        "Unique G1 IDs": (len(g1_unique), EXPECTED["g1_records"]),
        "G1 self-citations": (
            self_citations,
            EXPECTED["g1_self_citations"],
        ),
        "G2 records": (len(g2), EXPECTED["g2_records"]),
        "Unique G2 IDs": (len(g2_unique), EXPECTED["g2_records"]),
        "G2-parent links": (
            len(links),
            EXPECTED["g2_parent_links"],
        ),
        "G2 records with a parent link": (
            len(linked_g2_ids),
            EXPECTED["g2_records"],
        ),
        "Normalized field-year rows": (
            len(normalized),
            EXPECTED["normalized_rows"],
        ),
    }

    all_passed = True

    for label, (actual, expected) in checks.items():
        status = "PASS" if actual == expected else "FAIL"

        if status == "FAIL":
            all_passed = False

        print(
            f"{status:4} | {label}: "
            f"{actual} "
            f"(expected {expected})"
        )

    duplicate_g1 = len(g1) - len(g1_unique)
    duplicate_g2 = len(g2) - len(g2_unique)
    g2_without_parent = len(g2_unique - linked_g2_ids)

    print()
    print("Additional consistency checks")
    print("-" * 45)
    print(f"Duplicate G1 IDs: {duplicate_g1}")
    print(f"Duplicate G2 IDs: {duplicate_g2}")
    print(f"G2 records with no recorded parent: {g2_without_parent}")

    if duplicate_g1 != 0:
        all_passed = False

    if duplicate_g2 != 0:
        all_passed = False

    if g2_without_parent != 0:
        all_passed = False

    print()

    if all_passed:
        print(
            "PASS: saved snapshot matches the documented "
            "Phase 2 counts."
        )
    else:
        print(
            "FAIL: one or more saved results do not match "
            "the documented snapshot."
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
