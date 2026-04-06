from __future__ import annotations

import json
import re
import ssl
import time
import zipfile
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape as xml_escape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_INDEX_URL = "https://top.zhan.com/toefl/read/alltpo.html"
BASE_TPO_URL = "https://top.zhan.com/toefl/read/alltpo{number}.html"
INDEX_DIRNAME = "index"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)

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
    "艺术": "Art",
    "艺术史": "Art History",
    "植物学": "Botany",
    "气象学": "Meteorology",
    "海洋生物学": "Marine Biology",
    "环境科学": "Environmental Science",
    "生态学": "Ecology",
    "生物学": "Biology",
    "社会学": "Sociology",
    "考古学": "Archaeology",
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
def xml_text(text: str) -> str:
    return xml_escape(text, {'"': "&quot;", "'": "&apos;"})


def docx_paragraph(
    text: str,
    *,
    bold: bool = False,
    size: int | None = None,
    align: str | None = None,
    page_break_before: bool = False,
    spacing_after: int | None = None,
) -> str:
    ppr: list[str] = []
    if align:
        ppr.append(f'<w:jc w:val="{align}"/>')
    if page_break_before:
        ppr.append("<w:pageBreakBefore/>")
    if spacing_after is not None:
        ppr.append(f'<w:spacing w:after="{spacing_after}"/>')

    rpr: list[str] = []
    if bold:
        rpr.append("<w:b/>")
    if size is not None:
        rpr.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')

    ppr_xml = f"<w:pPr>{''.join(ppr)}</w:pPr>" if ppr else ""
    rpr_xml = f"<w:rPr>{''.join(rpr)}</w:rPr>" if rpr else ""
    return f"<w:p>{ppr_xml}<w:r>{rpr_xml}<w:t xml:space=\"preserve\">{xml_text(text)}</w:t></w:r></w:p>"


def docx_page_break() -> str:
    return "<w:p><w:r><w:br w:type=\"page\"/></w:r></w:p>"


def docx_two_column_section() -> str:
    return (
        "<w:p><w:pPr><w:sectPr>"
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="567" w:right="567" w:bottom="567" w:left="567" '
        'w:header="708" w:footer="708" w:gutter="0"/>'
        '<w:cols w:num="2" w:space="425"/>'
        "</w:sectPr></w:pPr></w:p>"
    )


def docx_single_column_section() -> str:
    return (
        "<w:p><w:pPr><w:sectPr>"
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="567" w:right="567" w:bottom="567" w:left="567" '
        'w:header="708" w:footer="708" w:gutter="0"/>'
        '<w:cols w:num="1" w:space="0"/>'
        "</w:sectPr></w:pPr></w:p>"
    )


def build_docx(document_body: str, output_path: Path) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    document_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>"""
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:rPr>
      <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Songti SC"/>
      <w:sz w:val="22"/>
      <w:szCs w:val="22"/>
    </w:rPr>
  </w:style>
</w:styles>"""
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"
 xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
 xmlns:v="urn:schemas-microsoft-com:vml"
 xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:w10="urn:schemas-microsoft-com:office:word"
 xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
 xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"
 xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk"
 xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml"
 xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
 mc:Ignorable="w14 wp14">
  <w:body>
    {document_body}
  </w:body>
</w:document>"""
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/_rels/document.xml.rels", document_rels)
        archive.writestr("word/styles.xml", styles)
        archive.writestr("word/document.xml", document_xml)


def render_docx_document(exported: ArticleExport, show_answers: bool) -> str:
    body: list[str] = []
    body.append(docx_paragraph(f"{exported.tpo_label.upper()} Article {exported.article_index}", bold=True, size=24, align="center", spacing_after=120))
    body.append(docx_paragraph(exported.title, bold=True, size=32, align="center", spacing_after=240))
    for paragraph in [part.strip() for part in exported.article_text.split("\n\n") if part.strip()]:
        body.append(docx_paragraph(paragraph, size=21, spacing_after=120))

    body.append(docx_page_break())
    body.append(docx_two_column_section())
    body.append(docx_paragraph("Questions", bold=True, size=24, spacing_after=120))
    for question in exported.questions:
        body.append(docx_paragraph(f"{question.index}. {question.prompt}", bold=True, size=20, spacing_after=40))
        for option in question.options:
            body.append(docx_paragraph(option, size=18, spacing_after=20))
        if show_answers:
            body.append(docx_paragraph(f"Answer: {question.correct_answer or 'N/A'}", size=18, spacing_after=80))
        else:
            body.append(docx_paragraph("Answer: ____________________", size=18, spacing_after=80))
    body.append(docx_single_column_section())
    return "".join(body)


def render_docx_answers(exported: ArticleExport) -> str:
    body: list[str] = []
    body.append(docx_paragraph(f"{exported.tpo_label.upper()} Article {exported.article_index}", bold=True, size=24, align="center", spacing_after=120))
    body.append(docx_paragraph(f"Answers - {exported.title}", bold=True, size=30, align="center", spacing_after=240))
    for question in exported.questions:
        body.append(docx_paragraph(f"{question.index}. {question.correct_answer or 'N/A'}", size=22, spacing_after=80))
    body.append(docx_single_column_section())
    return "".join(body)


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
    (target_dir / "answers.md").write_text(
        render_answers_markdown(exported),
        encoding="utf-8",
    )
    build_docx(render_docx_document(exported, show_answers=True), target_dir / "document.docx")
    build_docx(render_docx_document(exported, show_answers=False), target_dir / "worksheet.docx")
    build_docx(render_docx_answers(exported), target_dir / "answers.docx")
    return target_dir
