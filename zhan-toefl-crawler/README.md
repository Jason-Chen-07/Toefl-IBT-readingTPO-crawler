# Zhan TOEFL Reading Crawler

中文：这是一个从小站教育托福阅读页面抓取文章、题目与答案，并导出黑白打印版试卷的工具。  
English: This project crawls TOEFL reading passages, questions, and answers from Xiaozhan Education pages and exports printer-friendly black-and-white worksheets.

## Features

- Search by `TPO` or keyword
- Export worksheet, document, and answer files
- Build a local index with Chinese and English subject labels
- Print-friendly black-and-white HTML output
- Prebuilt index files included in `data/`

## Run

```bash
PYTHONPATH=src python3 -m zhan_toefl_crawler
```

## Menu

- `1` Search TPO or keyword
- `2` Export worksheet
- `q` Quit

## Output

Exported files are written to:

```text
output/<tpo>/article-<n>/
```

Common files:

- `worksheet.html`
- `document.html`
- `answers.html`
- `raw.json`

Prebuilt index files:

- `data/article_index.json`
- `data/article_index.csv`

## Data Source

中文：本项目中的网页数据均通过爬虫从小站教育网站获取。  
English: All website data in this project is crawled from Xiaozhan Education.

## Rebuild Index

See [REBUILD_INDEX.md](/Users/chensfolder/zhan-toefl-crawler/REBUILD_INDEX.md).

## Disclaimer

中文：本项目仅用于学习、研究与个人练习，请勿用于商业用途。若有侵权问题，请联系 `chenjqjason@icloud.com`。  
English: This project is for study, research, and personal practice only. For any infringement concern, please contact `chenjqjason@icloud.com`.
