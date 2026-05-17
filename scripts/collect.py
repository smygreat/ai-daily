#!/usr/bin/env python3
"""AI Daily 资讯采集 — 从 HN / arXiv / Dev.to 抓取，生成每日 Markdown 摘要。
   零外部依赖，仅使用 Python 标准库。"""

import json
import os
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ============================================================
# 配置
# ============================================================

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR = os.path.join(REPO_ROOT, "posts")

# 北京时间
TZ_BEIJING = timezone(timedelta(hours=8))

# 每个源拉取数量
HN_TOP_N = 10
ARXIV_N = 5
DEVTO_N = 5

# 网络超时（秒）
TIMEOUT = 15

# ============================================================
# 工具函数
# ============================================================

def fetch_json(url):
    """GET 请求并解析 JSON，失败返回 None。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Daily-Collector/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        print(f"  [WARN] 请求失败: {url} — {e}", file=sys.stderr)
        return None


def fetch_xml(url):
    """GET 请求并解析为 ElementTree，失败返回 None。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Daily-Collector/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return ET.fromstring(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ET.ParseError, OSError) as e:
        print(f"  [WARN] 请求失败: {url} — {e}", file=sys.stderr)
        return None


def truncate(text, max_chars=200):
    """截断文本到指定长度，末尾加 ..."""
    text = text.strip().replace("\n", " ")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rsplit(" ", 1)[0] + " ..."


# ============================================================
# 数据源抓取
# ============================================================

def fetch_hackernews(n=HN_TOP_N):
    """拉取 Hacker News 热榜 Top N。"""
    print(f"[HN] 拉取热榜前 {n} 条 ...")

    ids = fetch_json("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not ids:
        return []

    items = []
    for item_id in ids[:n]:
        detail = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
        if detail and "title" in detail:
            items.append(
                {
                    "title": detail.get("title", "(无标题)"),
                    "url": detail.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
                    "score": detail.get("score", 0),
                    "comments": detail.get("descendants", 0),
                    "by": detail.get("by", "unknown"),
                }
            )
        if len(items) >= n:
            break

    print(f"[HN] 获取到 {len(items)} 条")
    return items


def fetch_arxiv(n=ARXIV_N):
    """拉取 arXiv 最新 AI 论文。"""
    print(f"[arXiv] 拉取最新 {n} 篇 AI 论文 ...")

    url = (
        "http://export.arxiv.org/api/query?"
        "search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending"
        f"&start=0&max_results={n}"
    )
    root = fetch_xml(url)
    if root is None:
        return []

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    papers = []
    for entry in root.findall("atom:entry", ns):
        title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
        summary = entry.findtext("atom:summary", "", ns).strip()
        link = entry.find("atom:id", ns)
        link = link.text.strip() if link is not None and link.text else ""

        authors = []
        for author in entry.findall("atom:author", ns):
            name = author.findtext("atom:name", "", ns)
            if name:
                authors.append(name)

        papers.append(
            {
                "title": title,
                "url": link,
                "summary": truncate(summary, 250),
                "authors": ", ".join(authors[:3])
                + (f" et al." if len(authors) > 3 else ""),
            }
        )

    print(f"[arXiv] 获取到 {len(papers)} 篇")
    return papers


def fetch_devto(n=DEVTO_N):
    """拉取 Dev.to AI 标签热门文章。"""
    print(f"[Dev.to] 拉取 AI 热门 {n} 篇 ...")

    data = fetch_json(f"https://dev.to/api/articles?tag=ai&top=1&per_page={n}")
    if not data:
        # 回退：不带 top 参数
        data = fetch_json(f"https://dev.to/api/articles?tag=ai&per_page={n}")

    if not data:
        return []

    articles = []
    for a in data[:n]:
        articles.append(
            {
                "title": a.get("title", "(无标题)"),
                "url": a.get("url", ""),
                "description": truncate(a.get("description", ""), 200),
                "tags": ", ".join(a.get("tag_list", [])[:5]),
                "reactions": a.get("positive_reactions_count", 0),
                "author": a.get("user", {}).get("name", "unknown"),
            }
        )

    print(f"[Dev.to] 获取到 {len(articles)} 篇")
    return articles


# ============================================================
# Markdown 生成
# ============================================================

def build_markdown(date_str, hn_items, arxiv_papers, devto_articles):
    """拼装每日摘要 Markdown。"""
    lines = []
    lines.append(f"# AI Daily - {date_str}")
    lines.append("")
    lines.append("> 自动采集自 Hacker News、arXiv、Dev.to | 每日更新")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Hacker News ----
    if hn_items:
        lines.append("##  Hacker News 热榜")
        lines.append("")
        for i, item in enumerate(hn_items, 1):
            title = item["title"].replace("[", "【").replace("]", "】")
            lines.append(
                f"{i}. **[{title}]({item['url']})**  "
                f"Score: {item['score']} | {item['comments']} comments | by *{item['by']}*"
            )
            lines.append("")
    else:
        lines.append("##  Hacker News 热榜")
        lines.append("")
        lines.append("_(今日无法获取数据)_")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ---- arXiv ----
    if arxiv_papers:
        lines.append("##  arXiv 最新 AI 论文")
        lines.append("")
        for i, p in enumerate(arxiv_papers, 1):
            title = p["title"].replace("[", "【").replace("]", "】")
            lines.append(f"{i}. **[{title}]({p['url']})**")
            lines.append(f"   Authors: {p['authors']}")
            lines.append(f"   > {p['summary']}")
            lines.append("")
    else:
        lines.append("##  arXiv 最新 AI 论文")
        lines.append("")
        lines.append("_(今日无法获取数据)_")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ---- Dev.to ----
    if devto_articles:
        lines.append("##  Dev.to AI 精选")
        lines.append("")
        for i, a in enumerate(devto_articles, 1):
            title = a["title"].replace("[", "【").replace("]", "】")
            lines.append(f"{i}. **[{title}]({a['url']})**")
            lines.append(f"   Tags: {a['tags']} | Reactions: {a['reactions']} | by *{a['author']}*")
            lines.append(f"   > {a['description']}")
            lines.append("")
    else:
        lines.append("##  Dev.to AI 精选")
        lines.append("")
        lines.append("_(今日无法获取数据)_")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ---- 页脚 ----
    gen_time = datetime.now(TZ_BEIJING).strftime("%Y-%m-%d %H:%M")
    lines.append(
        f"自动生成于 {gen_time} (北京时间)  |  "
        f"[GitHub](https://github.com/smygreat/ai-daily)"
    )
    lines.append("")

    return "\n".join(lines)


# ============================================================
# 主流程
# ============================================================

def main():
    today = datetime.now(TZ_BEIJING).strftime("%Y-%m-%d")
    output_file = os.path.join(POSTS_DIR, f"{today}-ai-daily.md")

    # 幂等：如果当日文件已存在则跳过
    if os.path.exists(output_file):
        print(f"[SKIP] 今日文件已存在: {output_file}")
        return

    print(f"[COLLECT] 开始采集 {today} 的资讯 ...")
    print()

    hn_items = fetch_hackernews()
    print()

    arxiv_papers = fetch_arxiv()
    print()

    devto_articles = fetch_devto()
    print()

    if not hn_items and not arxiv_papers and not devto_articles:
        print("[FAIL] 所有数据源均无法获取，放弃生成。", file=sys.stderr)
        sys.exit(1)

    # 确保目录存在
    os.makedirs(POSTS_DIR, exist_ok=True)

    md = build_markdown(today, hn_items, arxiv_papers, devto_articles)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"[DONE] 生成成功: {output_file}")
    print(f"       文件大小: {len(md)} 字符")


if __name__ == "__main__":
    main()
