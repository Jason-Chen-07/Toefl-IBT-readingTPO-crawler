from __future__ import annotations

import json
import re
import ssl
import time
from dataclasses import asdict, dataclass
from html import escape, unescape
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_INDEX_URL = "https://top.zhan.com/toefl/read/alltpo.html"
BASE_TPO_URL = "https://top.zhan.com/toefl/read/alltpo{number}.html"
INDEX_DIRNAME = "index"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)

PRINT_STYLES = """
<style>
  @page {
    size: A4;
    margin: 10mm;
  }

  :root {
    --paper: #fffdf8;
    --ink: #1f2937;
    --muted: #6b7280;
    --line: #ded7cb;
    --accent: #8f5c38;
    --accent-soft: #f4eadf;
    --panel: #fffaf2;
  }

  * {
    box-sizing: border-box;
  }

  body {
    margin: 0;
    color: var(--ink);
    background: #efe8dc;
    font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
    line-height: 1.62;
  }

  .page {
    width: 210mm;
    min-height: 297mm;
    margin: 0 auto 16px;
    background: var(--paper);
    box-shadow: 0 14px 40px rgba(37, 26, 17, 0.14);
  }

  .cover {
    padding: 14mm 14mm 12mm;
    page-break-after: always;
  }

  .kicker {
    color: var(--accent);
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-bottom: 10px;
  }

  h1, h2, h3 {
    margin: 0;
    font-weight: 700;
    color: #24190f;
  }

  h1 {
    font-size: 24px;
    line-height: 1.2;
    margin-bottom: 8px;
  }

  .subtitle {
    color: var(--muted);
    font-size: 14px;
    margin-bottom: 20px;
  }

  .passage-box {
    border: 1px solid var(--line);
    background: linear-gradient(180deg, #fffefb, var(--panel));
    border-radius: 14px;
    padding: 11mm 10mm;
  }

  .passage-text {
    font-size: 11.4pt;
    white-space: pre-wrap;
    text-align: justify;
  }

  .question-page {
    min-height: 297mm;
    page-break-before: always;
    padding: 12mm 12mm 10mm;
  }

  .question-header {
    margin-bottom: 10px;
  }

  .question-grid {
    column-count: 2;
    column-gap: 12px;
  }

  .panel-title {
    font-size: 17px;
    margin-bottom: 6px;
  }

  .panel-note {
    font-size: 10px;
    color: var(--muted);
    margin-bottom: 8px;
  }

  .question {
    margin-bottom: 10px;
    break-inside: avoid;
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 8px 10px;
    background: #fffdfa;
    display: inline-block;
    width: 100%;
  }

  .question-number {
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 4px;
  }

  .prompt {
    font-size: 10pt;
    line-height: 1.42;
    margin-bottom: 7px;
  }

  .option {
    font-size: 9.3pt;
    line-height: 1.35;
    margin: 3px 0;
  }

  .answer-line {
    margin-top: 8px;
    padding-top: 6px;
    border-top: 1px dashed var(--line);
    color: var(--muted);
    font-size: 9.5pt;
  }

  .correct-answer {
    display: inline-block;
    margin-top: 6px;
    padding: 4px 8px;
    border-radius: 999px;
    background: var(--accent-soft);
    color: #6f4527;
    font-size: 9.5pt;
  }

  .answer-sheet {
    padding: 14mm 14mm 12mm;
    page-break-before: always;
  }

  .answer-list {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px 18px;
    margin-top: 12px;
  }

  .answer-item {
    border-bottom: 1px dashed var(--line);
    padding: 4px 0;
    font-size: 11pt;
  }

  @media print {
    body {
      background: white;
    }

    .page {
      width: auto;
      min-height: auto;
      margin: 0;
      box-shadow: none;
    }

    .question-grid {
      column-gap: 10px;
    }
  }
</style>
"""


class CrawlError(RuntimeError):
    pass


@dataclass
class ArticleEntry:
    tpo_label: str
    article_index: int
    article_id: int
    title: str
    category: str
    review_url: str


@dataclass
class CatalogEntry:
    tpo_label: str
    official_number: int
    article_index: int
    article_id: int
    title: str
    subject: str
    subject_english: str
    review_url: str
    source_page: str


SUBJECT_ENGLISH_MAP = {
    "人口统计学": "Demography",
    "人类学": "Anthropology",
    "农业": "Agriculture",
    "动物学": "Zoology",
    "化学": "Chemistry",
    "医学": "Medicine",
    "历史": "History",
    "商业": "Business",
    "地理学": "Geography",
    "天文学": "Astronomy",
    "心理学": "Psychology",
    "政治学": "Political Science",
    "教育": "Education",
    "材料科学": "Materials Science",
    "植物学": "Botany",
    "气象学": "Meteorology",
    "海洋生物学": "Marine Biology",
    "环境科学": "Environmental Science",
    "生态学": "Ecology",
    "生物学": "Biology",
    "社会学": "Sociology",
    "考古学": "Archaeology",
    "艺术史": "Art History",
    "地质学": "Geology",
    "经济学": "Economics",
    "语言学": "Linguistics",
    "物理学": "Physics",
}


@dataclass
class Question:
    index: int
    prompt: str
    options: list[str]
    correct_answer: str


@dataclass
class ArticleExport:
    tpo_label: str
    article_index: int
    article_id: int
    title: str
    review_url: str
    article_text: str
    questions: list[Question]


def normalize_tpo_label(value: str) -> tuple[str, int]:
    match = re.search(r"(\d+)", value.lower())
    if not match:
        raise CrawlError(f"Could not parse TPO number from: {value}")
    number = int(match.group(1))
    return f"tpo{number}", number


def fetch_text(url: str, timeout: int = 30, retries: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            },
        )
        context = ssl.create_default_context()
        try:
            with urlopen(request, timeout=timeout, context=context) as response:
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            raise CrawlError(f"HTTP error for {url}: {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(min(2 * attempt, 5))
    reason = getattr(last_error, "reason", str(last_error))
    raise CrawlError(f"Network error for {url}: {reason}")


def clean_html_text(html: str, preserve_breaks: bool = False) -> str:
    text = html
    text = re.sub(r"<br\s*/?>", "\n" if preserve_breaks else " ", text, flags=re.I)
    text = re.sub(r"</p>", "\n", text, flags=re.I)
    text = re.sub(r"<img[^>]*>", " ", text, flags=re.I)
    text = re.sub(r"<span[^>]*class=[\"']insert-area[\"'][^>]*data-answer=[\"']([A-D])[\"'][^>]*></span>", r"[\1]", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_article_cards(html: str, official_number: int) -> list[ArticleEntry]:
    card_pattern = re.compile(
        rf'alt="托福Official{official_number}阅读第(?P<idx>\d+)篇(?P<title>[^"]+?)题目解析"/>\s*'
        rf'<p class="cssImgBottomText">学科分类-(?P<category>[^<]+)<span[\s\S]*?'
        rf'article_type="Official{official_number}"\s+article_id="(?P<article_id>\d+)"[\s\S]*?'
        rf'href="(?P<review_url>https://top\.zhan\.com/toefl/read/practicereview-\d+-13\.html)"'
    )

    entries: list[ArticleEntry] = []
    for card in card_pattern.finditer(html):
        entries.append(
            ArticleEntry(
                tpo_label=f"tpo{official_number}",
                article_index=int(card.group("idx")),
                article_id=int(card.group("article_id")),
                title=clean_html_text(card.group("title")),
                category=clean_html_text(card.group("category")),
                review_url=card.group("review_url"),
            )
        )

    entries.sort(key=lambda item: item.article_index)
    if not entries:
        raise CrawlError(f"No article cards found for Official{official_number}.")
    return entries


def extract_catalog_entries(html: str, source_page: str) -> list[CatalogEntry]:
    pattern = re.compile(
        r'alt="托福Official(?P<official>\d+)阅读第(?P<idx>\d+)篇(?P<title>[^"]+?)题目解析"/>\s*'
        r'<p class="cssImgBottomText">学科分类-(?P<subject>[^<]+)<span[\s\S]*?'
        r'article_type="Official(?P=official)"\s+article_id="(?P<article_id>\d+)"[\s\S]*?'
        r'href="(?P<review_url>https://top\.zhan\.com/toefl/read/practicereview-\d+-13\.html)"'
    )
    entries: list[CatalogEntry] = []
    for match in pattern.finditer(html):
        official_number = int(match.group("official"))
        entries.append(
            CatalogEntry(
                tpo_label=f"tpo{official_number}",
                official_number=official_number,
                article_index=int(match.group("idx")),
                article_id=int(match.group("article_id")),
                title=clean_html_text(match.group("title")),
                subject=clean_html_text(match.group("subject")),
                subject_english=subject_to_english(clean_html_text(match.group("subject"))),
                review_url=match.group("review_url"),
                source_page=source_page,
            )
        )
    return entries


def subject_to_english(subject: str) -> str:
    return SUBJECT_ENGLISH_MAP.get(subject, subject)


def extract_group_page_urls(index_html: str) -> list[str]:
    found = re.findall(r"https://top\.zhan\.com/toefl/read/alltpo(?:\d+)?\.html", index_html)
    urls = list(dict.fromkeys([BASE_INDEX_URL, *found]))
    return urls


def refresh_catalog(output_root: Path) -> list[CatalogEntry]:
    output_root.mkdir(parents=True, exist_ok=True)
    index_html = fetch_text(BASE_INDEX_URL)
    page_urls = extract_group_page_urls(index_html)
    catalog: list[CatalogEntry] = []
    for url in page_urls:
        page_html = index_html if url == BASE_INDEX_URL else fetch_text(url)
        catalog.extend(extract_catalog_entries(page_html, url))

    deduped: dict[tuple[int, int], CatalogEntry] = {}
    for entry in catalog:
        deduped[(entry.official_number, entry.article_index)] = entry
    entries = sorted(
        deduped.values(),
        key=lambda item: (item.official_number, item.article_index),
    )
    write_catalog_files(entries, output_root)
    return entries


def write_catalog_files(entries: list[CatalogEntry], output_root: Path) -> None:
    json_path = output_root / "article_index.json"
    csv_path = output_root / "article_index.csv"
    payload = [asdict(entry) for entry in entries]
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = ["tpo_label,official_number,article_index,article_id,title,subject,review_url,source_page"]
    lines = ["tpo_label,official_number,article_index,article_id,title,subject,subject_english,review_url,source_page"]
    for entry in entries:
        row = [
            entry.tpo_label,
            str(entry.official_number),
            str(entry.article_index),
            str(entry.article_id),
            entry.title,
            entry.subject,
            entry.subject_english,
            entry.review_url,
            entry.source_page,
        ]
        escaped = ['"' + item.replace('"', '""') + '"' for item in row]
        lines.append(",".join(escaped))
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_catalog(output_root: Path) -> list[CatalogEntry]:
    json_path = output_root / "article_index.json"
    if not json_path.exists():
        raise CrawlError(f"Catalog file not found: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    return [CatalogEntry(**item) for item in payload]


def search_catalog(entries: list[CatalogEntry], keyword: str) -> list[CatalogEntry]:
    needle = keyword.strip().lower()
    if not needle:
        return entries
    return [
        entry
        for entry in entries
        if needle in entry.tpo_label.lower()
        or needle in entry.title.lower()
        or needle in entry.subject.lower()
        or needle in entry.subject_english.lower()
    ]


def list_subjects(entries: list[CatalogEntry]) -> list[str]:
    return sorted({entry.subject for entry in entries})


def list_articles(tpo_value: str) -> list[ArticleEntry]:
    _, number = normalize_tpo_label(tpo_value)
    index_html = fetch_text(BASE_INDEX_URL)
    try:
        return extract_article_cards(index_html, number)
    except CrawlError:
        dedicated_html = fetch_text(BASE_TPO_URL.format(number=number))
        return extract_article_cards(dedicated_html, number)


def extract_article_title(html: str) -> str:
    match = re.search(r'<span class="article_tit">(.*?)</span>', html, flags=re.S)
    if not match:
        raise CrawlError("Could not parse article title.")
    return clean_html_text(match.group(1))


def extract_article_text(html: str) -> str:
    match = re.search(
        r'<div class="article">([\s\S]*?)<span class="translation hide translationTmpl">',
        html,
        flags=re.S,
    )
    if not match:
        raise CrawlError("Could not parse article body.")
    return clean_html_text(match.group(1), preserve_breaks=True)


def extract_question_urls(html: str) -> list[str]:
    urls = re.findall(
        r'https://top\.zhan\.com/toefl/read/practicereview-\d+-13-0-\d+\.html',
        html,
    )
    deduped = list(dict.fromkeys(urls))
    if not deduped:
        raise CrawlError("Could not find question page URLs.")
    return deduped


def extract_question_prompt(html: str) -> str:
    match = re.search(
        r'<div class="q_tit">[\s\S]*?<div class="left text[^"]*">(.*?)</div>',
        html,
        flags=re.S,
    )
    if not match:
        raise CrawlError("Could not parse question prompt.")
    return clean_html_text(match.group(1), preserve_breaks=True)


def extract_question_options(html: str) -> list[str]:
    options = re.findall(r'<label[^>]*>(.*?)</label>', html, flags=re.S)
    if options:
        return [clean_html_text(option, preserve_breaks=True) for option in options]

    fallback = re.findall(r'<p class="ops [^"]*?">(.*?)</p>', html, flags=re.S)
    cleaned = [clean_html_text(option, preserve_breaks=True) for option in fallback]
    return [option for option in cleaned if option]


def extract_correct_answer(html: str) -> str:
    match = re.search(r'正确答案：<span>(.*?)</span>', html, flags=re.S)
    if not match:
        return ""
    return clean_html_text(match.group(1))


def extract_question(question_url: str, index: int) -> Question:
    html = fetch_text(question_url)
    return Question(
        index=index,
        prompt=extract_question_prompt(html),
        options=extract_question_options(html),
        correct_answer=extract_correct_answer(html),
    )


def export_article(tpo_value: str, article_index: int) -> ArticleExport:
    entries = list_articles(tpo_value)
    try:
        entry = next(item for item in entries if item.article_index == article_index)
    except StopIteration as exc:
        raise CrawlError(f"Article {article_index} was not found under {tpo_value}.") from exc

    review_html = fetch_text(entry.review_url)
    question_urls = extract_question_urls(review_html)
    questions = [
        extract_question(question_url, idx)
        for idx, question_url in enumerate(question_urls, start=1)
    ]

    return ArticleExport(
        tpo_label=entry.tpo_label,
        article_index=entry.article_index,
        article_id=entry.article_id,
        title=extract_article_title(review_html),
        review_url=entry.review_url,
        article_text=extract_article_text(review_html),
        questions=questions,
    )


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


def render_document(exported: ArticleExport) -> str:
    lines = [
        f"# {exported.tpo_label.upper()} Article {exported.article_index}: {exported.title}",
        "",
        f"- Article ID: `{exported.article_id}`",
        f"- Review URL: {exported.review_url}",
        "",
        "## Article",
        "",
        exported.article_text,
        "",
        "## Questions",
        "",
    ]
    for question in exported.questions:
        lines.append(f"### {question.index}. {question.prompt}")
        lines.append("")
        if question.options:
            for option in question.options:
                lines.append(f"- {option}")
        else:
            lines.append("- [No options parsed]")
        lines.append("")
        lines.append(f"Answer: `{question.correct_answer or 'N/A'}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_worksheet(exported: ArticleExport) -> str:
    lines = [
        f"# Worksheet: {exported.tpo_label.upper()} Article {exported.article_index}",
        "",
        f"## {exported.title}",
        "",
        "### Passage",
        "",
        exported.article_text,
        "",
        "### Questions",
        "",
    ]
    for question in exported.questions:
        lines.append(f"{question.index}. {question.prompt}")
        if question.options:
            for option in question.options:
                lines.append(f"   {option}")
        lines.append("   Answer: __________")
        lines.append("")
    lines.append("## Answer Sheet")
    lines.append("")
    for question in exported.questions:
        lines.append(f"- {question.index}: __________")
    return "\n".join(lines).strip() + "\n"


def paragraphize(text: str) -> str:
    parts = [part.strip() for part in text.split("\n\n") if part.strip()]
    return "\n".join(f"<p>{escape(part)}</p>" for part in parts)


def render_print_html(exported: ArticleExport, show_answers: bool) -> str:
    question_blocks: list[str] = []
    for question in exported.questions:
        options_html = "\n".join(
            f'<div class="option">{escape(option)}</div>'
            for option in question.options
        )
        answer_html = (
            f'<div class="correct-answer">Correct answer: {escape(question.correct_answer or "N/A")}</div>'
            if show_answers
            else '<div class="answer-line">Student answer: ______________________________</div>'
        )
        question_blocks.append(
            "\n".join(
                [
                    '<section class="question">',
                    f'<div class="question-number">Question {question.index}</div>',
                    f'<div class="prompt">{escape(question.prompt)}</div>',
                    options_html,
                    answer_html,
                    '</section>',
                ]
            )
        )

    sheet_label = "Document" if show_answers else "Worksheet"
    subtitle = "With answers" if show_answers else "Student print version"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(sheet_label)} - {escape(exported.title)}</title>
  {PRINT_STYLES}
</head>
<body>
  <section class="page cover">
    <div class="kicker">{escape(exported.tpo_label.upper())} • Article {exported.article_index}</div>
    <h1>{escape(exported.title)}</h1>
    <div class="subtitle">{escape(subtitle)}</div>
    <div class="passage-box">
      <div class="passage-text">{paragraphize(exported.article_text)}</div>
    </div>
  </section>

  <section class="page question-page">
    <div class="question-header">
      <div class="panel-title">Questions</div>
      <div class="panel-note">{escape(subtitle)}</div>
    </div>
    <div class="question-grid">
      {"".join(question_blocks)}
    </div>
  </section>
</body>
</html>
"""


def render_answers_markdown(exported: ArticleExport) -> str:
    lines = [
        f"# Answers: {exported.tpo_label.upper()} Article {exported.article_index}",
        "",
        f"## {exported.title}",
        "",
    ]
    for question in exported.questions:
        lines.append(f"- {question.index}. `{question.correct_answer or 'N/A'}`")
    return "\n".join(lines).strip() + "\n"


def render_answers_html(exported: ArticleExport) -> str:
    items = "\n".join(
        f'<div class="answer-item">Question {question.index}: <strong>{escape(question.correct_answer or "N/A")}</strong></div>'
        for question in exported.questions
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Answers - {escape(exported.title)}</title>
  {PRINT_STYLES}
</head>
<body>
  <section class="page answer-sheet">
    <div class="kicker">{escape(exported.tpo_label.upper())} • Article {exported.article_index}</div>
    <h1>{escape(exported.title)}</h1>
    <div class="subtitle">Answer key</div>
    <div class="answer-list">
      {items}
    </div>
  </section>
</body>
</html>
"""


def export_to_directory(exported: ArticleExport, output_root: Path) -> Path:
    target_dir = output_root / exported.tpo_label / f"article-{exported.article_index}"
    target_dir.mkdir(parents=True, exist_ok=True)

    raw_payload = {
        **asdict(exported),
        "questions": [asdict(question) for question in exported.questions],
    }
    (target_dir / "raw.json").write_text(
        json.dumps(raw_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (target_dir / "document.md").write_text(
        render_document(exported),
        encoding="utf-8",
    )
    (target_dir / "worksheet.md").write_text(
        render_worksheet(exported),
        encoding="utf-8",
    )
    (target_dir / "document.html").write_text(
        render_print_html(exported, show_answers=True),
        encoding="utf-8",
    )
    (target_dir / "worksheet.html").write_text(
        render_print_html(exported, show_answers=False),
        encoding="utf-8",
    )
    (target_dir / "answers.md").write_text(
        render_answers_markdown(exported),
        encoding="utf-8",
    )
    (target_dir / "answers.html").write_text(
        render_answers_html(exported),
        encoding="utf-8",
    )
    return target_dir
