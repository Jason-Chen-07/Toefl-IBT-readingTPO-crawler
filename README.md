# Zhan TOEFL Reading Crawler

从小站托福阅读入口页抓取指定 `TPO/Official` 的文章、题目，并导出成适合刷题的 worksheet。

## 现在支持

- 从总入口 `https://top.zhan.com/toefl/read/alltpo.html` 找到指定 `tpo33` 的分组页
- 列出该 TPO 下 3 篇文章
- 选择某一篇后抓取
  - 文章标题
  - 文章正文
  - 全部题目
  - 选项
  - 正确答案
- 导出 3 份文件
  - `raw.json`
  - `document.md`
  - `worksheet.md`

## 安装

```bash
cd /Users/chensfolder/zhan-toefl-crawler
python3 -m pip install -e .
```

也可以不安装，直接运行模块：

```bash
PYTHONPATH=src python3 -m zhan_toefl_crawler
```

## 交互式使用

```bash
PYTHONPATH=src python3 -m zhan_toefl_crawler
```

示例流程：

```text
Enter TPO (example: tpo33): tpo33
[1] The First Civilizations
[2] Railroads and Commercial Agriculture In Nineteenth-Century United States
[3] Extinction Episodes of The Past
Select article number: 1
```

导出结果默认在：

```text
output/tpo33/article-1/
```

## 命令行用法

列出某个 TPO 的文章：

```bash
PYTHONPATH=src python3 -m zhan_toefl_crawler list tpo33
```

导出某篇文章：

```bash
PYTHONPATH=src python3 -m zhan_toefl_crawler export tpo33 1
```

指定输出目录：

```bash
PYTHONPATH=src python3 -m zhan_toefl_crawler export tpo33 1 --output ./exports
```

## 导出内容说明

`document.md`

- 包含文章原文
- 包含全部题目、选项、正确答案

`worksheet.md`

- 保留文章原文
- 题目保留空白答题区，不显示正确答案
- 更像练习试卷

`raw.json`

- 方便后续接 Web UI、数据库、批量抓取脚本

## 说明

- 当前实现基于小站页面现有 HTML 结构，若网站改版，解析规则可能需要微调。
- 项目目前优先覆盖阅读题型；已经兼容普通选择题、句子插入题、总结题等常见结构。
