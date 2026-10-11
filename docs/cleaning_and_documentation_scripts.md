# Cleaning and documentation scripts

This guide explains the scripts that turn the extracted OpenAlex tables into the cleaned dataset, the data dictionary and the workbook, and the tools that keep live re-runs fixed to the 4 October 2026 cutoff. The retrieval and extraction scripts are summarised in `README.md`.

Run everything from the project root (the folder that contains `scripts/` and `data/`).

```text
data/core + data/raw ──► clean_and_document.py ──► data/clean/*.csv
                              ▲
              manual_decisions.csv

data/clean/g2_clean.csv ──► build_g2_field_year_table.py
                         └─► data/clean/g2_field_year_core.csv

data/clean ──► make_reference_tables.py
            └─► data_dictionary.csv, provenance.csv, manual_check.csv

data/clean + reference tables ──► build_workbook.py
                               └─► G4_CSC512_WOA_Phase2_Dataset.xlsx
```

---

## 1. `clean_and_document.py`

**Purpose.** Cleans G1 and G2, finds duplicates, decides which records are counted in the core analysis, logs every decision, and builds the core field-by-year tables.

**Inputs (read only).** `data/core/g1_with_field_ids.csv`, `data/core/g2_extracted.csv`, `data/core/g2_parent_links.csv`, `data/core/field_year_normalized.csv`, the saved raw files in `data/raw/`, and `scripts/manual_decisions.csv`.

**Outputs (`data/clean/`).**

| File | Content |
|---|---|
| `g1_clean.csv`, `g2_clean.csv` | Every record, with the original columns, extra raw fields and derived columns |
| `g2_parent_links_clean.csv` | G2 → G1 links, with whether each end is in the core analysis |
| `field_year_core.csv` | Core G1 counts by field and year: all, without self-citations, without retracted works; shares per 100,000 OpenAlex works |
| `subfield_year_core.csv` | Same counts by subfield for Computer Science and Engineering |
| `cleaning_log.csv` | One row per exclusion or flag: record, rule, action, reason, related record |
| `cleaning_rules.csv` | The rules below, in words |
| `data_quality_summary.csv` | Counts of missing metadata, duplicates, exclusions and checks |

**Principles.** No record is deleted and no source value is overwritten. A record that is not counted keeps its row and gets `in_core_analysis = 0` and an `exclusion_reason`.

### Step by step

1. **Load and enrich (`prepare`, `raw_extras`).** Each generation is loaded and matched one-to-one with its saved OpenAlex records to copy fields the extraction did not keep: publication date, date the record was added to OpenAlex, retraction and open-access flags, first author, affiliation countries and the abstract (rebuilt from OpenAlex's word-position index).
2. **Derived columns (`prepare`).**
   - `doi_normalized`, `title_normalized`: lower case, no accents, HTML tags or punctuation, so small spelling differences do not hide duplicates.
   - `field_analysis`: the OpenAlex field, or `Unknown`.
   - `analysis_category`: field, or field > subfield for Computer Science and Engineering (rule F2).
   - `doc_type_group`: `core`, `excluded_type` or `assess_separately` (rules T1, T2).
   - `after_cutoff_flag`: 1 if the record was added to OpenAlex or published after 2026-10-04 (rule C1).
3. **Duplicates (`dedupe`).**
   - D1: OpenAlex IDs must be unique (checked; none found).
   - D2: records with the same normalised DOI form a group.
   - D3: records with the same normalised title, first author and year form a group. If the group is one published record plus preprints or other versions, it is resolved automatically; if it holds two core records with different DOIs it is marked `needs_manual_check`.
   - D4 (`primary_sort_key`): the record kept in a group is the core type, then the non-preprint, then the one with a DOI, then the most cited, then the oldest OpenAlex ID.
4. **Manual decisions (`apply_manual`, rule M1).** Each group in `manual_decisions.csv` is either `same work` (only the kept record stays in the analysis) or `keep both` (all stay). The decision and its evidence are written to the cleaning log with `decided_by = manual`.
5. **G2-specific checks.**
   - D5: a G2 record with the same title, first author and year as a G1 record is a version of a G1 work and is not counted as new G2 reach.
   - S3: `seed_author_flag` marks G2 works by a seed-paper author. They cite a G1 paper, not the seed, so they are not self-citations of the seed; G2 counts are also given without them.
6. **Final decision (`finalize`).** The first rule that applies gives the `exclusion_reason`, in this order: excluded type (T1), non-core type (T2), duplicate (D2/D3/M1), version of a G1 work (D5), after the cutoff (C1). Records with no reason have `in_core_analysis = 1`. Retracted works (Q1) and seed-author names with a different or missing author ID (S2) are flagged in the log but stay in the analysis.
7. **Field-by-year tables (`fy_counts`).** Numerators are recounted on the core G1 set; denominators (all OpenAlex works per field and year, queried on 4 October 2026) come from `field_year_normalized.csv`.
8. **Data-quality summary (`dq`).** Counts for G1 and G2, plus the gap between the seed's `cited_by_count` and the retrieved G1 total, and the share of G1 records that name WOA in title, abstract or keywords.

### Rules

| ID | Rule |
|---|---|
| C1 | Added to OpenAlex or published after 2026-10-04 → not counted |
| T1 | Peer-review report, paratext, retraction notice, erratum, editorial, reference entry, dataset → not counted |
| T2 | Preprint, dissertation, book, report, software paper, other → kept, counted separately |
| D1–D5 | Duplicate rules above |
| M1 | Manual decision on unresolved duplicate groups |
| F1 / F2 | Field level by default; subfields for Computer Science and Engineering |
| S1 | Self-citation = a G1 record lists author ID A5091500375 or A5063313173 (set by `add_self_citation_flag.py`) |
| S2 | Seed-author name with another or no author ID → flagged only |
| S3 | G2 work by a seed author → flagged only |
| Q1 | Retracted → kept, flagged; tables also without them |

### How to check it

- `cleaning_log.csv` has a row for every record that is not counted, with its rule.
- In the workbook, sheet `Data_Quality` recomputes the main counts with Excel formulas from `G1_clean` and `G2_clean`; the `Check` column must read `match` on every row.

---

## 2. `manual_decisions.csv`

One row per duplicate group that the rules could not resolve.

| Column | Meaning |
|---|---|
| `duplicate_group_id` | Group ID from `g1_clean.csv` / `g2_clean.csv` (e.g. `G1-D004`) |
| `decision` | `same work` or `keep both` |
| `date` | Date of the check |
| `evidence` | What was checked: DOI registration and target page at doi.org, venue, volume, issue, pages, authors, abstract |

A decision is `same work` when one publication has more than one record (two DOIs for one article, a translation, a revised version, a reprint) and `keep both` when the same title was published separately (different issues, page ranges or venues). The script stops with an error if a listed group does not exist or was not flagged for manual checking.

---

## 3. `make_reference_tables.py`

Writes three tables next to the scripts:

- `data_dictionary.csv`: every column of every sheet, with meaning, type, source field in the OpenAlex record or the rule that computes it, allowed values, raw or derived, and the script that creates it.
- `provenance.csv`: database, seed, cutoff, exact query strings, retrieval dates, what was saved from each query, request settings, script order, re-run behaviour.
- `manual_check.csv`: the records of every manually checked group, with the decision and evidence.

---
## 4. `build_g2_field_year_table.py`

Builds the G2 field-by-year comparison requested for seed-author sensitivity.

**Input:** `data/clean/g2_clean.csv`

**Output:** `data/clean/g2_field_year_core.csv`

Only records with `in_core_analysis = 1` are counted. For each publication year and analysis field, the table reports:

- `g2_count_with_seed_author`: all core G2 records.
- `g2_count_without_seed_author`: the same records after excluding works with `seed_author_flag = 1`.
- `seed_author_difference`: the difference between the two counts.
- `year_status`: 2026 is labelled `partial`.

The seed-author flag is not called a self-citation in G2 because a G2 work cites a sampled G1 work rather than the original WOA seed paper.

```bash
python scripts/build_g2_field_year_table.py
```
---
## 5. `build_workbook.py`

Assembles `G4_CSC512_WOA_Phase2_Dataset.xlsx`:

| Sheet | Content |
|---|---|
| README | What each sheet holds; header colours |
| G1_clean, G2_clean | Cleaned records. Blue header = copied from OpenAlex; orange header = derived |
| G2_parent_links | G2 → G1 links |
| Field_Year_All | Normalised field-by-year table on all G1 records |
| Field_Year_Core | Same on the core set, also without retracted works |
| G2_Field_Year_Core | Core G2 counts by field and year, with and without seed-author works |
| Subfield_Year_Core | Subfield counts for Computer Science and Engineering |
| Cleaning_Rules, Cleaning_Log | Rules and every action |
| Manual_Check | Manually checked groups with decision and evidence |
| Data_Quality | Counts recomputed by formula next to the script values |
| Data_Dictionary, Provenance | Column definitions; sources, queries and dates |

```bash
python scripts/build_workbook.py G4_CSC512_WOA_Phase2_Dataset.xlsx
```

---

## 6. Cutoff and live re-run tools

OpenAlex changes over time, so the submitted analysis remains tied to the saved 4 October 2026 snapshot.

`snapshot_config.py` stores the cutoff date and shared helpers used by the retrieval scripts.

Any new live retrieval is kept separate from the submitted snapshot. Complete OpenAlex JSON responses are saved under:

`data/rerun/<date>/pages/`

This applies to:

- `fetch_g1.py`
- `fetch_g2_from_stratified_sample.py`
- `normalize_field_year.py`
- `compare_live_to_snapshot.py`

The submitted files in `data/raw/`, `data/core/` and `data/clean/` are not overwritten by verification re-runs.

`compare_live_to_snapshot.py` re-runs the G1 query and compares the live OpenAlex results with the submitted snapshot by OpenAlex ID. It records records that are newly returned, no longer returned, or outside the declared cutoff. Its outputs are stored in `data/rerun/<date>/`.

The full JSON response for every live G1 page and the seed-work response are also cached in `data/rerun/<date>/pages/`.
