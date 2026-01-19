#!/usr/bin/env python3
import argparse
from pathlib import Path

import pandas as pd


def read_tsv_auto(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.suffix == ".gz":
        return pd.read_csv(path, sep="\t", na_values="\\N", compression="gzip", low_memory=False)
    return pd.read_csv(path, sep="\t", na_values="\\N", low_memory=False)


def add_imdb_paths_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--basics-path", required=True, help="Path to title.basics.tsv or .tsv.gz")
    parser.add_argument("--ratings-path", required=True, help="Path to title.ratings.tsv or .tsv.gz")


def add_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--min-votes", type=int, default=500, help="Minimum votes (default 500)")
    parser.add_argument("--min-rating", type=float, default=6.5, help="Minimum rating (default 6.5)")
    parser.add_argument("--genre", help="Optional genre filter (single value, case-insensitive)")
    parser.add_argument(
        "--include-genres",
        help="Comma-separated list; keep titles matching ANY of these genres",
    )
    parser.add_argument(
        "--exclude-genres",
        help="Comma-separated list; drop titles matching ANY of these genres",
    )


def add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--min-runtime", type=int, help="Minimum runtime in minutes")
    parser.add_argument("--max-runtime", type=int, help="Maximum runtime in minutes")


def add_sort_format_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--sort-by",
        default="rating",
        choices=["rating", "votes", "title"],
        help="Sort within each year (default rating)",
    )
    parser.add_argument(
        "--format",
        default="text",
        choices=["text", "csv", "json"],
        help="Output format (default text)",
    )
    parser.add_argument(
        "--limit-per-year",
        type=int,
        help="Maximum number of rows per year (default no limit)",
    )


def add_title_type_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--title-type",
        default="movie",
        help="IMDb titleType to include (default movie)",
    )


def add_last_n_years_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--last-n-years",
        type=int,
        help="Override start/end years to include only the most recent N years",
    )


def add_year_range_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start-year", type=int, default=2000, help="First year (default 2000)")
    parser.add_argument("--end-year", type=int, default=2025, help="Last year inclusive (default 2025)")
