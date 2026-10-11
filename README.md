# WOA Phase 2

**Data cutoff: 4 October 2026.** The submitted dataset is the OpenAlex snapshot retrieved on 4 October 2026 (G1, seed record, normalisation totals) and 6 October 2026 (G2, limited to works in OpenAlex by 4 October). Every number in the report is computed from the saved files in `data/raw`, not from live OpenAlex.

This folder contains the Phase 2 data collection and preparation work for the Whale Optimization Algorithm (WOA) citation study.

## Documentation

- `docs/cleaning_and_documentation_scripts.md`: how the cleaning, data-dictionary and workbook scripts and the cutoff tools work.
- `G4_CSC512_WOA_Phase2_Dataset.xlsx`: cleaned dataset, data dictionary, cleaning log and provenance in one workbook.

## Main data source

OpenAlex API

Seed work:
- The Whale Optimization Algorithm
- OpenAlex ID: W2290883490

## Main datasets

`data/core/g1_with_field_ids.csv`  
Direct citing works (G1), including field IDs and self-citation information.

`data/core/g2_extracted.csv`  
Second-generation citing works (G2) collected from the frozen stratified G1 sample.

`data/core/g2_parent_links.csv`  
Links each G2 work to the sampled G1 work(s) it cites.

`data/core/field_year_normalized.csv`  
Field-by-year citation counts and normalized shares, with and without seed-author self-citations.

`data/core/g1_stratified_sample_500.csv`  
The fixed 500-record G1 sample used to collect G2.

## Logs

`data/logs/query_log.txt`  
OpenAlex queries, retrieval dates, and collection settings.

`data/logs/data_quality_log.txt`  
Data-quality checks, missing metadata, self-citation counts, and validation results.

`data/logs/normalization_query_log.csv`  
OpenAlex field-year queries used for normalization.

Other log files record the G2 pilot, sampling, and collection summaries.

## Raw and intermediate files

`data/raw/`  
Original OpenAlex responses. These files are kept unchanged.

`data/intermediate/`  
Temporary datasets created between processing steps and kept for traceability.

## How to open and run the project

1. Install Python 3 if it is not already installed.
2. Install Visual Studio Code.
3. Open Visual Studio Code.
4. Select **File > Open Folder** and open the `WOA_Phase2` folder.
5. Open **Terminal > New Terminal** in VS Code.

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the required package:

```bash
pip install requests
```

## Reproduce the submitted results (no internet needed)

Run from the project root, in this order. None of these steps contacts OpenAlex: they read the saved raw files, the saved seed record (`data/raw/seed_work_info.json`) and the saved normalisation totals (`data/logs/normalization_query_log.csv`). Re-running them regenerates byte-identical files.

```bash
pip install requests pandas openpyxl
python scripts/extract_g1_metadata.py
python scripts/add_self_citation_flag.py
python scripts/add_field_ids.py
python scripts/build_field_year_with_ids.py
python scripts/normalize_field_year.py
python scripts/create_stratified_g1_sample.py
python scripts/verify_snapshot.py
python scripts/clean_and_document.py
python scripts/make_reference_tables.py
python scripts/build_workbook.py G4_CSC512_WOA_Phase2_Dataset.xlsx
```

## Re-run against live OpenAlex

OpenAlex changes every day, and its free API cannot return the database as it was on a past date (the `to_created_date` filter needs a paid plan). The retrieval scripts are therefore fixed to the 4 October 2026 cutoff as follows:

- they send exactly the snapshot query strings;
- they drop every returned work created in OpenAlex or published after 2026-10-04 (`scripts/snapshot_config.py`);
- they never overwrite the snapshot: output goes to `data/rerun/<today>/`.

To see how today's OpenAlex differs from the snapshot, run:

```bash
python scripts/compare_live_to_snapshot.py
```

It lists every differing OpenAlex ID in `data/rerun/<today>/g1_live_vs_snapshot.csv` with the reason. A run on 10 October 2026 returned 14,588 records: 23 were added to OpenAlex after the cutoff (dropped by the cutoff rule), 74 snapshot records are no longer returned (all preprints, none in the core analysis set), and 1 record that existed by the cutoff gained its citation link later (14,638 - 74 + 1 = 14,565 records within the cutoff). Add the group's e-mail to `MAILTO` in `scripts/snapshot_config.py` before any live run.

## How to verify the saved results

The saved datasets should be used when checking the submitted results. OpenAlex is updated continuously, so re-running the API queries later may return slightly different counts.

To check the main saved counts, run:

```bash
python scripts/verify_snapshot.py
```

The verification should confirm the saved Phase 2 snapshot, including the documented G1 and G2 counts.

The recorded OpenAlex queries can also be checked directly in:

```text
data/logs/query_log.txt
data/logs/normalization_query_log.csv
```

The data-quality checks are recorded in:

```text
data/logs/data_quality_log.txt
```

## Full workflow

The scripts were run in this order (the logs written at run time refer to `data/processed/`; those files now sit in `data/core/` and `data/intermediate/`, and the scripts read them from there):

```text
fetch_g1.py
→ extract_g1_metadata.py
→ add_self_citation_flag.py
→ add_field_ids.py
→ build_field_year_with_ids.py
→ normalize_field_year.py
→ estimate_g2_pilot.py
→ create_stratified_g1_sample.py
→ fetch_g2_from_stratified_sample.py
→ clean_and_document.py
→ make_reference_tables.py
→ build_workbook.py
```

The full workflow does not need to be re-run just to verify the submitted results. Re-running the retrieval scripts will query the current OpenAlex database and may produce slightly different counts.

## Recorded retrieval dates

G1: 2026-10-04  
G2: 2026-10-06

## Current recorded counts

G1 records: 14,638  
G1 self-citation records: 261  
G2 records: 9,332  
G2-parent links: 9,725
Core analysis set after cleaning: G1 13,970; G2 8,961 (see `data/clean/cleaning_log.csv`)

2026 is treated as a partial year and is not used as a complete year in growth or trend claims.