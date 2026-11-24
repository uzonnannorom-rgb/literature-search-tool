# Literature Search Tool

Python tools for searching academic literature through the free **OpenAlex** and **Crossref** APIs, extracting abstracts, and screening the results into a themed shortlist.

First built for my MSc Data Science dissertation on land use/land cover change and urban expansion in Enugu, Nigeria (Liverpool John Moores University, 2026).

## How it works

The workflow has two steps.

**Step 1: Search** (`src/nigeria_lit_review_generator_fixed_v2.py`)

- Runs keyword queries against OpenAlex and Crossref
- Rebuilds OpenAlex abstracts from their word index and strips XML tags from Crossref abstracts
- Keeps only records that match the place names of interest
- Removes duplicates by DOI, or by title when there is no DOI
- Gives each paper a keyword relevance score, then ranks by score, citations and year
- Saves a CSV, an Excel file, a BibTeX file and an automatic Markdown summary

**Step 2: Filter and theme** (`src/filter_and_theme_papers.py`)

- Merges one or more CSV files from Step 1
- Removes duplicate titles
- Keeps journal articles and reviews from a chosen year with enough citations, or published recently
- Groups papers into themes by keyword and saves a shortlist CSV

The final reading list is then chosen by hand from the shortlist.

## Setup

```bash
pip install -r requirements.txt
```

## Running it

Step 1 (use your own email so the APIs can contact you if needed):

```bash
python src/nigeria_lit_review_generator_fixed_v2.py --mailto your_email@example.com --outdir results
```

Step 2:

```bash
python src/filter_and_theme_papers.py results/nigeria_literature.csv --min-year 2015 --min-citations 20 --out results/shortlist.csv
```

Both scripts also run in Google Colab or Jupyter.

## Reusing it for a new topic

In `src/nigeria_lit_review_generator_fixed_v2.py`, edit:

- `DEFAULT_QUERIES`: the search queries
- `NIGERIA_TERMS`: the place names a paper must mention to be kept
- `TOPIC_TERMS`: the keywords used for the relevance score
- `SEED_DOIS` and `SEED_TITLES`: papers you always want included
- The output file names near the end of `run_generator()`

In `src/filter_and_theme_papers.py`, edit `THEMES` with your own themes and keywords.

## Example: Enugu LULC dissertation

`examples/enugu-lulc-dissertation/` holds the outputs from the original project:

| File | Contents |
|---|---|
| `search_results/nigeria_literature.csv` | 4,192 papers from Step 1 (OpenAlex and Crossref), with abstracts |
| `search_results/nigeria_literature.bib` | The same papers as BibTeX |
| `search_results/nigeria_literature_review.md` | Automatic summary of the search results |
| `search_results/nigeria_related_literature.csv` | 143 papers from an earlier version of the search script |
| `search_results/related_literature_sentinel2_urban_growth.csv` | 396 papers from an earlier version of the search script |
| `final_selection/final_22_papers_merged_for_downloads.xlsx` | The final 22 papers chosen for the literature review |

The two earlier files have no abstract or relevance score columns, because the earlier version of the script did not collect them.

## Notes and limitations

- This is metadata-based screening, not a full-text systematic review.
- Not every paper has an abstract in OpenAlex or Crossref.
- The automatic Markdown summary is a starting point, not a finished literature review.
- Large searches can take several minutes because the scripts pause between requests to respect the APIs.
