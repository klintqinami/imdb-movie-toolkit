#!/usr/bin/env python3
import argparse
import datetime as dt
import re
from typing import Iterable

import pandas as pd

from imdb_utils import (
    add_filter_args,
    add_imdb_paths_args,
    add_last_n_years_arg,
    add_runtime_args,
    add_sort_format_args,
    add_title_type_arg,
    add_year_range_args,
    read_tsv_auto,
)

def load_data(basics_path: str, ratings_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("Loading data...")
    basics = read_tsv_auto(basics_path)
    ratings = read_tsv_auto(ratings_path)
    return basics, ratings


def parse_genre_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_genre_pattern(genres: list[str]) -> str:
    escaped = [re.escape(g) for g in genres]
    return "|".join(escaped)


def apply_genre_filters(
    df: pd.DataFrame,
    include_genres: list[str],
    exclude_genres: list[str],
) -> pd.DataFrame:
    df["genres"] = df["genres"].fillna("")
    if include_genres:
        pattern = build_genre_pattern(include_genres)
        df = df[df["genres"].str.contains(pattern, case=False, na=False)]
    if exclude_genres:
        pattern = build_genre_pattern(exclude_genres)
        df = df[~df["genres"].str.contains(pattern, case=False, na=False)]
    return df


def apply_runtime_filters(
    df: pd.DataFrame,
    min_runtime: int | None,
    max_runtime: int | None,
) -> pd.DataFrame:
    if min_runtime is None and max_runtime is None:
        return df
    df["runtimeMinutes"] = pd.to_numeric(df["runtimeMinutes"], errors="coerce")
    if min_runtime is not None:
        df = df[df["runtimeMinutes"] >= min_runtime]
    if max_runtime is not None:
        df = df[df["runtimeMinutes"] <= max_runtime]
    return df


def sort_titles(df: pd.DataFrame, sort_by: str) -> pd.DataFrame:
    if sort_by == "votes":
        df.sort_values(
            by=["numVotes", "averageRating"],
            ascending=[False, False],
            inplace=True,
        )
        return df
    if sort_by == "title":
        df.sort_values(by=["primaryTitle"], ascending=[True], inplace=True)
        return df
    df.sort_values(
        by=["averageRating", "numVotes"],
        ascending=[False, False],
        inplace=True,
    )
    return df


def filter_one_year(
    basics: pd.DataFrame,
    ratings: pd.DataFrame,
    year: int,
    min_votes: int,
    min_rating: float,
    title_type: str,
    include_genres: list[str],
    exclude_genres: list[str],
    min_runtime: int | None,
    max_runtime: int | None,
    sort_by: str,
    limit_per_year: int | None,
) -> pd.DataFrame:
    df = basics.merge(ratings, on="tconst", how="inner")

    df = df[df["titleType"] == title_type].copy()

    df["startYear"] = pd.to_numeric(df["startYear"], errors="coerce").astype("Int64")
    df = df[df["startYear"] == year]

    df = apply_genre_filters(df, include_genres, exclude_genres)

    df = df[
        (df["numVotes"] >= min_votes) &
        (df["averageRating"] >= min_rating)
    ].copy()

    df = apply_runtime_filters(df, min_runtime, max_runtime)
    df = sort_titles(df, sort_by)
    if limit_per_year:
        return df.head(limit_per_year).copy()
    return df


def format_movie_line(row: pd.Series) -> str:
    return (
        f"  {row['primaryTitle']} "
        f"(rating={row['averageRating']}, votes={row['numVotes']}, "
        f"genres={row['genres']}, id={row['tconst']})"
    )


def build_year_section(year: int, df: pd.DataFrame) -> list[str]:
    lines = [str(year)]
    if df.empty:
        return lines + ["  (no titles)", ""]
    lines.extend(format_movie_line(row) for _, row in df.iterrows())
    lines.append("")
    return lines


def build_output(
    basics: pd.DataFrame,
    ratings: pd.DataFrame,
    years: Iterable[int],
    min_votes: int,
    min_rating: float,
    title_type: str,
    include_genres: list[str],
    exclude_genres: list[str],
    min_runtime: int | None,
    max_runtime: int | None,
    sort_by: str,
    limit_per_year: int | None,
) -> list[str]:
    out_lines: list[str] = []
    for year in years:
        print(f"Processing {year}...")
        df = filter_one_year(
            basics,
            ratings,
            year=year,
            min_votes=min_votes,
            min_rating=min_rating,
            title_type=title_type,
            include_genres=include_genres,
            exclude_genres=exclude_genres,
            min_runtime=min_runtime,
            max_runtime=max_runtime,
            sort_by=sort_by,
            limit_per_year=limit_per_year,
        )
        out_lines.extend(build_year_section(year, df))
    return out_lines


def collect_rows(
    basics: pd.DataFrame,
    ratings: pd.DataFrame,
    years: Iterable[int],
    min_votes: int,
    min_rating: float,
    title_type: str,
    include_genres: list[str],
    exclude_genres: list[str],
    min_runtime: int | None,
    max_runtime: int | None,
    sort_by: str,
    limit_per_year: int | None,
) -> pd.DataFrame:
    frames = []
    for year in years:
        print(f"Processing {year}...")
        df = filter_one_year(
            basics,
            ratings,
            year=year,
            min_votes=min_votes,
            min_rating=min_rating,
            title_type=title_type,
            include_genres=include_genres,
            exclude_genres=exclude_genres,
            min_runtime=min_runtime,
            max_runtime=max_runtime,
            sort_by=sort_by,
            limit_per_year=limit_per_year,
        )
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def write_output(lines: list[str], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def resolve_years(
    start_year: int,
    end_year: int,
    last_n_years: int | None,
) -> range:
    if last_n_years:
        if last_n_years < 1:
            raise ValueError("--last-n-years must be >= 1")
        end_year = dt.date.today().year
        start_year = end_year - last_n_years + 1
    if start_year > end_year:
        raise ValueError("start-year must be <= end-year")
    return range(start_year, end_year + 1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Aggregate IMDb movies into a single text file."
    )
    add_imdb_paths_args(parser)
    add_year_range_args(parser)
    add_last_n_years_arg(parser)
    add_filter_args(parser)
    add_runtime_args(parser)
    add_sort_format_args(parser)
    add_title_type_arg(parser)
    parser.add_argument("--output", default="movies_by_year.txt", help="Output text file")
    return parser.parse_args()


def main():
    args = parse_args()

    basics, ratings = load_data(args.basics_path, args.ratings_path)
    try:
        years = resolve_years(args.start_year, args.end_year, args.last_n_years)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    include_genres = parse_genre_list(args.include_genres)
    exclude_genres = parse_genre_list(args.exclude_genres)
    if args.genre:
        include_genres.append(args.genre)

    if args.format == "text":
        out_lines = build_output(
            basics,
            ratings,
            years=years,
            min_votes=args.min_votes,
            min_rating=args.min_rating,
            title_type=args.title_type,
            include_genres=include_genres,
            exclude_genres=exclude_genres,
            min_runtime=args.min_runtime,
            max_runtime=args.max_runtime,
            sort_by=args.sort_by,
            limit_per_year=args.limit_per_year,
        )
        write_output(out_lines, args.output)
        print(f"Done. Wrote {args.output}")
        return

    df = collect_rows(
        basics,
        ratings,
        years=years,
        min_votes=args.min_votes,
        min_rating=args.min_rating,
        title_type=args.title_type,
        include_genres=include_genres,
        exclude_genres=exclude_genres,
        min_runtime=args.min_runtime,
        max_runtime=args.max_runtime,
        sort_by=args.sort_by,
        limit_per_year=args.limit_per_year,
    )
    columns = [
        "tconst",
        "primaryTitle",
        "startYear",
        "averageRating",
        "numVotes",
        "genres",
        "runtimeMinutes",
        "titleType",
    ]
    if df.empty:
        df = pd.DataFrame(columns=columns)
    else:
        columns = [col for col in columns if col in df.columns]
        df = df[columns]
    if args.format == "csv":
        df.to_csv(args.output, index=False)
    else:
        df.to_json(args.output, orient="records", indent=2)
    print(f"Done. Wrote {args.output}")


if __name__ == "__main__":
    main()
