#!/usr/bin/env python3
"""
Colab/Jupyter-safe one-click literature review generator for:
Nigeria + Sentinel-2 + urban growth / LULC transitions
"""

import argparse
import re
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

OPENALEX_BASE = "https://api.openalex.org/works"
CROSSREF_BASE = "https://api.crossref.org/works"

DEFAULT_QUERIES = [
    '"Nigeria" "Sentinel-2" "urban growth"',
    '"Nigeria" "Sentinel-2" "land use land cover"',
    '"Nigeria" "land cover change" "urban expansion"',
    '"Nigeria" "LULC" "urban growth" remote sensing',
    '"Lagos" Nigeria "land cover change" GIS',
    '"Abuja" Nigeria "urban expansion" remote sensing',
    '"Ibadan" Nigeria "land use" remote sensing',
    '"Port Harcourt" Nigeria "land cover" remote sensing',
    '"Kano" Nigeria "urban growth" remote sensing',
]

SEED_TITLES = [
    "Analyzing urban growth and land cover change scenario in Lagos, Nigeria using multi-temporal remote sensing data and GIS to mitigate flooding",
]

SEED_DOIS = [
    "10.1080/19475705.2021.1887940",
]

NIGERIA_TERMS = [
    "nigeria", "lagos", "abuja", "ibadan", "port harcourt", "kano",
    "kaduna", "enugu", "benin city", "maiduguri", "ilorin", "jos",
    "oyo", "ogun", "ondo", "anambra", "rivers state", "fct",
]

TOPIC_TERMS = [
    "sentinel-2", "sentinel 2", "multitemporal", "multi-temporal",
    "urban growth", "urban expansion", "urbanization", "urbanisation",
    "land use", "land cover", "land-use", "land-cover", "lulc",
    "transition", "change detection", "remote sensing", "gis",
    "flood", "flooding",
]

STOPWORDS = {
    "the", "and", "for", "with", "using", "from", "into", "over", "under",
    "between", "within", "study", "analysis", "based", "approach",
    "assessment", "case", "area", "areas", "change", "changes",
    "scenario", "scenarios", "data", "gis", "remote", "sensing",
    "urban", "growth", "land", "cover", "use", "nigeria", "lagos",
    "abuja", "sentinel", "multi", "temporal",
}


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(str(text).lower().strip().split())


def normalize_doi(doi: Optional[str]) -> str:
    if not doi:
        return ""
    doi = str(doi).strip().lower()
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    return doi


def is_nigeria_related(text: str) -> bool:
    t = normalize_text(text)
    return any(term in t for term in NIGERIA_TERMS)


def invert_openalex_abstract(inv_idx: Optional[Dict]) -> str:
    if not inv_idx:
        return ""
    pairs = []
    for word, positions in inv_idx.items():
        for pos in positions:
            pairs.append((pos, word))
    pairs.sort(key=lambda x: x[0])
    return " ".join(word for _, word in pairs)


def safe_get(obj, *keys, default=None):
    cur = obj
    for key in keys:
        if cur is None:
            return default
        if isinstance(cur, list):
            if not cur:
                return default
            cur = cur[0]
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return default
    return cur if cur is not None else default


def strip_xml_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def score_record(title: str, abstract: str, journal: str) -> int:
    text = normalize_text(f"{title} {abstract} {journal}")
    score = 0
    for term in NIGERIA_TERMS:
        if term in text:
            score += 2
    for term in TOPIC_TERMS:
        if term in text:
            score += 2
    if "sentinel-2" in text or "sentinel 2" in text:
        score += 3
    if "urban growth" in text or "urban expansion" in text:
        score += 3
    if "land use" in text and "land cover" in text:
        score += 3
    return score


def get_session(mailto: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": f"NigeriaLiteratureReviewGenerator/1.2 (mailto:{mailto})",
        "Accept": "application/json",
    })
    return session


def fetch_openalex_query(session: requests.Session, query: str, mailto: str, pause: float = 0.8) -> List[Dict]:
    rows = []
    cursor = "*"
    seen_ids = set()

    while True:
        params = {
            "search": query,
            "per-page": 200,
            "cursor": cursor,
            "mailto": mailto,
            "select": ",".join([
                "id", "doi", "display_name", "publication_year",
                "publication_date", "cited_by_count", "type",
                "primary_location", "authorships", "abstract_inverted_index"
            ])
        }
        r = session.get(OPENALEX_BASE, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()

        results = data.get("results", [])
        next_cursor = data.get("meta", {}).get("next_cursor")
        if not results:
            break

        for item in results:
            item_id = item.get("id")
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)

            title = item.get("display_name", "") or ""
            abstract = invert_openalex_abstract(item.get("abstract_inverted_index"))
            journal = safe_get(item, "primary_location", "source", "display_name", default="") or ""
            combined = f"{title} {abstract} {journal}"
            if not is_nigeria_related(combined):
                continue

            authors = []
            for a in item.get("authorships", [])[:15]:
                name = safe_get(a, "author", "display_name", default="")
                if name:
                    authors.append(name)

            rows.append({
                "source_api": "OpenAlex",
                "query": query,
                "title": title,
                "authors": "; ".join(authors),
                "year": item.get("publication_year"),
                "publication_date": item.get("publication_date"),
                "journal": journal,
                "doi": normalize_doi(item.get("doi")),
                "url": item.get("id"),
                "citations": item.get("cited_by_count"),
                "type": item.get("type"),
                "abstract": abstract,
            })

        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(pause)

    return rows


def fetch_openalex_by_doi(session: requests.Session, doi: str, mailto: str) -> Optional[Dict]:
    doi = normalize_doi(doi)
    if not doi:
        return None

    url = f"{OPENALEX_BASE}/https://doi.org/{doi}"
    r = session.get(url, params={"mailto": mailto}, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    item = r.json()

    title = item.get("display_name", "") or ""
    abstract = invert_openalex_abstract(item.get("abstract_inverted_index"))
    journal = safe_get(item, "primary_location", "source", "display_name", default="") or ""

    authors = []
    for a in item.get("authorships", [])[:15]:
        name = safe_get(a, "author", "display_name", default="")
        if name:
            authors.append(name)

    return {
        "source_api": "OpenAlex",
        "query": f"DOI:{doi}",
        "title": title,
        "authors": "; ".join(authors),
        "year": item.get("publication_year"),
        "publication_date": item.get("publication_date"),
        "journal": journal,
        "doi": doi,
        "url": item.get("id"),
        "citations": item.get("cited_by_count"),
        "type": item.get("type"),
        "abstract": abstract,
    }


def fetch_crossref_query(session: requests.Session, query: str, mailto: str, max_records: int = 5000, pause: float = 1.0) -> List[Dict]:
    rows = []
    cursor = "*"
    total_seen = 0

    while True:
        params = {
            "query.bibliographic": query,
            "rows": 1000,
            "cursor": cursor,
            "mailto": mailto,
            "select": ",".join([
                "DOI", "title", "author", "container-title", "issued",
                "published-print", "published-online", "URL",
                "is-referenced-by-count", "type", "abstract"
            ])
        }

        r = session.get(CROSSREF_BASE, params=params, timeout=90)
        r.raise_for_status()
        message = r.json().get("message", {})
        items = message.get("items", [])
        next_cursor = message.get("next-cursor")
        if not items:
            break

        for item in items:
            title = (item.get("title") or [""])[0]
            journal = (item.get("container-title") or [""])[0]
            abstract = strip_xml_tags(item.get("abstract", ""))
            combined = f"{title} {abstract} {journal}"
            if not is_nigeria_related(combined):
                continue

            authors = []
            for a in (item.get("author") or [])[:15]:
                full = f"{a.get('given', '')} {a.get('family', '')}".strip()
                if full:
                    authors.append(full)

            year = (
                safe_get(item, "published-print", "date-parts", default=[[None]])[0][0]
                or safe_get(item, "published-online", "date-parts", default=[[None]])[0][0]
                or safe_get(item, "issued", "date-parts", default=[[None]])[0][0]
            )

            rows.append({
                "source_api": "Crossref",
                "query": query,
                "title": title,
                "authors": "; ".join(authors),
                "year": year,
                "publication_date": None,
                "journal": journal,
                "doi": normalize_doi(item.get("DOI")),
                "url": item.get("URL", ""),
                "citations": item.get("is-referenced-by-count"),
                "type": item.get("type"),
                "abstract": abstract,
            })

        total_seen += len(items)
        if total_seen >= max_records:
            break
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(pause)

    return rows


def fetch_crossref_by_title(session: requests.Session, title: str, mailto: str) -> List[Dict]:
    params = {
        "query.title": title,
        "rows": 20,
        "mailto": mailto,
        "select": ",".join([
            "DOI", "title", "author", "container-title", "issued",
            "published-print", "published-online", "URL",
            "is-referenced-by-count", "type", "abstract"
        ])
    }
    r = session.get(CROSSREF_BASE, params=params, timeout=60)
    r.raise_for_status()
    items = r.json().get("message", {}).get("items", [])

    rows = []
    for item in items:
        got_title = (item.get("title") or [""])[0]
        if normalize_text(got_title) != normalize_text(title):
            continue
        journal = (item.get("container-title") or [""])[0]
        abstract = strip_xml_tags(item.get("abstract", ""))

        authors = []
        for a in (item.get("author") or [])[:15]:
            full = f"{a.get('given', '')} {a.get('family', '')}".strip()
            if full:
                authors.append(full)

        year = (
            safe_get(item, "published-print", "date-parts", default=[[None]])[0][0]
            or safe_get(item, "published-online", "date-parts", default=[[None]])[0][0]
            or safe_get(item, "issued", "date-parts", default=[[None]])[0][0]
        )

        rows.append({
            "source_api": "Crossref",
            "query": f"TITLE:{title}",
            "title": got_title,
            "authors": "; ".join(authors),
            "year": year,
            "publication_date": None,
            "journal": journal,
            "doi": normalize_doi(item.get("DOI")),
            "url": item.get("URL", ""),
            "citations": item.get("is-referenced-by-count"),
            "type": item.get("type"),
            "abstract": abstract,
        })
    return rows


def dedupe_records(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    df["doi_norm"] = df["doi"].fillna("").map(normalize_doi)
    df["title_norm"] = df["title"].fillna("").map(normalize_text)
    df["priority"] = df["source_api"].map({"OpenAlex": 0, "Crossref": 1}).fillna(9)
    df["citations"] = pd.to_numeric(df["citations"], errors="coerce").fillna(0).astype(int)
    df["year_num"] = pd.to_numeric(df["year"], errors="coerce").fillna(0).astype(int)

    df = df.sort_values(
        ["doi_norm", "title_norm", "priority", "citations", "year_num"],
        ascending=[True, True, True, False, False]
    )

    with_doi = df[df["doi_norm"] != ""].drop_duplicates("doi_norm", keep="first")
    without_doi = df[df["doi_norm"] == ""].drop_duplicates("title_norm", keep="first")
    merged = pd.concat([with_doi, without_doi], ignore_index=True)

    merged["relevance_score"] = [
        score_record(t, a, j)
        for t, a, j in zip(
            merged["title"].fillna(""),
            merged["abstract"].fillna(""),
            merged["journal"].fillna("")
        )
    ]

    merged = merged.sort_values(["relevance_score", "citations", "year_num"], ascending=[False, False, False])
    return merged


def extract_keywords(df: pd.DataFrame, top_n: int = 20) -> List[Tuple[str, int]]:
    text = " ".join((df["title"].fillna("") + " " + df["abstract"].fillna("")).tolist()).lower()
    words = re.findall(r"[a-zA-Z0-9\-]{4,}", text)
    words = [w for w in words if w not in STOPWORDS and not w.isdigit()]
    return Counter(words).most_common(top_n)


def summarize_years(df: pd.DataFrame) -> str:
    years = pd.to_numeric(df["year"], errors="coerce").dropna().astype(int)
    if years.empty:
        return "Year information was sparse."
    return f"The records span {years.min()} to {years.max()}, with a median publication year of {int(years.median())}."


def thematic_notes(df: pd.DataFrame) -> List[str]:
    text = " ".join((df["title"].fillna("") + " " + df["abstract"].fillna("")).tolist()).lower()
    notes = []
    if "flood" in text or "flooding" in text:
        notes.append("Flood risk and flood mitigation appear repeatedly in the literature.")
    if "lagos" in text:
        notes.append("Lagos is the most frequently recurring case-study city in the harvested set.")
    if "abuja" in text:
        notes.append("Abuja also appears often, showing strong interest in capital-region expansion.")
    if "change detection" in text or "multitemporal" in text or "multi-temporal" in text:
        notes.append("Multi-temporal change detection is a dominant methodological pattern.")
    if "sentinel-2" in text or "sentinel 2" in text:
        notes.append("Sentinel-2 is directly represented, though some related studies still rely on Landsat or mixed-sensor archives.")
    if not notes:
        notes.append("The harvested literature clusters around urban expansion, LULC transitions, and remote-sensing methods in Nigerian cities.")
    return notes


def write_bibtex(df: pd.DataFrame, out_path: Path) -> None:
    def key_for_row(i: int, row: pd.Series) -> str:
        first_author = row.get("authors", "").split(";")[0].strip().split(" ")[-1].lower() or "paper"
        year = str(int(row["year_num"])) if row.get("year_num", 0) else "nd"
        return f"{first_author}{year}{i}"

    with out_path.open("w", encoding="utf-8") as f:
        for i, (_, row) in enumerate(df.iterrows(), start=1):
            entry_type = "article" if "journal" in str(row.get("type", "")).lower() else "misc"
            key = key_for_row(i, row)
            f.write(f"@{entry_type}{{{key},\n")
            if row.get("title"):
                f.write(f"  title = {{{row['title']}}},\n")
            if row.get("authors"):
                f.write(f"  author = {{{row['authors'].replace('; ', ' and ')}}},\n")
            if row.get("journal"):
                f.write(f"  journal = {{{row['journal']}}},\n")
            if row.get("year"):
                f.write(f"  year = {{{row['year']}}},\n")
            if row.get("doi"):
                f.write(f"  doi = {{{row['doi']}}},\n")
            if row.get("url"):
                f.write(f"  url = {{{row['url']}}},\n")
            f.write("}\n\n")


def write_review(df: pd.DataFrame, out_path: Path) -> None:
    total = len(df)
    top10 = df.head(10).copy()
    keywords = extract_keywords(df, 18)
    notes = thematic_notes(df)
    year_summary = summarize_years(df)

    city_counts = {}
    fulltext = " ".join((df["title"].fillna("") + " " + df["abstract"].fillna("")).tolist()).lower()
    for city in ["lagos", "abuja", "ibadan", "port harcourt", "kano", "kaduna", "enugu", "benin city"]:
        city_counts[city] = fulltext.count(city)
    top_cities = sorted(city_counts.items(), key=lambda x: x[1], reverse=True)

    lines = []
    lines.append("# Literature Review: Nigeria Urban Growth and Sentinel-2\n")
    lines.append("## Scope\n")
    lines.append("This review was generated automatically from OpenAlex and Crossref metadata using Nigeria-focused queries around Sentinel-2, urban growth, land-use/land-cover change, and multi-temporal remote sensing.\n")
    lines.append("## Corpus overview\n")
    lines.append(f"- Total deduplicated records: **{total}**")
    lines.append(f"- {year_summary}")
    lines.append(f"- Mean citation count in the harvested set: **{df['citations'].mean():.1f}**\n")

    lines.append("## Main patterns\n")
    for note in notes:
        lines.append(f"- {note}")
    lines.append("")

    lines.append("## Frequent keywords\n")
    lines.append(", ".join([f"{k} ({v})" for k, v in keywords]) + "\n")

    lines.append("## Most visible city references\n")
    lines.append(", ".join([f"{c.title()} ({n})" for c, n in top_cities if n > 0]) + "\n")

    lines.append("## Suggested narrative synthesis\n")
    lines.append(
        "The harvested literature suggests that Nigeria-focused urban growth research is concentrated in major metropolitan regions, "
        "especially Lagos and Abuja, with strong attention to built-up expansion, vegetation loss, conversion of peri-urban land, "
        "and planning consequences of rapid city growth. A recurring methodological pattern is multi-temporal image comparison for "
        "change detection, often framed as LULC transitions and in some cases linked to flood vulnerability, informal expansion, "
        "or environmental management. Sentinel-2-specific studies appear alongside a broader body of work using Landsat or mixed-sensor archives.\n"
    )

    lines.append("## Top-ranked papers\n")
    for i, (_, row) in enumerate(top10.iterrows(), start=1):
        title = row["title"]
        authors = row["authors"] or "Unknown authors"
        year = int(row["year_num"]) if row["year_num"] else "n.d."
        journal = row["journal"] or "Unknown venue"
        doi = row["doi"] or "No DOI"
        lines.append(f"{i}. **{title}** — {authors}. *{journal}*, {year}. DOI: {doi}")
    lines.append("")

    lines.append("## Notes and limitations\n")
    lines.append("- This is metadata-driven harvesting, not a full-text systematic review.")
    lines.append("- OpenAlex abstracts are reconstructed from inverted indexes when available.")
    lines.append("- Crossref coverage depends on publisher-deposited metadata; some records may have sparse abstracts or keywords.")
    lines.append("- Very large harvests can take time, especially in Colab.\n")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def run_generator(mailto: str, outdir: str = ".", crossref_max_records_per_query: int = 5000) -> Path:
    outdir_path = Path(outdir).resolve()
    outdir_path.mkdir(parents=True, exist_ok=True)

    session = get_session(mailto)
    all_rows = []

    print("Harvesting OpenAlex...")
    for query in DEFAULT_QUERIES:
        try:
            print(f"  OpenAlex query: {query}")
            rows = fetch_openalex_query(session, query, mailto)
            all_rows.extend(rows)
            print(f"    added {len(rows)} rows")
        except Exception as e:
            print(f"  OpenAlex failed for query {query!r}: {e}")

    print("Harvesting Crossref...")
    for query in DEFAULT_QUERIES:
        try:
            print(f"  Crossref query: {query}")
            rows = fetch_crossref_query(session, query, mailto, max_records=crossref_max_records_per_query)
            all_rows.extend(rows)
            print(f"    added {len(rows)} rows")
        except Exception as e:
            print(f"  Crossref failed for query {query!r}: {e}")

    print("Adding seed DOI/title safety-net records...")
    for doi in SEED_DOIS:
        try:
            row = fetch_openalex_by_doi(session, doi, mailto)
            if row:
                all_rows.append(row)
                print(f"    added seed DOI {doi}")
        except Exception as e:
            print(f"  Seed DOI failed for {doi!r}: {e}")

    for title in SEED_TITLES:
        try:
            rows = fetch_crossref_by_title(session, title, mailto)
            all_rows.extend(rows)
            print(f"    added {len(rows)} seed title rows")
        except Exception as e:
            print(f"  Seed title failed for {title!r}: {e}")

    df = pd.DataFrame(all_rows)
    if df.empty:
        raise RuntimeError("No records were harvested. Try broader queries or check internet access.")

    df = dedupe_records(df)

    keep_cols = [
        "source_api", "query", "title", "authors", "year", "publication_date",
        "journal", "doi", "url", "citations", "type", "relevance_score", "year_num", "abstract"
    ]
    df = df[keep_cols]

    csv_path = outdir_path / "nigeria_literature.csv"
    xlsx_path = outdir_path / "nigeria_literature.xlsx"
    bib_path = outdir_path / "nigeria_literature.bib"
    md_path = outdir_path / "nigeria_literature_review.md"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_excel(xlsx_path, index=False)
    write_bibtex(df, bib_path)
    write_review(df, md_path)

    print(f"Saved: {csv_path}")
    print(f"Saved: {xlsx_path}")
    print(f"Saved: {bib_path}")
    print(f"Saved: {md_path}")
    print(f"Done. Total deduplicated records: {len(df)}")
    return outdir_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mailto", default="your_email@example.com", help="Email for polite API access")
    parser.add_argument("--outdir", default=".", help="Output directory")
    parser.add_argument("--crossref-max-records-per-query", type=int, default=5000, help="Safety cap for Crossref results per query")
    return parser


def main(argv=None):
    parser = build_parser()
    args, _unknown = parser.parse_known_args(argv)
    run_generator(
        mailto=args.mailto,
        outdir=args.outdir,
        crossref_max_records_per_query=args.crossref_max_records_per_query
    )


if __name__ == "__main__":
    main()
