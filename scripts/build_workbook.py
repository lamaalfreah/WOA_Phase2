"""Assemble the Phase 2 dataset workbook from data/clean and data/core.
Run from the WOA_Phase2 project root after clean_and_document.py."""
import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUT_XLSX = Path(sys.argv[1] if len(sys.argv) > 1 else "G4_CSC512_WOA_Phase2_Dataset.xlsx")
CLEAN, CORE = Path("data/clean"), Path("data/core")

FONT = "Arial"
HDR_FILL = PatternFill("solid", fgColor="1F3A5F")
RAW_FILL = PatternFill("solid", fgColor="DCE6F1")      # header of columns copied from OpenAlex
DER_FILL = PatternFill("solid", fgColor="FCE4D6")      # header of derived columns
INPUT_FILL = PatternFill("solid", fgColor="FFFF00")
thin = Side(style="thin", color="BFBFBF")

g1 = pd.read_csv(CLEAN / "g1_clean.csv", low_memory=False, dtype={"field_id": "string"})
g2 = pd.read_csv(CLEAN / "g2_clean.csv", low_memory=False, dtype={"field_id": "string"})
links = pd.read_csv(CLEAN / "g2_parent_links_clean.csv")
fy_all = pd.read_csv(CORE / "field_year_normalized.csv")
fy_core = pd.read_csv(CLEAN / "field_year_core.csv")
sf_core = pd.read_csv(CLEAN / "subfield_year_core.csv")
g2_fy = pd.read_csv(CLEAN / "g2_field_year_core.csv")
rules = pd.read_csv(CLEAN / "cleaning_rules.csv")
log = pd.read_csv(CLEAN / "cleaning_log.csv")
dq = pd.read_csv(CLEAN / "data_quality_summary.csv")
dd = pd.read_csv(Path(__file__).parent / "data_dictionary.csv")
prov = pd.read_csv(Path(__file__).parent / "provenance.csv")
manual = pd.read_csv(Path(__file__).parent / "manual_check.csv")

for d in (g1, g2):
    d["field_id"] = d["field_id"].str.replace(r"\.0$", "", regex=True)

DERIVED = set(dd[dd.raw_or_derived == "derived"].column)

wb = Workbook()
wb.remove(wb.active)


def clean(v):
    if v is None or v is pd.NA or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, str):
        return ILLEGAL_CHARACTERS_RE.sub("", v)
    if hasattr(v, "item"):
        return v.item()
    return v


def put_df(
    name,
    df,
    widths=None,
    colour_headers=False,
    wrap_cols=(),
    freeze="A2"
):
    ws = wb.create_sheet(name)

    columns = list(df.columns)
    ws.append(columns)

    for row_number, row in enumerate(
        df.itertuples(index=False, name=None),
        start=2
    ):
        values = [clean(v) for v in row]
        ws.append(values)

        for column_number, value in enumerate(
            values,
            start=1
        ):
            if (
                isinstance(value, str)
                and value.startswith("=")
            ):
                ws.cell(
                    row=row_number,
                    column=column_number
                ).data_type = "s"

    for j, col_name in enumerate(columns, 1):
        c = ws.cell(row=1, column=j)

        if colour_headers:
            c.fill = (
                DER_FILL
                if col_name in DERIVED
                else RAW_FILL
            )
            c.font = Font(
                name=FONT,
                bold=True,
                color="000000"
            )
        else:
            c.fill = HDR_FILL
            c.font = Font(
                name=FONT,
                bold=True,
                color="FFFFFF"
            )

        c.alignment = Alignment(
            wrap_text=True,
            vertical="top"
        )

        w = (widths or {}).get(
            col_name,
            min(
                max(len(str(col_name)) + 2, 12),
                40
            )
        )

        ws.column_dimensions[
            get_column_letter(j)
        ].width = w

    for j, col_name in enumerate(columns, 1):
        if col_name in wrap_cols:
            for r in range(2, len(df) + 2):
                ws.cell(
                    row=r,
                    column=j
                ).alignment = Alignment(
                    wrap_text=True,
                    vertical="top"
                )

    ws.freeze_panes = freeze
    ws.auto_filter.ref = ws.dimensions

    return ws

def set_font(ws):
    for row in ws.iter_rows():
        for c in row:
            if c.font is None or c.font.name != FONT:
                c.font = Font(name=FONT, bold=c.font.bold if c.font else False,
                              color=c.font.color if c.font else None, size=c.font.sz if c.font else 10)


# ---------------------------------------------------------------- README
ws = wb.create_sheet("README")
readme = [
    ("WOA Phase 2 - cleaned dataset package", True),
    ("CSC512 Algorithms Analysis & Design, King Saud University, Fall 2026 - Group 4", False),
    ("", False),
    ("Source: OpenAlex API. Seed work W2290883490 (Mirjalili & Lewis 2016, DOI 10.1016/j.advengsoft.2016.01.008).", False),
    ("Data cutoff: 4 October 2026. G1 retrieved 4 Oct 2026; G2 retrieved 6 Oct 2026 and limited to works in OpenAlex by 4 Oct (rule C1).", False),
    ("2026 is a partial year: kept in every table, labelled 'partial', and excluded from growth or trend claims.", False),
    ("", False),
    ("Sheets", True),
    ("G1_clean - all 14,638 direct citers of the seed. Nothing deleted; in_core_analysis = 1 marks records counted in core tables.", False),
    ("G2_clean - 9,332 second-generation works reached from a frozen stratified sample of 500 G1 records (seed 20261004).", False),
    ("G2_parent_links - one row per G2 -> sampled-G1 citation link.", False),
    ("Field_Year_All - normalised field-by-year table on all G1 records (normalize_field_year.py) (with and without self-citations).", False),
    ("Field_Year_Core - same, on the core-analysis set; also without retracted works. share_per_100k = WOA citers per 100,000 OpenAlex works in that field and year.", False),
    ("G2_Field_Year_Core - G2 core counts by publication year and field, shown with and without seed-author works.", False),
    ("Subfield_Year_Core - subfield counts for Computer Science and Engineering (rule F2). No denominators were retrieved at subfield level.", False),
    ("Cleaning_Rules, Cleaning_Log - every rule, and every flag/exclusion with its reason.", False),
    ("Manual_Check - duplicate groups the rules could not resolve, the decision taken after checking each DOI, and its evidence (rule M1).", False),
    ("Data_Quality - counts recomputed by formula from G1_clean / G2_clean, next to the script values.", False),
    ("Data_Dictionary - every column of every sheet. Provenance - database, queries, dates, files, scripts.", False),
    ("", False),
    ("Header colours in G1_clean / G2_clean", True),
    ("Blue header = value copied from the OpenAlex response without change.", False),
    ("Orange header = derived column, computed by a rule in Cleaning_Rules. Source values are never overwritten.", False),
]
for i, (t, b) in enumerate(readme, 1):
    c = ws.cell(row=i, column=1, value=t)
    c.font = Font(name=FONT, bold=b, size=12 if i == 1 else 10)
ws.cell(row=21, column=1).fill = RAW_FILL
ws.cell(row=22, column=1).fill = DER_FILL
ws.column_dimensions["A"].width = 140

# ---------------------------------------------------------------- data sheets
wide = {"title": 60, "abstract": 60, "authors": 40, "keywords": 40, "exclusion_reason": 45,
        "venue": 30, "author_ids": 30, "seed_author_name_without_seed_id": 34, "title_normalized": 40}
ws_g1 = put_df("G1_clean", g1, widths=wide, colour_headers=True, freeze="B2")
ws_g2 = put_df("G2_clean", g2, widths=wide, colour_headers=True, freeze="B2")
put_df("G2_parent_links", links)
put_df("Field_Year_All", fy_all)
put_df("Field_Year_Core", fy_core, widths={"field": 34})
put_df("G2_Field_Year_Core", g2_fy, widths={"field": 34})
put_df("Subfield_Year_Core", sf_core, widths={"field > subfield": 60})
put_df("Cleaning_Rules", rules, widths={"rule": 120}, wrap_cols=("rule",))
put_df("Cleaning_Log", log, widths={"reason": 100, "action": 28})
wm = put_df("Manual_Check", manual, widths={"title": 50, "doi": 40, "venue": 28, "decision": 14, "evidence": 70},
            wrap_cols=("title", "evidence"))

# ---------------------------------------------------------------- Data_Quality with formulas


def col(ws, df, name):
    L = get_column_letter(list(df.columns).index(name) + 1)
    return f"{ws.title}!${L}$2:${L}${len(df) + 1}"


ws = wb.create_sheet("Data_Quality")
ws.append(["Metric", "G1 (formula on G1_clean)", "G2 (formula on G2_clean)",
           "G1 (script)", "G2 (script)", "Check"])
script = dq.set_index("metric")
specs = [
    ("Records", "COUNTA({openalex_id})"),
    ("Missing DOI", "COUNTBLANK({doi})"),
    ("Missing title", "COUNTBLANK({title})"),
    ("Missing abstract", "COUNTIF({abstract_available},0)"),
    ("Missing field (Unknown)", "COUNTBLANK({field})"),
    ("Missing field, published 2026", "SUMPRODUCT((LEN({field})=0)*({publication_year}=2026))"),
    ("Missing venue", "COUNTBLANK({venue})"),
    ("Missing language", "COUNTBLANK({language})"),
    ("Missing author affiliation country", "COUNTBLANK({author_countries})"),
    ("Retracted (OpenAlex is_retracted)", "COUNTIF({is_retracted},TRUE)"),
    ("Records excluded as duplicate/version", "COUNTIFS({duplicate_confidence},\"high\",{duplicate_of},\"<>\")+COUNTIFS({duplicate_confidence},\"manual_same_work\",{duplicate_of},\"<>\")"),
    ("Core document types", "COUNTIF({doc_type_group},\"core\")"),
    ("Non-core types assessed separately", "COUNTIF({doc_type_group},\"assess_separately\")"),
    ("Excluded document types", "COUNTIF({doc_type_group},\"excluded_type\")"),
    ("Added to OpenAlex after cutoff", "SUM({after_cutoff_flag})"),
    ("Seed-author name without seed author ID", "COUNTA({seed_author_name_without_seed_id})"),
    ("In core analysis", "SUM({in_core_analysis})"),
    ("In core analysis, complete years 2016-2025", "COUNTIFS({in_core_analysis},1,{publication_year},\"<=2025\")"),
    ("In core analysis, partial year 2026", "COUNTIFS({in_core_analysis},1,{publication_year},2026)"),
]
r = 2
for metric, f in specs:
    ws.cell(row=r, column=1, value=metric)
    for k, (wsx, df) in enumerate(((ws_g1, g1), (ws_g2, g2))):
        names = {c: col(wsx, df, c) for c in df.columns}
        ws.cell(row=r, column=2 + k, value="=" + f.format(**names))
    ws.cell(row=r, column=4, value=clean(script.loc[metric, "G1"]))
    ws.cell(row=r, column=5, value=clean(script.loc[metric, "G2"]))
    ws.cell(row=r, column=6, value=f'=IF(AND(B{r}=D{r},C{r}=E{r}),"match","CHECK")')
    r += 1
ws.cell(row=r, column=1, value="Self-citations by author ID (rule S1)")
ws.cell(row=r, column=2, value=f"=COUNTIF({col(ws_g1, g1, 'self_citation_flag')},TRUE)")
ws.cell(row=r, column=4, value=clean(script.loc["Self-citations by author ID (rule S1)", "G1"]))
ws.cell(row=r, column=6, value=f'=IF(B{r}=D{r},"match","CHECK")')
r += 2
ws.cell(row=r, column=1, value="Computed by clean_and_document.py only (not reproducible as a simple formula)").font = Font(name=FONT, bold=True)
r += 1
done = {m for m, _ in specs} | {"Self-citations by author ID (rule S1)"}
for metric, row in script.iterrows():
    if metric in done:
        continue
    ws.cell(row=r, column=1, value=metric.strip())
    ws.cell(row=r, column=4, value=clean(row["G1"]))
    ws.cell(row=r, column=5, value=clean(row["G2"]))
    r += 1
for j, w in enumerate([58, 24, 24, 14, 14, 10], 1):
    ws.column_dimensions[get_column_letter(j)].width = w
for c in ws[1]:
    c.fill = HDR_FILL
    c.font = Font(name=FONT, bold=True, color="FFFFFF")
    c.alignment = Alignment(wrap_text=True)
ws.freeze_panes = "A2"

put_df("Data_Dictionary", dd, widths={"meaning": 70, "source": 45, "allowed_values_or_format": 40, "notes": 50},
       wrap_cols=("meaning", "source", "allowed_values_or_format", "notes"))
put_df("Provenance", prov, widths={"item": 34, "value": 120}, wrap_cols=("value",))

for s in wb.worksheets:
    for row in s.iter_rows():
        for c in row:
            f = c.font
            c.font = Font(name=FONT, bold=f.bold, color=f.color, size=f.sz or 10)
wb.save(OUT_XLSX)
print("saved", OUT_XLSX)
