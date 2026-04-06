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


def print_search_hits(entries) -> None:
    for entry in entries:
        print(
            f"[{entry.tpo_label} #{entry.article_index}] {entry.title} | "
            f"{entry.subject} / {entry.subject_english}"
        )


def print_tpo_entries(entries) -> None:
    for entry in sorted(entries, key=lambda item: item.article_index):
        print(f"[{entry.article_index}] {entry.title} | {entry.subject} / {entry.subject_english}")


def parse_tpo_input(value: str) -> str:
    raw = value.strip().lower()
    if not raw:
        raise CrawlError("TPO input cannot be empty.")
    if raw.startswith("tpo"):
        return raw
    if raw.isdigit():
        return f"tpo{int(raw)}"
    raise CrawlError(f"Invalid TPO input: {value}")


def parse_article_selection(value: str) -> list[int]:
    cleaned = value.strip().lower()
    if not cleaned:
        raise CrawlError("Article selection cannot be empty.")
    if cleaned == "q":
        return []
    selected: list[int] = []
    for char in cleaned:
        if char in {"1", "2", "3"}:
            number = int(char)
            if number not in selected:
                selected.append(number)
    if not selected:
        raise CrawlError("Please enter 1, 2, 3, or a combination like 12 or 123.")
    return selected


def handle_search(catalog) -> None:
    print("How would you like to filter?")
    print("[1] TPO number")
    print("[2] Article name")
    print("[3] Article category")
    mode = input("Press a key: ").strip().lower()

    if mode == "1":
        tpo = parse_tpo_input(input("Enter TPO number: ").strip())
        hits = [entry for entry in catalog if entry.tpo_label.lower() == tpo]
    elif mode == "2":
        keyword = input("Enter article name keyword: ").strip()
        hits = [
            entry for entry in catalog
            if keyword.lower() in entry.title.lower()
        ]
    elif mode == "3":
        keyword = input("Enter article category: ").strip()
        hits = [
            entry for entry in catalog
            if keyword.lower() in entry.subject.lower()
            or keyword.lower() in entry.subject_english.lower()
        ]
    else:
        print("Invalid choice. Returning to main menu.")
        return

    if not hits:
        print("No results found.")
        return
    print_search_hits(hits[:100])


def handle_export(catalog, output_root: Path) -> None:
    tpo = parse_tpo_input(input("Which TPO? ").strip())
    hits = [entry for entry in catalog if entry.tpo_label.lower() == tpo]
    if not hits:
        print(f"No indexed entries found for: {tpo}")
        return

    print_tpo_entries(hits)
    selected_raw = input("Which article? (1 / 2 / 3 / 12 / 123, q to cancel): ").strip()
    selected_articles = parse_article_selection(selected_raw)
    if not selected_articles:
        return

    for article_index in selected_articles:
        selected_entry = next(
            (entry for entry in hits if entry.article_index == article_index),
            None,
        )
        if selected_entry is None:
            continue
        exported = export_article(selected_entry.tpo_label, selected_entry.article_index)
        target_dir = export_to_directory(exported, output_root)
        print(f"Exported to: {target_dir}")


def get_catalog(catalog_root: Path, refresh: bool = False):
    if refresh:
        return refresh_catalog(catalog_root)
    try:
        return load_catalog(catalog_root)
    except CrawlError:
        return refresh_catalog(catalog_root)


def run_interactive(output_root: Path, catalog_root: Path) -> int:
    catalog = get_catalog(catalog_root)
    print(f"Catalog loaded: {catalog_root / 'article_index.json'}")
    while True:
        print("")
        print("Choose an action:")
        print("[1] Search")
        print("[2] Create worksheet and save locally")
        print("[Q] Quit")

        choice = input("Press a key: ").strip().lower()
        if choice == "q":
            return 0

        if choice == "1":
            handle_search(catalog)
            continue

        if choice == "2":
            handle_export(catalog, output_root)
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
