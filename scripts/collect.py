#!/usr/bin/env python3
"""AI Daily 采集器 — 从 HN / arXiv / Dev.to 拉取原始数据，存为 JSON。
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
INBOX_DIR = os.path.join(REPO_ROOT, "_inbox")

TZ_BEIJING = timezone(timedelta(hours=8))
TIMEOUT = 15

# 采集数量（比之前多拉，给策展环节更多素材）
HN_TOP_N = 15
ARXIV_N = 8
DEVTO_N = 8

# ============================================================
# 工具函数
# ============================================================

def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Daily-Collector/2.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [WARN] {e}", file=sys.stderr)
        return None


def fetch_xml(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Daily-Collector/2.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return ET.fromstring(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [WARN] {e}", file=sys.stderr)
        return None


# ============================================================
# 数据源
# ============================================================

def fetch_hackernews(n=HN_TOP_N):
    print(f"[HN] 拉取热榜前 {n} 条 ...")
    ids = fetch_json("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not ids:
        return []

    items = []
    for item_id in ids[:n]:
        detail = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
        if detail and "title" in detail:
            items.append({
                "source": "hackernews",
                "id": item_id,
                "title": detail.get("title", "(无标题)"),
                "url": detail.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
                "score": detail.get("score", 0),
                "comments": detail.get("descendants", 0),
                "by": detail.get("by", "unknown"),
                "type": detail.get("type", "story"),
            })
        if len(items) >= n:
            break
    print(f"[HN] 获取到 {len(items)} 条")
    return items


def fetch_arxiv(n=ARXIV_N):
    print(f"[arXiv] 拉取最新 {n} 篇 AI 论文 ...")
    url = (
        "http://export.arxiv.org/api/query?"
        "search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending"
        f"&start=0&max_results={n}"
    )
    root = fetch_xml(url)
    if root is None:
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    papers = []
    for entry in root.findall("atom:entry", ns):
        title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
        summary = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")
        link = entry.find("atom:id", ns)
        link = link.text.strip() if link is not None and link.text else ""
        published = entry.findtext("atom:published", "", ns) or ""

        authors = []
        for author in entry.findall("atom:author", ns):
            name = author.findtext("atom:name", "", ns)
            if name:
                authors.append(name)

        categories = [c.get("term", "") for c in entry.findall("atom:category", ns) if c.get("term")]

        papers.append({
            "source": "arxiv",
            "id": link,
            "title": title,
            "url": link,
            "summary": summary,
            "authors": authors,
            "published": published,
            "categories": categories,
        })
    print(f"[arXiv] 获取到 {len(papers)} 篇")
    return papers


def fetch_devto(n=DEVTO_N):
    print(f"[Dev.to] 拉取 AI 热门 {n} 篇 ...")
    data = fetch_json(f"https://dev.to/api/articles?tag=ai&top=1&per_page={n}")
    if not data:
        data = fetch_json(f"https://dev.to/api/articles?tag=ai&per_page={n}")
    if not data:
        return []

    articles = []
    for a in data[:n]:
        articles.append({
            "source": "devto",
            "id": a.get("id"),
            "title": a.get("title", "(无标题)"),
            "url": a.get("url", ""),
            "description": (a.get("description") or "").strip().replace("\n", " "),
            "tags": a.get("tag_list", []),
            "reactions": a.get("positive_reactions_count", 0),
            "comments": a.get("comments_count", 0),
            "author": (a.get("user") or {}).get("name", "unknown"),
            "published": a.get("published_at", ""),
            "reading_time": a.get("reading_time_minutes", 0),
        })
    print(f"[Dev.to] 获取到 {len(articles)} 篇")
    return articles


# ============================================================
# 主流程
# ============================================================

def main():
    today = datetime.now(TZ_BEIJING)
    date_str = today.strftime("%Y-%m-%d")
    output_file = os.path.join(INBOX_DIR, f"{date_str}.json")

    if os.path.exists(output_file):
        print(f"[SKIP] 今日已采集: {output_file}")
        return

    print(f"[COLLECT] ====== {date_str} 采集开始 ======\n")

    hn = fetch_hackernews()
    print()
    arxiv = fetch_arxiv()
    print()
    devto = fetch_devto()
    print()

    total = len(hn) + len(arxiv) + len(devto)
    if total == 0:
        print("[FAIL] 全部数据源不可用", file=sys.stderr)
        sys.exit(1)

    data = {
        "date": date_str,
        "collected_at": datetime.now(TZ_BEIJING).isoformat(),
        "total_items": total,
        "hackernews": hn,
        "arxiv": arxiv,
        "devto": devto,
    }

    os.makedirs(INBOX_DIR, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] 采集完成 → {output_file}")
    print(f"       HN: {len(hn)} | arXiv: {len(arxiv)} | Dev.to: {len(devto)} | 合计: {total}")


if __name__ == "__main__":
    main()
