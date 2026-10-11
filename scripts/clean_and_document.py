"""
clean_and_document.py - cleaning, deduplication and documentation of the
WOA citation dataset (G1 and G2).

Run from the project root, after the retrieval and extraction scripts:
    python scripts/clean_and_document.py

What it does, in order
    1. Loads the extracted G1 and G2 tables and adds a few fields copied
       unchanged from the saved OpenAlex records (publication and creation
       dates, retraction and open-access flags, first author, affiliation
       countries, abstract).
    2. Adds derived columns: normalised DOI and title, analysis field,
       document-type group, cutoff flag.
    3. Finds duplicates: same OpenAlex ID (D1), same DOI (D2), same title +
       first author + year (D3); picks the record to keep (D4); finds G2
       records that are versions of G1 works (D5).
    4. Applies the manual decisions in manual_decisions.csv (M1).
    5. Decides for every record whether it is counted in the core analysis
       (in_core_analysis) and writes the reason when it is not.
    6. Writes one cleaning-log row for every exclusion or flag.
    7. Builds the core field-by-year and subfield-by-year tables, with and
       without self-citations and without retracted works.
    8. Writes a data-quality summary and the list of cleaning rules.

Reads (never modifies)
    data/core/g1_with_field_ids.csv, data/core/g2_extracted.csv,
    data/core/g2_parent_links.csv, data/core/field_year_normalized.csv,
    data/raw/g1_raw_2026-10-04.json, data/raw/g2_stratified_raw_2026-10-06.json,
    data/raw/seed_work_info.json, scripts/manual_decisions.csv

Writes (data/clean/)
    g1_clean.csv, g2_clean.csv, g2_parent_links_clean.csv,
    field_year_core.csv, subfield_year_core.csv,
    cleaning_log.csv, cleaning_rules.csv, data_quality_summary.csv

Principles: no record is deleted and no source column is overwritten.
Every added column is either copied from the saved OpenAlex record ("raw")
or computed by a rule in cleaning_rules.csv ("derived").
"""

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

CUTOFF = "2026-10-04"           # declared data cutoff (G1 retrieval date)
CLEANING_DATE = "2026-10-09"
SEED_AUTHORS = {"A5091500375": "Seyedali Mirjalili", "A5063313173": "Andrew Lewis"}

CORE_TYPES = {"article", "conference-paper", "review", "book-chapter"}
EXCLUDED_TYPES = {"peer-review", "paratext", "retraction", "erratum", "editorial",
                  "reference-entry", "dataset", "book-review"}
# everything else (preprint, dissertation, book, report, software-paper, other,
# conference-abstract, letter, data-paper) -> assessed separately
SUBFIELD_FIELDS = {"Computer Science", "Engineering"}   # see rule F2

CORE = Path("data/core")
RAW = Path("data/raw")
OUT = Path("data/clean")
OUT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- helpers

def strip_id(u):
    """https://openalex.org/W123 -> W123"""
    return (u or "").replace("https://openalex.org/", "")


def rebuild_abstract(inv):
    """OpenAlex stores abstracts as {word: [positions]}; put the words back in order."""
    if not inv:
        return ""
    pos = {}
    for word, places in inv.items():
        for p in places:
            pos[p] = word
    return " ".join(pos[k] for k in sorted(pos))


def norm_text(s):
    """Lower-case, strip accents, HTML tags and punctuation, so that titles
    written slightly differently compare as equal."""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s).lower()
    s = re.sub(r"<[^>]+>", " ", s)               # inline HTML tags such as <i>
    return re.sub(r"[^\w]+", " ", s).strip()


def norm_doi(d):
    """https://doi.org/10.X/ABC -> 10.x/abc"""
    if not isinstance(d, str) or not d.strip():
        return ""
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", d.strip().lower())


def raw_extras(path):
    """Read the saved OpenAlex records and return, for each work, the extra
    fields copied unchanged from the record (step 1)."""
    results = json.load(open(path, encoding="utf-8"))["results"]
    rows = []
    for w in results:
        au = w.get("authorships") or []
        first = (au[0].get("author") or {}) if au else {}
        countries = sorted({c for a in au for c in (a.get("countries") or [])})
        # authors whose display name is a seed author but whose ID is not a seed ID
        name_only = []
        for a in au:
            aut = a.get("author") or {}
            nm = aut.get("display_name") or a.get("raw_author_name") or ""
            aid = strip_id(aut.get("id"))
            for sid, sname in SEED_AUTHORS.items():
                if norm_text(nm) == norm_text(sname) and aid != sid:
                    name_only.append(f"{sname} ({aid or 'no author ID'})")
        oa = w.get("open_access") or {}
        abstract = rebuild_abstract(w.get("abstract_inverted_index"))
        rows.append({
            "openalex_id": strip_id(w["id"]),
            "publication_date": w.get("publication_date") or "",
            "openalex_created_date": (w.get("created_date") or "")[:10],
            "is_retracted": bool(w.get("is_retracted")),
            "is_open_access": bool(oa.get("is_oa")),
            "first_author_name": first.get("display_name") or "",
            "first_author_id": strip_id(first.get("id")),
            "author_countries": ";".join(countries),
            "abstract": abstract,
            "seed_author_name_without_seed_id": "; ".join(name_only),
        })
    return pd.DataFrame(rows)


def doc_type_group(t):
    """Rules T1/T2: core research types, excluded non-research types, or
    other types that are kept but counted separately."""
    if t in CORE_TYPES:
        return "core"
    if t in EXCLUDED_TYPES:
        return "excluded_type"
    return "assess_separately"


def primary_sort_key(df):
    # Rule D4: sort a duplicate group so the record to keep comes first:
    # core type, then not a preprint, then has a DOI, then most cited,
    # then the oldest OpenAlex ID.
    return df.assign(
        _k1=(df.doc_type_group != "core").astype(int),
        _k2=(df.publication_type == "preprint").astype(int),
        _k3=(df.doi_normalized == "").astype(int),
        _k4=-df.citation_count,
        _k5=df.openalex_id.str[1:].astype("int64"),
    ).sort_values(["_k1", "_k2", "_k3", "_k4", "_k5"])


log = []   # one dict per cleaning action; saved as cleaning_log.csv


def add_log(rec, gen, rule, action, reason, related=""):
    """Record one rule-based action on one record."""
    log.append({"record_id": rec, "generation": gen, "rule_id": rule, "action": action,
                "reason": reason, "related_record": related, "decided_by": "rule",
                "date": CLEANING_DATE})


def prepare(gen, csv_path, raw_path):
    """Steps 1-2: load a generation, add raw extras and derived columns."""
    df = pd.read_csv(csv_path, low_memory=False, dtype={"field_id": "string"})
    df["field_id"] = df["field_id"].str.replace(r"\.0$", "", regex=True)   # 17.0 -> 17 (format only)
    n0 = len(df)
    df = df.merge(raw_extras(raw_path), on="openalex_id", how="left", validate="one_to_one")
    assert len(df) == n0
    df["abstract_available"] = (df.abstract.fillna("") != "").astype(int)
    df["doi_normalized"] = df.doi.map(norm_doi)
    df["title_normalized"] = df.title.map(norm_text)
    df["first_author_normalized"] = df.first_author_name.map(norm_text)
    df["field_analysis"] = df.field.fillna("Unknown")
    df["analysis_category"] = df.field_analysis
    sub = df.field_analysis.isin(SUBFIELD_FIELDS)
    df.loc[sub, "analysis_category"] = df.field_analysis[sub] + " > " + df.subfield.fillna("Unknown subfield")[sub]
    df["doc_type_group"] = df.publication_type.map(doc_type_group)
    after = (df.openalex_created_date > CUTOFF) | (df.publication_date > CUTOFF)
    df["after_cutoff_flag"] = after.astype(int)
    df["duplicate_group_id"] = ""
    df["duplicate_rule"] = ""
    df["duplicate_of"] = ""
    df["duplicate_confidence"] = ""
    df["possible_version_of_g1"] = ""
    return df


def dedupe(df, gen):
    """Step 3: duplicate rules D1-D3. Records are only marked; the kept
    record of each group has duplicate_of empty."""
    gid = 0
    # D1: OpenAlex ID
    assert not df.openalex_id.duplicated().any(), "duplicate OpenAlex IDs"
    # D2: normalised DOI
    has = df[df.doi_normalized != ""]
    for doi, grp in has[has.doi_normalized.duplicated(keep=False)].groupby("doi_normalized"):
        gid += 1
        order = primary_sort_key(grp)
        keep = order.index[0]
        for i in grp.index:
            df.at[i, "duplicate_group_id"] = f"{gen}-D{gid:03d}"
            df.at[i, "duplicate_rule"] = "D2"
            df.at[i, "duplicate_confidence"] = "high"
            if i != keep:
                df.at[i, "duplicate_of"] = df.at[keep, "openalex_id"]
                add_log(df.at[i, "openalex_id"], gen, "D2", "exclude_from_core_analysis",
                        f"Same DOI ({doi}) as {df.at[keep, 'openalex_id']}; kept record chosen by rule D4",
                        df.at[keep, "openalex_id"])
    # D3: title + first author + year (only rows not already resolved, with a title)
    cand = df[(df.title_normalized != "") & (df.duplicate_group_id == "")]
    keys = ["title_normalized", "first_author_normalized", "publication_year"]
    for _, grp in cand[cand.duplicated(keys, keep=False)].groupby(keys):
        gid += 1
        order = primary_sort_key(grp)
        keep = order.index[0]
        n_core = (grp.doc_type_group == "core").sum()
        dois = set(grp.doi_normalized[grp.doc_type_group == "core"]) - {""}
        # high: at most one core record (others are preprints/other versions)
        conf = "high" if n_core <= 1 or len(dois) <= 1 else "needs_manual_check"
        for i in grp.index:
            df.at[i, "duplicate_group_id"] = f"{gen}-D{gid:03d}"
            df.at[i, "duplicate_rule"] = "D3"
            df.at[i, "duplicate_confidence"] = conf
            if i != keep:
                df.at[i, "duplicate_of"] = df.at[keep, "openalex_id"]
                if conf == "high":
                    add_log(df.at[i, "openalex_id"], gen, "D3", "exclude_from_core_analysis",
                            f"Same title, first author and year as {df.at[keep, 'openalex_id']} "
                            f"({df.at[i, 'publication_type']} vs {df.at[keep, 'publication_type']}); version of the same work",
                            df.at[keep, "openalex_id"])
                else:
                    add_log(df.at[i, "openalex_id"], gen, "D3", "flag_only",
                            f"Same title, first author and year as {df.at[keep, 'openalex_id']} but both are core "
                            "records with different DOIs; kept in analysis until checked manually",
                            df.at[keep, "openalex_id"])
    return df


# Step 4: decisions taken by hand on groups the rules could not resolve
MANUAL = pd.read_csv(Path(__file__).parent / "manual_decisions.csv")


def apply_manual(df, gen):
    """Rule M1: manual decisions on groups flagged needs_manual_check."""
    for _, m in MANUAL[MANUAL.duplicate_group_id.str.startswith(gen + "-")].iterrows():
        grp = df[df.duplicate_group_id == m.duplicate_group_id]
        assert len(grp) >= 2 and (grp.duplicate_confidence == "needs_manual_check").all(), m.duplicate_group_id
        keep_id = grp[grp.duplicate_of == ""].openalex_id.iloc[0]
        # drop the provisional flag_only log rows for this group
        global log
        log = [r for r in log if not (r["rule_id"] == "D3" and r["record_id"] in set(grp.openalex_id) and r["action"] == "flag_only")]
        for i in grp.index:
            rid = df.at[i, "openalex_id"]
            if m.decision == "same work":
                df.at[i, "duplicate_confidence"] = "manual_same_work"
                if rid != keep_id:
                    log.append({"record_id": rid, "generation": gen, "rule_id": "M1", "action": "exclude_from_core_analysis",
                                "reason": f"Manual check: same work as {keep_id}. {m.evidence}", "related_record": keep_id,
                                "decided_by": "manual", "date": m.date})
            else:
                df.at[i, "duplicate_confidence"] = "manual_distinct"
                df.at[i, "duplicate_of"] = ""
                log.append({"record_id": rid, "generation": gen, "rule_id": "M1", "action": "keep",
                            "reason": f"Manual check: separate publication, kept. {m.evidence}", "related_record": keep_id if rid != keep_id else "",
                            "decided_by": "manual", "date": m.date})
    return df


def finalize(df, gen):
    """Steps 5-6: in_core_analysis, exclusion_reason and log rows. The first
    reason that applies is the one written."""
    excl = pd.Series("", index=df.index)
    excl[df.doc_type_group == "excluded_type"] = "excluded document type (rule T1)"
    excl[(excl == "") & (df.doc_type_group == "assess_separately")] = "assessed separately: non-core document type (rule T2)"
    dup_out = (df.duplicate_of != "") & (df.duplicate_confidence == "high")
    excl[(excl == "") & dup_out] = "duplicate/version of " + df.duplicate_of[dup_out] + " (rule " + df.duplicate_rule[dup_out] + ")"
    man_out = (df.duplicate_of != "") & (df.duplicate_confidence == "manual_same_work")
    excl[(excl == "") & man_out] = "same work as " + df.duplicate_of[man_out] + " (manual check, rule M1)"
    if gen == "G2":
        v = (df.possible_version_of_g1 != "") & (excl == "")
        excl[v] = "version of G1 record " + df.possible_version_of_g1[v] + " (rule D5)"
    excl[(excl == "") & (df.after_cutoff_flag == 1)] = f"added to OpenAlex after cutoff {CUTOFF} (rule C1)"
    df["exclusion_reason"] = excl
    df["in_core_analysis"] = (excl == "").astype(int)
    for i in df.index[df.doc_type_group == "excluded_type"]:
        add_log(df.at[i, "openalex_id"], gen, "T1", "exclude_from_core_analysis",
                f"Document type '{df.at[i, 'publication_type']}' is not a research output")
    for i in df.index[df.doc_type_group == "assess_separately"]:
        add_log(df.at[i, "openalex_id"], gen, "T2", "exclude_from_core_analysis",
                f"Document type '{df.at[i, 'publication_type']}' is assessed separately from core counts")
    for i in df.index[df.after_cutoff_flag == 1]:
        add_log(df.at[i, "openalex_id"], gen, "C1", "exclude_from_core_analysis",
                f"openalex_created_date {df.at[i, 'openalex_created_date']} is after the declared cutoff {CUTOFF}")
    for i in df.index[df.is_retracted]:
        add_log(df.at[i, "openalex_id"], gen, "Q1", "flag_only",
                "Marked retracted in OpenAlex; kept, and core counts are also reported without retracted works")
    for i in df.index[df.seed_author_name_without_seed_id != ""]:
        add_log(df.at[i, "openalex_id"], gen, "S2", "flag_only",
                "Seed-author name appears with a different or missing OpenAlex author ID: "
                + df.at[i, "seed_author_name_without_seed_id"] + "; self_citation_flag (ID rule) left unchanged")
    return df.drop(columns=["first_author_normalized"])


# ------------------------------------------------------------------ G1
g1 = prepare("G1", CORE / "g1_with_field_ids.csv", RAW / "g1_raw_2026-10-04.json")
g1 = dedupe(g1, "G1")
g1 = apply_manual(g1, "G1")
g1 = finalize(g1, "G1")

# ------------------------------------------------------------------ G2
g2 = prepare("G2", CORE / "g2_extracted.csv", RAW / "g2_stratified_raw_2026-10-06.json")
g2 = dedupe(g2, "G2")
# G2 works written by a seed author: they cite a G1 paper, not the seed, so
# they are not self-citations of the seed; flagged so G2 can be shown without them.
g2["seed_author_flag"] = g2.author_ids.fillna("").str.contains("A5091500375|A5063313173")
g2 = apply_manual(g2, "G2")
# D5: G2 record with same title + first author + year as a G1 record
g1_first = pd.read_csv(CORE / "g1_with_field_ids.csv", usecols=["openalex_id"]).merge(
    g1[["openalex_id", "title_normalized", "publication_year", "first_author_name"]], on="openalex_id")
g1_first["fa"] = g1_first.first_author_name.map(norm_text)
key = dict(zip(zip(g1_first.title_normalized, g1_first.fa, g1_first.publication_year), g1_first.openalex_id))
for i, r in g2.iterrows():
    k = (r.title_normalized, norm_text(r.first_author_name), r.publication_year)
    if r.title_normalized and k in key:
        g2.at[i, "possible_version_of_g1"] = key[k]
        add_log(r.openalex_id, "G2", "D5", "exclude_from_core_analysis",
                f"Same title, first author and year as G1 record {key[k]}; a version of a G1 work is not a new G2 work",
                key[k])
g2 = finalize(g2, "G2")
g1 = g1.drop(columns=["possible_version_of_g1"])

# ------------------------------------------------------------------ links
links = pd.read_csv(CORE / "g2_parent_links.csv")
links["g2_in_core_analysis"] = links.g2_id.map(dict(zip(g2.openalex_id, g2.in_core_analysis)))
links["parent_in_core_analysis"] = links.parent_g1_id.map(dict(zip(g1.openalex_id, g1.in_core_analysis)))

# ------------------------------------------------------------------ field-year (core set)
# Step 7: denominators (all OpenAlex works per field and year, queried on
# 2026-10-04) come from the normalisation table; numerators are recounted
# on the core-analysis set.
fy_all = pd.read_csv(CORE / "field_year_normalized.csv", dtype={"field_id": "string"})
den = fy_all[["year", "field", "total_openalex_field_output"]]
core1 = g1[g1.in_core_analysis == 1]


def fy_counts(d, col):
    """Counts per year and category: all, without self-citations, without
    retracted works."""
    a = d.groupby(["publication_year", col]).size().rename("count_with_self")
    b = d[~d.self_citation_flag].groupby(["publication_year", col]).size().rename("count_without_self")
    c = d[~d.is_retracted].groupby(["publication_year", col]).size().rename("count_without_retracted")
    out = pd.concat([a, b, c], axis=1).fillna(0).astype(int).reset_index()
    return out.rename(columns={"publication_year": "year"})


fy = fy_counts(core1, "field_analysis").rename(columns={"field_analysis": "field"})
fy = fy.merge(den, on=["year", "field"], how="left")
for c in ["with_self", "without_self"]:
    fy[f"share_per_100k_{c}"] = (fy[f"count_{c}"] / fy.total_openalex_field_output * 1e5).round(3)
fy["year_status"] = fy.year.map(lambda y: "partial" if y == 2026 else "complete")
fy.to_csv(OUT / "field_year_core.csv", index=False)

sf = fy_counts(core1[core1.field_analysis.isin(SUBFIELD_FIELDS)], "analysis_category").rename(
    columns={"analysis_category": "field > subfield"})
sf["year_status"] = sf.year.map(lambda y: "partial" if y == 2026 else "complete")
sf.to_csv(OUT / "subfield_year_core.csv", index=False)

# ------------------------------------------------------------------ step 8: data-quality summary
seed = json.load(open(RAW / "seed_work_info.json", encoding="utf-8"))


def dq(d):
    return {
        "Records": len(d),
        "Unique OpenAlex IDs": d.openalex_id.nunique(),
        "Missing DOI": int((d.doi_normalized == "").sum()),
        "Missing title": int(d.title.isna().sum()),
        "Missing abstract": int((d.abstract_available == 0).sum()),
        "Missing field (Unknown)": int(d.field.isna().sum()),
        "Missing field, published 2026": int((d.field.isna() & (d.publication_year == 2026)).sum()),
        "Missing venue": int(d.venue.isna().sum()),
        "Missing language": int(d.language.isna().sum()),
        "Language tagged English (%)": round((d.language == "en").mean() * 100, 1),
        "Missing author affiliation country": int((d.author_countries == "").sum()),
        "Retracted (OpenAlex is_retracted)": int(d.is_retracted.sum()),
        "Duplicate DOI groups (rule D2)": int(d[d.duplicate_rule == "D2"].duplicate_group_id.nunique()),
        "Title+first author+year groups (rule D3)": int(d[d.duplicate_rule == "D3"].duplicate_group_id.nunique()),
        "  of which checked by hand (M1)": int(d[(d.duplicate_rule == "D3") & (d.duplicate_confidence.isin(["needs_manual_check", "manual_same_work", "manual_distinct"]))].duplicate_group_id.nunique()),
        "  still awaiting manual check": int(d[d.duplicate_confidence == "needs_manual_check"].duplicate_group_id.nunique()),
        "Records excluded as duplicate/version": int(((d.duplicate_of != "") & (d.duplicate_confidence.isin(["high", "manual_same_work"]))).sum()),
        "Manual-check groups judged same work": int(d[d.duplicate_confidence == "manual_same_work"].duplicate_group_id.nunique()),
        "Manual-check groups judged separate publications": int(d[d.duplicate_confidence == "manual_distinct"].duplicate_group_id.nunique()),
        "Core document types": int((d.doc_type_group == "core").sum()),
        "Non-core types assessed separately": int((d.doc_type_group == "assess_separately").sum()),
        "Excluded document types": int((d.doc_type_group == "excluded_type").sum()),
        "Added to OpenAlex after cutoff": int(d.after_cutoff_flag.sum()),
        "Seed-author name without seed author ID": int((d.seed_author_name_without_seed_id != "").sum()),
        "In core analysis": int(d.in_core_analysis.sum()),
        "In core analysis, complete years 2016-2025": int(((d.in_core_analysis == 1) & (d.publication_year <= 2025)).sum()),
        "In core analysis, partial year 2026": int(((d.in_core_analysis == 1) & (d.publication_year == 2026)).sum()),
    }


q = pd.DataFrame({"G1": dq(g1), "G2": dq(g2.assign(self_citation_flag=False))})
q.loc["G2 records that are versions of G1 works (rule D5)"] = [None, int((g2.possible_version_of_g1 != "").sum())]
q.loc["G2 works with a seed author (flag only, rule S3)"] = [None, int(g2.seed_author_flag.sum())]
q.loc["G2 core analysis without seed-author works"] = [None, int(((g2.in_core_analysis == 1) & ~g2.seed_author_flag).sum())]
q.loc["Self-citations by author ID (rule S1)"] = [int(g1.self_citation_flag.sum()), None]
q.loc["Seed paper cited_by_count (OpenAlex, 2026-10-04)"] = [seed["cited_by_count"], None]
q.loc["Gap: cited_by_count minus retrieved G1"] = [seed["cited_by_count"] - len(g1), None]
txt = (g1.title.fillna("") + " " + g1.abstract.fillna("") + " " + g1.keywords.fillna("")).str.lower()
has = g1.abstract_available == 1
q.loc["G1 with abstract naming WOA in title/abstract/keywords (%)"] = [
    round(txt[has].str.contains(r"whale|\bwoa\b").mean() * 100, 1), None]
q.index.name = "metric"
q.to_csv(OUT / "data_quality_summary.csv")

# ------------------------------------------------------------------ save
rules = pd.DataFrame([
    ("C1", "Cutoff", f"Records created in OpenAlex or published after {CUTOFF} are flagged (after_cutoff_flag=1) and kept out of the core analysis."),
    ("T1", "Document type", "peer-review, paratext, retraction notice, erratum, editorial, reference-entry, dataset: kept in file, excluded from core analysis."),
    ("T2", "Document type", "preprint, dissertation, book, report, software-paper, other, conference-abstract, letter, data-paper: kept, assessed separately (not in core counts)."),
    ("D1", "Duplicates", "Same OpenAlex ID: none found in G1 or G2."),
    ("D2", "Duplicates", "Same normalised DOI: one record kept (rule D4), others excluded from core analysis with duplicate_of set."),
    ("D3", "Duplicates", "Same normalised title + first author + publication year: if at most one record is a core type (or core records share a DOI) the group is a version group (high confidence) and only the kept record stays in analysis; otherwise all stay in analysis and the group is flagged needs_manual_check."),
    ("D4", "Duplicates", "Kept record = core type first, then non-preprint, then has DOI, then higher citation_count, then lower OpenAlex ID."),
    ("D5", "Duplicates", "G2 record with the same title + first author + year as a G1 record is a version of a G1 work and is excluded from G2 core analysis."),
    ("F1", "Field", "Analysis level = OpenAlex primary_topic field. Missing field kept as 'Unknown'."),
    ("F2", "Field", "Computer Science and Engineering are additionally broken down by subfield (analysis_category), because together they hold most G1 records."),
    ("S1", "Self-citation", "self_citation_flag = a citing work lists OpenAlex author ID A5091500375 or A5063313173 (add_self_citation_flag.py, unchanged)."),
    ("S2", "Self-citation", "Records where a seed-author name appears with a different or missing author ID are flagged only; ID rule is not overridden."),
    ("M1", "Duplicates", "Groups flagged needs_manual_check were checked by hand (DOI resolution, venue, issue, pages, authors, abstract). 'same work': only the record kept by D4 stays in analysis; 'keep both': all stay. Decisions and evidence in manual_decisions.csv."),
    ("S3", "Self-citation", "G2 works whose author IDs include a seed author are flagged (seed_author_flag). They cite a G1 paper, not the seed, so they are not counted as self-citations of the seed; G2 counts are also given without them."),
    ("Q1", "Quality", "Retracted works kept and flagged; core field-year counts are also given without them."),
], columns=["rule_id", "area", "rule"])
rules.to_csv(OUT / "cleaning_rules.csv", index=False)

pd.DataFrame(log).to_csv(OUT / "cleaning_log.csv", index=False)
g1.to_csv(OUT / "g1_clean.csv", index=False)
g2.to_csv(OUT / "g2_clean.csv", index=False)
links.to_csv(OUT / "g2_parent_links_clean.csv", index=False)
print(q.to_string())
print("log rows:", len(log))
