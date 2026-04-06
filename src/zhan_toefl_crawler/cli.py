from __future__ import annotations

import argparse
from pathlib import Path

from .crawler import (
    CrawlError,
    export_article,
    export_to_directory,
    list_articles,
    list_subjects,
    load_catalog,
    refresh_catalog,
    search_catalog,
)


INDEX_ROOT = Path("data")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zhan-toefl",
        description="Crawl Zhan TOEFL reading passages and export worksheets.",
    )
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="List articles under a TPO.")
    list_parser.add_argument("tpo", help="Example: tpo33")

    export_parser = subparsers.add_parser("export", help="Export a specific article.")
    export_parser.add_argument("tpo", help="Example: tpo33")
    export_parser.add_argument("article", type=int, help="Article number, usually 1-3")
    export_parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="Output directory root",
    )

    search_parser = subparsers.add_parser("search", help="Search local catalog by keyword.")
    search_parser.add_argument("keyword", help="Keyword in TPO, title, or subject")

    subparsers.add_parser("subjects", help="Show available subjects from local catalog.")
    subparsers.add_parser("index", help="Refresh local catalog files.")

    return parser


def print_catalog_hits(entries) -> None:
    for entry in entries:
        print(
            f"[{entry.tpo_label} #{entry.article_index}] {entry.title} | "
            f"{entry.subject} / {entry.subject_english} | article_id={entry.article_id}"
        )


def get_catalog(catalog_root: Path, refresh: bool = False):
    if refresh:
        return refresh_catalog(catalog_root)
    try:
        return load_catalog(catalog_root)
    except CrawlError:
        return refresh_catalog(catalog_root)


def run_interactive(output_root: Path, catalog_root: Path) -> int:
    catalog = refresh_catalog(catalog_root)
    print(f"Catalog refreshed: {catalog_root / 'article_index.json'}")
    while True:
        print("")
        print("Choose an action:")
        print("[1] Search TPO or keyword")
        print("[2] Export worksheet")
        print("[Q] Quit")

        choice = input("Press a key: ").strip().lower()
        if choice == "q":
            return 0

        if choice == "1":
            keyword = input("Enter TPO or keyword: ").strip()
            if keyword.lower().startswith("tpo"):
                hits = [entry for entry in catalog if entry.tpo_label.lower() == keyword.lower()]
            else:
                hits = search_catalog(catalog, keyword)
            if not hits:
                print(f"No matches found for: {keyword}")
                continue
            print_catalog_hits(hits[:50])
            continue

        if choice == "2":
            tpo = input("Enter TPO (example: tpo33): ").strip()
            articles = list_articles(tpo)
            for article in articles:
                suffix = f" | {article.category}" if getattr(article, "category", "") else ""
                print(f"[{article.article_index}] {article.title}{suffix}")
            selected = int(input("Select article number: ").strip())
            exported = export_article(tpo, selected)
            target_dir = export_to_directory(exported, output_root)
            print(f"Exported to: {target_dir}")
            continue

        print("Invalid choice. Please press 1, 2, or Q.")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "index":
            entries = refresh_catalog(INDEX_ROOT)
            print(f"Catalog refreshed: {len(entries)} articles")
            print(f"JSON: {INDEX_ROOT / 'article_index.json'}")
            print(f"CSV: {INDEX_ROOT / 'article_index.csv'}")
            return 0

        if args.command == "search":
            catalog = get_catalog(INDEX_ROOT)
            hits = search_catalog(catalog, args.keyword)
            print_catalog_hits(hits)
            return 0

        if args.command == "subjects":
            catalog = get_catalog(INDEX_ROOT)
            for subject in list_subjects(catalog):
                print(subject)
            return 0

        if args.command == "list":
            catalog = get_catalog(INDEX_ROOT)
            hits = [entry for entry in catalog if entry.tpo_label.lower() == args.tpo.lower()]
            if hits:
                print_catalog_hits(hits)
            else:
                articles = list_articles(args.tpo)
                for article in articles:
                    suffix = f" | {article.category}" if getattr(article, "category", "") else ""
                    print(f"[{article.article_index}] {article.title}{suffix} (article_id={article.article_id})")
            return 0

        if args.command == "export":
            exported = export_article(args.tpo, args.article)
            target_dir = export_to_directory(exported, args.output)
            print(f"Exported to: {target_dir}")
            return 0

        return run_interactive(Path("output"), INDEX_ROOT)
    except CrawlError as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
