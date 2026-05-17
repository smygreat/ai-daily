# AI Daily - 科技前沿 & AI 进展

每日自动采集 Hacker News、arXiv、Dev.to 的科技与 AI 资讯，生成 Markdown 摘要并通过 Git 发布。

## 内容源

| 源 | 说明 |
|---|---|
| [Hacker News](https://news.ycombinator.com/) | 科技圈最热话题 Top 10 |
| [arXiv](https://arxiv.org/) | 最新 AI/cs.AI 论文 5 篇 |
| [Dev.to](https://dev.to/t/ai) | 开发者社区 AI 精选 5 篇 |

## 目录

```
.
├── README.md
├── posts/                     # 每日摘要 (YYYY-MM-DD-ai-daily.md)
└── scripts/
    ├── collect.py             # 资讯采集脚本
    └── publish.sh             # git add/commit/push
```

## 使用方式

```bash
# 手动采集 + 发布
python3 scripts/collect.py && bash scripts/publish.sh

# 手动添加文章
echo "# 我的文章" > posts/2026-xx-xx-my-post.md
bash scripts/publish.sh
```

## 自动发布

Cron 每日早上 9:00（北京时间）自动执行。
