# Rebuild Index / 重建索引

## English

This project keeps prebuilt index files in `data/` so most users do not need to crawl the website again.

If you want to rebuild the local index files manually:

```bash
PYTHONPATH=src python3 -m zhan_toefl_crawler index
```

Generated files:

- `data/article_index.json`
- `data/article_index.csv`

These files are crawled from Xiaozhan Education reading pages.

## 中文

本项目会把预生成的索引文件保存在 `data/` 目录中，所以大多数使用者不需要重新爬取网站。

如果你想手动重建本地索引文件，请运行：

```bash
PYTHONPATH=src python3 -m zhan_toefl_crawler index
```

生成文件：

- `data/article_index.json`
- `data/article_index.csv`

这些文件的数据来源于小站教育托福阅读页面。
