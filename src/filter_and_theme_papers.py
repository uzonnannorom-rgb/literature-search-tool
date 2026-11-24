#!/usr/bin/env python3
"""
Step 2 of the literature search workflow.

Merges one or more CSV files produced by the search script, removes
duplicates, keeps recent and well-cited journal papers, and groups
them into themes using keywords.

Usage:
    python filter_and_theme_papers.py file1.csv file2.csv file3.csv
    python filter_and_theme_papers.py *.csv --min-year 2015 --min-citations 20 --out shortlist.csv
"""

import argparse

import pandas as pd

COMMON_COLS = ['title', 'authors', 'year', 'journal', 'doi', 'citations', 'type', 'query']

# Edit these themes and keywords for a new topic.
THEMES = {
    'T1_Urbanisation_Nigeria': ['nigeria', 'lagos', 'abuja', 'kano', 'benin', 'enugu', 'west africa', 'african city'],
    'T2_Sentinel2_LULC': ['sentinel-2', 'sentinel2', 'land cover', 'land use', 'lulc', 'classification'],
    'T3_ML_Classification': ['random forest', 'support vector', 'machine learning', 'deep learning', 'cnn', 'neural network', 'classification'],
    'T4_Change_Detection': ['change detection', 'temporal', 'multi-temporal', 'transition'],
    'T5_Urban_Expansion': ['urban expansion', 'urban growth', 'urban sprawl', 'built-up'],
    'T6_Prediction_Modelling': ['predict', 'markov', 'cellular automata', 'simulation', 'future'],
}


def assign_theme(row):
    text = (str(row['title']) + ' ' + str(row['query'])).lower()
    for theme, keywords in THEMES.items():
        if any(k in text for k in keywords):
            return theme
    return 'Other'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_files', nargs='+', help='CSV files from the search script')
    parser.add_argument('--min-year', type=int, default=2015)
    parser.add_argument('--min-citations', type=int, default=20)
    parser.add_argument('--recent-year', type=int, default=2021,
                        help='Papers from this year on are kept even with few citations')
    parser.add_argument('--top', type=int, default=8, help='Papers to print per theme')
    parser.add_argument('--out', default='shortlist.csv')
    args, _unknown = parser.parse_known_args()

    frames = [pd.read_csv(f, encoding='utf-8-sig')[COMMON_COLS] for f in args.csv_files]
    df_all = pd.concat(frames, ignore_index=True)

    # Clean
    df_all['year'] = pd.to_numeric(df_all['year'], errors='coerce')
    df_all['citations'] = pd.to_numeric(df_all['citations'], errors='coerce').fillna(0)
    df_all = df_all.dropna(subset=['title', 'year']).drop_duplicates(subset=['title'])

    # Filter: journal articles/reviews from min-year on, with enough citations or published recently
    recent = df_all[
        (df_all['year'] >= args.min_year) &
        (df_all['type'].isin(['article', 'review', 'journal-article'])) &
        ((df_all['citations'] >= args.min_citations) | (df_all['year'] >= args.recent_year))
    ].sort_values('citations', ascending=False).copy()

    recent['theme'] = recent.apply(assign_theme, axis=1)

    print(f'Papers after filtering: {len(recent)}')
    for theme in THEMES:
        subset = recent[recent['theme'] == theme].head(args.top)
        if len(subset):
            print(f"\n{'=' * 60}\nTHEME: {theme}\n{'=' * 60}")
            for _, row in subset.iterrows():
                print(f"  [{int(row['year'])}] {row['citations']:.0f} cit. | {str(row['title'])[:80]}")
                print(f"         Authors: {str(row['authors'])[:60]}")
                print(f"         Journal: {str(row['journal'])[:50]}\n")

    recent.to_csv(args.out, index=False, encoding='utf-8-sig')
    print(f'\nSaved: {args.out}')


if __name__ == '__main__':
    main()
