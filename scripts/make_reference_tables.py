"""Writes data_dictionary.csv, provenance.csv and manual_check.csv
next to this script. Run from the WOA_Phase2 root after clean_and_document.py."""
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
L, S = "retrieval/extraction scripts", "clean_and_document.py"
OA = "OpenAlex work record: "

rows = []


def add(tables, column, meaning, typ, source, rd, allowed="", notes="", by=L):
    for t in tables.split(","):
        rows.append(dict(sheet=t, column=column, meaning=meaning, type=typ, source=source,
                         raw_or_derived=rd, allowed_values_or_format=allowed, notes=notes, created_by=by))


G = "G1_clean,G2_clean"
add(G, "openalex_id", "Persistent OpenAlex work ID (primary key)", "text", OA + "id (URL prefix removed)", "raw", "W followed by digits", "Unique in each sheet")
add(G, "doi", "Digital Object Identifier as a URL", "text", OA + "doi", "raw", "https://doi.org/...; blank if none")
add(G, "title", "Work title as indexed", "text", OA + "title", "raw", "", "May contain inline HTML or non-English text")
add(G, "publication_year", "Year of publication", "integer", OA + "publication_year", "raw", "2016-2026")
add(G, "venue", "Journal, proceedings or repository name", "text", OA + "primary_location.source.display_name", "raw", "blank if no source")
add(G, "field", "OpenAlex field of the primary topic", "text", OA + "primary_topic.field.display_name", "raw", "26 OpenAlex fields; blank if unclassified")
add(G, "field_id", "Numeric OpenAlex field ID", "text", OA + "primary_topic.field.id", "raw", "11-36", "Stored as text; '.0' suffix from CSV float conversion removed")
add(G, "subfield", "OpenAlex subfield of the primary topic", "text", OA + "primary_topic.subfield.display_name", "raw")
add(G, "domain", "OpenAlex domain of the primary topic", "text", OA + "primary_topic.domain.display_name", "raw", "Physical, Social, Health, Life Sciences")
add(G, "keywords", "OpenAlex-assigned keywords", "text", OA + "keywords[].display_name", "raw", "separated by '; '")
add(G, "citation_count", "Times this work is cited, on the retrieval date", "integer", OA + "cited_by_count", "raw", ">= 0", "Changes over time; valid only for the retrieval date")
add(G, "authors", "Author display names in byline order", "text", OA + "authorships[].author.display_name", "raw", "separated by '; '")
add(G, "author_ids", "OpenAlex author IDs", "text", OA + "authorships[].author.id", "raw", "separated by '; '",
    "Authors without an ID are skipped, so positions may not line up with 'authors'")
add(G, "publication_type", "OpenAlex document type", "text", OA + "type", "raw", "article, conference-paper, review, book-chapter, preprint, ...")
add(G, "language", "Detected language code", "text", OA + "language", "raw", "ISO 639-1 code; blank if unknown")
add(G, "generation", "Citation generation", "text", "Set by retrieval script", "derived", "G1 or G2")
add(G, "retrieval_date", "Date the record was downloaded", "date", "Retrieval script", "derived", "2026-10-04 (G1), 2026-10-06 (G2)")
add(G, "year_status", "Whether the publication year is complete", "text", "Rule: 2026 = partial", "derived", "complete / partial")
add("G1_clean", "self_citation_flag", "Citing work has a seed-paper author", "boolean", "Rule S1: author_ids contains A5091500375 or A5063313173", "derived", "TRUE / FALSE")
add("G1_clean", "matched_seed_authors", "Which seed author(s) matched", "text", "Rule S1", "derived", "Seyedali Mirjalili; Andrew Lewis")
add(G, "publication_date", "Full publication date", "date", OA + "publication_date", "raw", "YYYY-MM-DD", by=S)
add(G, "openalex_created_date", "Date the record was added to OpenAlex", "date", OA + "created_date", "raw", "YYYY-MM-DD", "Used for the cutoff rule C1", by=S)
add(G, "is_retracted", "OpenAlex marks the work as retracted", "boolean", OA + "is_retracted", "raw", "TRUE / FALSE", by=S)
add(G, "is_open_access", "Work has an open-access copy", "boolean", OA + "open_access.is_oa", "raw", "TRUE / FALSE", by=S)
add(G, "first_author_name", "First author's display name", "text", OA + "authorships[0].author.display_name", "raw", by=S)
add(G, "first_author_id", "First author's OpenAlex ID", "text", OA + "authorships[0].author.id", "raw", "A followed by digits; blank if none", by=S)
add(G, "author_countries", "Distinct countries of the authors' affiliations", "text", OA + "authorships[].countries", "raw", "ISO 3166-1 alpha-2 codes, ';' separated",
    "Affiliation country, not where the work was applied", by=S)
add(G, "abstract", "Abstract text", "text", OA + "abstract_inverted_index, rebuilt word by word", "raw", "blank if not indexed", by=S)
add(G, "seed_author_name_without_seed_id", "A seed-author name appears with a different or missing author ID", "text", "Rule S2, from authorships", "derived",
    "blank, or name (ID)", "Flag only; self_citation_flag is not changed", by=S)
add(G, "abstract_available", "Abstract present", "integer", "abstract is not blank", "derived", "1 / 0", by=S)
add(G, "doi_normalized", "DOI in lower case without the https://doi.org/ prefix", "text", "From doi", "derived", "", "Used for rule D2", by=S)
add(G, "title_normalized", "Title lower-cased, accents and punctuation removed", "text", "From title", "derived", "", "Used for rules D3 and D5", by=S)
add(G, "field_analysis", "Field used in analysis", "text", "Rule F1: field, or 'Unknown' if blank", "derived", "26 fields + Unknown", by=S)
add(G, "analysis_category", "Field, or field > subfield for Computer Science and Engineering", "text", "Rule F2", "derived", by=S)
add(G, "doc_type_group", "Document-type group", "text", "Rules T1/T2 from publication_type", "derived", "core / assess_separately / excluded_type", by=S)
add(G, "after_cutoff_flag", "Created or published after the 4 Oct 2026 cutoff", "integer", "Rule C1", "derived", "1 / 0", by=S)
add(G, "duplicate_group_id", "ID of the duplicate group the record belongs to", "text", "Rules D2/D3", "derived", "G1-D### / G2-D###; blank if none", by=S)
add(G, "duplicate_rule", "Rule that formed the group", "text", "Rules D2/D3", "derived", "D2 (DOI) / D3 (title+first author+year)", by=S)
add(G, "duplicate_of", "OpenAlex ID of the record kept for this group", "text", "Rule D4", "derived", "blank if this record is the kept one", by=S)
add(G, "duplicate_confidence", "Confidence that the group is one work", "text", "Rules D3, M1", "derived", "high / manual_same_work / manual_distinct / needs_manual_check", by=S)
add("G2_clean", "seed_author_flag", "G2 work has a seed-paper author (Mirjalili or Lewis)", "boolean", "Rule S3: author_ids contains A5091500375 or A5063313173", "derived", "TRUE / FALSE", "Flag only; G2 works cite G1 papers, not the seed", by=S)
add("G2_clean", "possible_version_of_g1", "G1 record with the same title, first author and year", "text", "Rule D5", "derived", "OpenAlex ID or blank", by=S)
add(G, "exclusion_reason", "Why the record is not in the core analysis", "text", "First applicable of rules T1, T2, D2-D5, C1", "derived", "blank if included", by=S)
add(G, "in_core_analysis", "Record is counted in core analysis tables", "integer", "exclusion_reason is blank", "derived", "1 / 0", by=S)

add("G2_parent_links", "g2_id", "Citing (child) G2 work", "text", "fetch_g2_from_stratified_sample.py", "raw", "OpenAlex ID")
add("G2_parent_links", "parent_g1_id", "Cited (parent) work from the frozen G1 sample", "text", "fetch_g2_from_stratified_sample.py", "raw", "OpenAlex ID",
    "Direction stored child -> parent")
add("G2_parent_links", "g2_in_core_analysis", "Child is in G2 core analysis", "integer", "Lookup in G2_clean", "derived", "1 / 0", by=S)
add("G2_parent_links", "parent_in_core_analysis", "Parent is in G1 core analysis", "integer", "Lookup in G1_clean", "derived", "1 / 0", by=S)

FA = "Field_Year_All"
add(FA, "year", "Publication year", "integer", "G1", "derived", "2016-2026")
add(FA, "field_id", "OpenAlex field ID", "text", "G1", "raw", "or UNKNOWN")
add(FA, "field", "OpenAlex field name", "text", "G1", "raw")
add(FA, "count_with_self", "G1 records in this field and year, all records", "integer", "normalize_field_year.py", "derived")
add(FA, "count_without_self", "Same, excluding self-citations (rule S1)", "integer", "normalize_field_year.py", "derived")
add(FA, "year_status", "complete / partial", "text", "Rule: 2026 = partial", "derived")
add(FA, "total_openalex_field_output", "All OpenAlex works in this field and year (denominator)", "integer",
    "API: /works?filter=publication_year:Y,primary_topic.field.id:F (meta.count), 4 Oct 2026", "raw", "", "Blank for Unknown field")
add(FA, "normalized_share_with_self", "count_with_self / total_openalex_field_output", "decimal", "normalize_field_year.py", "derived")
add(FA, "normalized_share_without_self", "count_without_self / total_openalex_field_output", "decimal", "normalize_field_year.py", "derived")

FC = "Field_Year_Core"
add(FC, "year", "Publication year", "integer", "G1_clean", "derived", "2016-2026", by=S)
add(FC, "field", "field_analysis", "text", "G1_clean", "derived", by=S)
add(FC, "count_with_self", "Core-analysis G1 records in this field and year", "integer", "G1_clean where in_core_analysis = 1", "derived", by=S)
add(FC, "count_without_self", "Same, excluding self-citations", "integer", "self_citation_flag = FALSE", "derived", by=S)
add(FC, "count_without_retracted", "Same as count_with_self, excluding retracted works", "integer", "is_retracted = FALSE", "derived", by=S)
add(FC, "total_openalex_field_output", "Denominator, copied from Field_Year_All", "integer", "Field_Year_All", "raw", "",
    "Counts all OpenAlex document types, while the numerator counts core types only", by=S)
add(FC, "share_per_100k_with_self", "WOA citers per 100,000 OpenAlex works in this field and year", "decimal", "count_with_self / total x 100,000", "derived", by=S)
add(FC, "share_per_100k_without_self", "Same, without self-citations", "decimal", "count_without_self / total x 100,000", "derived", by=S)
add(FC, "year_status", "complete / partial", "text", "Rule: 2026 = partial", "derived", by=S)
SF = "Subfield_Year_Core"
add(SF, "year", "Publication year", "integer", "G1_clean", "derived", by=S)
add(SF, "field > subfield", "analysis_category for Computer Science and Engineering", "text", "Rule F2", "derived", by=S)
for c, m in [("count_with_self", "core records"), ("count_without_self", "core records without self-citations"),
             ("count_without_retracted", "core records without retracted works")]:
    add(SF, c, m, "integer", "G1_clean", "derived", by=S)
add(SF, "year_status", "complete / partial", "text", "Rule: 2026 = partial", "derived", by=S)
G2FY = "G2_Field_Year_Core"

add(
    G2FY,
    "publication_year",
    "Publication year",
    "integer",
    "G2_clean where in_core_analysis = 1",
    "derived",
    "2016-2026",
    by="build_g2_field_year_table.py",
)

add(
    G2FY,
    "field",
    "Analysis field used for G2 field-year grouping",
    "text",
    "G2_clean: field_analysis",
    "derived",
    "",
    "Blank values represented as Unknown",
    by="build_g2_field_year_table.py",
)

add(
    G2FY,
    "g2_count_with_seed_author",
    "Core-analysis G2 records in this field and year including seed-author works",
    "integer",
    "G2_clean where in_core_analysis = 1",
    "derived",
    ">= 0",
    by="build_g2_field_year_table.py",
)

add(
    G2FY,
    "g2_count_without_seed_author",
    "Core-analysis G2 records in this field and year excluding works authored by a seed-paper author",
    "integer",
    "G2_clean where in_core_analysis = 1 and seed_author_flag = FALSE",
    "derived",
    ">= 0",
    by="build_g2_field_year_table.py",
)

add(
    G2FY,
    "seed_author_difference",
    "Difference between G2 counts with and without seed-author works",
    "integer",
    "g2_count_with_seed_author - g2_count_without_seed_author",
    "derived",
    ">= 0",
    by="build_g2_field_year_table.py",
)

add(
    G2FY,
    "year_status",
    "complete / partial",
    "text",
    "Rule: 2026 = partial",
    "derived",
    "complete / partial",
    by="build_g2_field_year_table.py",
)
CL = "Cleaning_Log"
for c, m, a in [("record_id", "OpenAlex ID affected", ""), ("generation", "G1 or G2", ""),
                ("rule_id", "Rule applied (see Cleaning_Rules)", "C1, T1, T2, D2, D3, D5, M1, Q1, S2"),
                ("action", "What was done", "exclude_from_core_analysis / keep / flag_only"),
                ("reason", "Plain-language reason", ""), ("related_record", "Kept or matching record, if any", ""),
                ("decided_by", "rule, or manual review", "rule / manual"), ("date", "Date of the cleaning run", "YYYY-MM-DD")]:
    add(CL, c, m, "text", "clean_and_document.py", "derived", a, by=S)

pd.DataFrame(rows).to_csv(HERE / "data_dictionary.csv", index=False)

# ------------------------------------------------------------------ provenance
prov = [
    ("Database", "OpenAlex (https://openalex.org), public REST API https://api.openalex.org"),
    ("Seed work", "Mirjalili S., Lewis A. (2016). The Whale Optimization Algorithm. Advances in Engineering Software 95, 51-67. DOI 10.1016/j.advengsoft.2016.01.008. OpenAlex ID W2290883490"),
    ("Seed authors (OpenAlex IDs)", "Seyedali Mirjalili A5091500375; Andrew Lewis A5063313173"),
    ("Data cutoff", "4 October 2026. Works created in OpenAlex or published after this date are flagged and kept out of the core analysis (rule C1)."),
    ("G1 query", "GET https://api.openalex.org/works?filter=cites:W2290883490,publication_year:2016-2026&per_page=100&cursor=* (all next_cursor pages followed)"),
    ("G1 retrieval date", "4 October 2026 - 14,638 records; raw file data/raw/g1_raw_2026-10-04.json"),
    ("Seed record", "GET https://api.openalex.org/works/W2290883490 on 4 October 2026 - cited_by_count 14,692; raw file data/raw/seed_work_info.json"),
    ("Normalisation queries", "GET https://api.openalex.org/works?filter=publication_year:Y,primary_topic.field.id:F&per_page=1 (meta.count) for each field-year in G1; 4 October 2026; listed in data/logs/normalization_query_log.csv"),
    ("G2 pilot", "100 random G1 records (seed 20261004), batches of 25; 4 October 2026; data/raw/g2_pilot_raw_2026-10-04.json. Estimated full G2 about 218,000 works, so the stratified-sample fallback was used."),
    ("G2 sample", "500 G1 records stratified by publication year x field, at least one per non-empty stratum (198 strata), rest random; seed 20261004; data/core/g1_stratified_sample_500.csv"),
    ("G2 query", "GET https://api.openalex.org/works?filter=cites:<25 sampled G1 IDs joined by |>,publication_year:2016-2026&per_page=100&cursor=*"),
    ("G2 retrieval date", "6 October 2026 - 11,835 unique works reached, 9,332 after removing all G1 works; raw file data/raw/g2_stratified_raw_2026-10-06.json"),
    ("Request settings", "100 records per page. G1: 0.2 s pause between pages; the script stops on any error. G2 and normalisation: 0.25-0.3 s pause; on HTTP 429, 5xx or timeout the request is retried after 2^attempt seconds (G2: up to 6 tries). Requests did not include a mailto parameter. Cached raw files are reused instead of re-querying."),
    ("Script order", "fetch_g1 -> extract_g1_metadata -> add_self_citation_flag -> add_field_ids -> build_field_year_with_ids -> normalize_field_year -> estimate_g2_pilot -> create_stratified_g1_sample -> fetch_g2_from_stratified_sample -> clean_and_document -> make_reference_tables -> build_workbook"),
    ("Cleaning run", "9 October 2026, clean_and_document.py; reads data/core and data/raw, writes data/clean; never edits raw or core files"),
    ("Raw-file storage", "data/raw/ in the WOA_Phase2 project folder (shared group folder); kept unchanged"),
    ("Re-runs fixed to the cutoff", "Retrieval scripts send the snapshot query strings unchanged, drop works created in OpenAlex or published after 2026-10-04 (scripts/snapshot_config.py), and write to data/rerun/<date>/ so the snapshot is never overwritten. compare_live_to_snapshot.py lists every difference by OpenAlex ID."),
    ("Live check, 10 Oct 2026", "The G1 query returned 14,588 records: 23 added after the cutoff (dropped by rule C1); 74 snapshot records no longer returned (all preprints, none in the core analysis set); 1 record that existed by the cutoff gained its citation link later. 14,638 - 74 + 1 = 14,565 within the cutoff. Seed cited_by_count 14,642."),
    ("Earlier snapshot", "Phase 1 G1 retrieval on 19 September 2026 returned 14,541 records; Phase 2 replaces it with the 4 October 2026 snapshot"),
]
pd.DataFrame(prov, columns=["item", "value"]).to_csv(HERE / "provenance.csv", index=False)

# ------------------------------------------------------------------ manual check
DEC = pd.read_csv(HERE / "manual_decisions.csv").set_index("duplicate_group_id")
out = []
for gen in ("g1", "g2"):
    d = pd.read_csv(f"data/clean/{gen}_clean.csv", low_memory=False)
    m = d[d.duplicate_confidence.isin(["needs_manual_check", "manual_same_work", "manual_distinct"])].sort_values(["duplicate_group_id", "openalex_id"])
    for _, r in m.iterrows():
        out.append({"duplicate_group_id": r.duplicate_group_id, "openalex_id": r.openalex_id,
                    "publication_type": r.publication_type, "publication_year": r.publication_year,
                    "doi": r.doi, "venue": r.venue, "title": r.title, "citation_count": r.citation_count,
                    "decision": DEC.decision.get(r.duplicate_group_id, ""),
                    "evidence": DEC.evidence.get(r.duplicate_group_id, "")})
pd.DataFrame(out).to_csv(HERE / "manual_check.csv", index=False)
print(len(rows), "dictionary rows;", len(out), "manual-check rows")
