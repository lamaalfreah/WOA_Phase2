import json
import csv
from pathlib import Path

INPUT_FILE = Path("data/raw/g1_raw_2026-10-04.json")
OUTPUT_FILE = Path("data/intermediate/g1_extracted.csv")

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

results = data["results"]

fieldnames = [
    "openalex_id",
    "doi",
    "title",
    "publication_year",
    "venue",
    "field",
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
    "year_status",
]

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()

    for work in results:
        openalex_id = work.get("id", "").replace("https://openalex.org/", "")

        doi = work.get("doi") or ""

        title = work.get("title") or ""

        publication_year = work.get("publication_year") or ""

        citation_count = work.get("cited_by_count") or 0

        publication_type = work.get("type") or ""

        language = work.get("language") or ""

        primary_location = work.get("primary_location") or {}
        source = primary_location.get("source") or {}
        venue = source.get("display_name") or ""

        primary_topic = work.get("primary_topic") or {}

        field = ""
        subfield = ""
        domain = ""

        if primary_topic:
            field_obj = primary_topic.get("field") or {}
            subfield_obj = primary_topic.get("subfield") or {}
            domain_obj = primary_topic.get("domain") or {}

            field = field_obj.get("display_name") or ""
            subfield = subfield_obj.get("display_name") or ""
            domain = domain_obj.get("display_name") or ""

        keywords_list = work.get("keywords") or []
        keywords = "; ".join(
            kw.get("display_name", "")
            for kw in keywords_list
            if kw.get("display_name")
        )

        authorships = work.get("authorships") or []

        authors = "; ".join(
            auth.get("author", {}).get("display_name", "")
            for auth in authorships
            if auth.get("author")
        )

        author_ids = "; ".join(
            auth.get("author", {}).get("id", "").replace(
                "https://openalex.org/", ""
            )
            for auth in authorships
            if auth.get("author", {}).get("id")
        )

        year_status = (
            "partial"
            if publication_year == 2026
            else "complete"
        )

        writer.writerow({
            "openalex_id": openalex_id,
            "doi": doi,
            "title": title,
            "publication_year": publication_year,
            "venue": venue,
            "field": field,
            "subfield": subfield,
            "domain": domain,
            "keywords": keywords,
            "citation_count": citation_count,
            "authors": authors,
            "author_ids": author_ids,
            "publication_type": publication_type,
            "language": language,
            "generation": "G1",
            "retrieval_date": data.get("retrieval_date", ""),
            "year_status": year_status,
        })

print(f"Done. Extracted {len(results)} records.")
print(f"Saved to: {OUTPUT_FILE}")