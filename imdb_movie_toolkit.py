#!/usr/bin/env python3
import argparse
import datetime as dt
import html
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


def format_runtime(runtime: float | int | None) -> str:
    if runtime is None or pd.isna(runtime):
        return "NA"
    return f"{int(runtime)} min"


def format_votes(votes: float | int | None) -> str:
    if votes is None or pd.isna(votes):
        return "NA"
    return f"{int(votes):,}"


def format_rating(rating: float | int | None) -> str:
    if rating is None or pd.isna(rating):
        return "NA"
    return f"{float(rating):.1f}"


def build_html_header(title: str, subtitle: str, nav_html: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f6f2ea;
      --bg-accent: #fdf9f2;
      --ink: #1c1a17;
      --muted: #5a534a;
      --card: #fffaf3;
      --accent: #2b6f5f;
      --accent-2: #cf7c4a;
      --border: #e7dccf;
      --shadow: 0 20px 50px rgba(0, 0, 0, 0.08);
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      font-family: "Space Grotesk", "Avenir Next", "Avenir", sans-serif;
      color: var(--ink);
      background: radial-gradient(circle at 10% 10%, #efe3d6, transparent 45%),
        radial-gradient(circle at 80% 20%, #f6efe5, transparent 40%),
        linear-gradient(145deg, var(--bg), var(--bg-accent));
      min-height: 100vh;
    }}
    .page {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 48px 24px 64px;
    }}
    .hero {{
      display: grid;
      gap: 16px;
      margin-bottom: 32px;
    }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.2em;
      font-size: 12px;
      color: var(--accent);
      font-weight: 700;
    }}
    h1 {{
      font-family: "Fraunces", "Baskerville", serif;
      font-size: clamp(32px, 4vw, 52px);
      margin: 0;
    }}
    .subtitle {{
      font-size: 18px;
      color: var(--muted);
      margin: 0;
      max-width: 70ch;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin: 24px 0 40px;
    }}
    .year-nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 16px 0 0;
    }}
    .year-nav a {{
      text-decoration: none;
      color: var(--accent);
      font-weight: 600;
      font-size: 13px;
      padding: 6px 12px;
      border-radius: 999px;
      border: 1px solid rgba(43, 111, 95, 0.25);
      background: rgba(43, 111, 95, 0.08);
    }}
    .year-nav a:hover {{
      background: rgba(43, 111, 95, 0.18);
    }}
    .meta-card {{
      padding: 16px 18px;
      border-radius: 16px;
      background: var(--card);
      border: 1px solid var(--border);
      box-shadow: var(--shadow);
    }}
    .meta-card h3 {{
      margin: 0 0 6px;
      font-size: 14px;
      color: var(--muted);
      font-weight: 600;
    }}
    .meta-card p {{
      margin: 0;
      font-size: 18px;
      font-weight: 700;
      color: var(--ink);
    }}
    .year-section {{
      margin-bottom: 36px;
    }}
    .year-title {{
      display: flex;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 16px;
    }}
    .year-title h2 {{
      margin: 0;
      font-size: 28px;
      font-weight: 700;
    }}
    .year-title span {{
      font-size: 14px;
      color: var(--muted);
    }}
    .back-to-top {{
      position: fixed;
      right: 24px;
      bottom: 24px;
      font-size: 12px;
      text-decoration: none;
      color: #fff;
      font-weight: 700;
      background: var(--accent-2);
      padding: 10px 14px;
      border-radius: 999px;
      box-shadow: 0 12px 28px rgba(207, 124, 74, 0.35);
      z-index: 20;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }}
    .movie-card {{
      background: var(--card);
      border-radius: 18px;
      padding: 12px 14px;
      border: 1px solid var(--border);
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
      animation: fadeUp 0.6s ease both;
      animation-delay: calc(var(--i) * 45ms);
    }}
    .movie-card::after {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(130deg, rgba(43, 111, 95, 0.08), transparent 45%);
      opacity: 0;
      transition: opacity 0.3s ease;
    }}
    .movie-card:hover::after {{
      opacity: 1;
    }}
    .movie-card h3 {{
      margin: 0 0 6px;
      font-size: 16px;
      font-weight: 700;
      position: relative;
      z-index: 1;
    }}
    .movie-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      font-size: 12px;
      color: var(--muted);
      position: relative;
      z-index: 1;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 3px 8px;
      border-radius: 999px;
      background: rgba(207, 124, 74, 0.15);
      color: #7a3e1e;
      font-weight: 600;
      font-size: 11px;
    }}
    details.movie-details {{
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
      position: relative;
      z-index: 1;
    }}
    details.movie-details summary {{
      cursor: pointer;
      color: var(--accent-2);
      font-weight: 600;
      list-style: none;
    }}
    details.movie-details summary::-webkit-details-marker {{
      display: none;
    }}
    .details-content {{
      margin-top: 6px;
      display: grid;
      gap: 4px;
    }}
    .footer {{
      margin-top: 48px;
      font-size: 12px;
      color: var(--muted);
      text-align: center;
    }}
    @keyframes fadeUp {{
      from {{ opacity: 0; transform: translateY(8px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
  </style>
</head>
<body>
  <div class="page" id="top">
    <header class="hero">
      <div class="eyebrow">IMDb Movie Toolkit</div>
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">{html.escape(subtitle)}</p>
      {nav_html}
    </header>
"""


def build_html_footer(generated_at: str) -> str:
    return f"""
    <div class="footer">Generated {html.escape(generated_at)} by imdb_movie_toolkit.py</div>
  </div>
</body>
</html>
"""


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


def build_html_page(
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
) -> str:
    years_list = list(years)
    title = f"{years_list[0]}-{years_list[-1]} {title_type.title()}s"
    filters = []
    filters.append(f"Min votes: {min_votes}")
    filters.append(f"Min rating: {min_rating}")
    if include_genres:
        filters.append(f"Include genres: {', '.join(include_genres)}")
    if exclude_genres:
        filters.append(f"Exclude genres: {', '.join(exclude_genres)}")
    if min_runtime is not None or max_runtime is not None:
        min_r = min_runtime if min_runtime is not None else 0
        max_r = max_runtime if max_runtime is not None else "any"
        filters.append(f"Runtime: {min_r}-{max_r} min")
    filters.append(f"Sort by: {sort_by}")
    if limit_per_year:
        filters.append(f"Limit per year: {limit_per_year}")

    total_titles = 0
    sections = []
    years_with_titles: list[int] = []
    for year in years_list:
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
        total_titles += len(df)
        if df.empty:
            continue
        years_with_titles.append(year)
        cards = []
        for idx, (_, row) in enumerate(df.iterrows(), start=1):
            cards.append(
                f"""
        <article class="movie-card" style="--i: {idx}">
          <h3>{html.escape(str(row.get('primaryTitle', 'Untitled')))}</h3>
          <div class="movie-meta">
            <div class="pill">Rating {format_rating(row.get('averageRating'))}</div>
            <div>Votes: {format_votes(row.get('numVotes'))}</div>
            <div>Runtime: {format_runtime(row.get('runtimeMinutes'))}</div>
          </div>
          <details class="movie-details">
            <summary>More details</summary>
            <div class="details-content">
              <div>Genres: {html.escape(str(row.get('genres', '') or ''))}</div>
              <div>Year: {html.escape(str(row.get('startYear', '')))}</div>
              <div>Type: {html.escape(str(row.get('titleType', '')))}</div>
              <div>IMDb ID: {html.escape(str(row.get('tconst', '')))}</div>
            </div>
          </details>
        </article>
                """.rstrip()
            )
        section = f"""
      <section class="year-section" id="year-{year}">
        <div class="year-title">
          <h2>{year}</h2>
          <span>{len(df)} titles</span>
        </div>
        <div class="grid">
          {''.join(cards)}
        </div>
      </section>
        """.rstrip()
        sections.append(section)

    subtitle = " | ".join(filters)
    if years_with_titles:
        year_links = "".join(f'<a href="#year-{year}">{year}</a>' for year in years_with_titles)
        nav_html = f'<nav class="year-nav">{year_links}</nav>'
    else:
        nav_html = ""
    header = build_html_header(title, subtitle, nav_html)
    meta = f"""
    <section class="meta-grid">
      <div class="meta-card">
        <h3>Years</h3>
        <p>{years_list[0]} to {years_list[-1]}</p>
      </div>
      <div class="meta-card">
        <h3>Title type</h3>
        <p>{html.escape(title_type)}</p>
      </div>
      <div class="meta-card">
        <h3>Total titles</h3>
        <p>{total_titles}</p>
      </div>
    </section>
    """.rstrip()
    body = "\n".join(sections) if sections else "<p>No titles matched your filters.</p>"
    footer = build_html_footer(dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    back_to_top = '<a class="back-to-top" href="#top">Back to top</a>'
    return header + meta + body + back_to_top + footer


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

    if args.format == "html":
        html_page = build_html_page(
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
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html_page)
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
