#!/usr/bin/env python3
"""
AI Radar — 每日 AI 前沿情报日报

基于 AI Dispatch 架构，改造为：
- 支持 aiping.cn (OpenAI 兼容 API) 做 LLM 摘要
- 集成 Tavily Search 补充 RSS 覆盖不到的信息
- 中英文混合信源，中文日报输出
- 通过邮件推送

用法:
    python fetch_news.py              # 抓取 + 摘要 + 发送
    python fetch_news.py --dry-run    # 只抓取不发送，输出到 stdout
    python fetch_news.py --no-email   # 抓取 + 摘要，保存 HTML 但不发送
"""

import feedparser
import hashlib
import json
import os
import re
import signal
import smtplib
import socket
import sys
import time
import yaml
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ── 全局 socket 超时，防止 RSS 抓取卡死 ──
socket.setdefaulttimeout(15)   # 每个连接最多等 15 秒

# ── 可选依赖 ──────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    ENV_PATH = Path.home() / ".ai-config" / ".env"
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
except ImportError:
    pass  # python-dotenv 未安装时静默跳过

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

# ── 路径 ──────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).parent
HISTORY_PATH = PROJECT_DIR / "sent_history.json"
OUTPUT_DIR = PROJECT_DIR / "output" / "daily"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_MAX = 2000


# ╔══════════════════════════════════════════════════════════════╗
# ║  CONFIG & HISTORY                                            ║
# ╚══════════════════════════════════════════════════════════════╝

def load_config() -> dict:
    path = PROJECT_DIR / "config.yml"
    if not path.exists():
        sys.exit("❌ config.yml not found. 请先创建配置文件。")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_history() -> dict:
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    return {"urls": [], "last_sent_date": ""}


def save_history(history: dict, new_urls: list[str]) -> None:
    urls = set(history.get("urls", []))
    for u in new_urls:
        if u:
            urls.add(u)
    updated = list(urls)
    if len(updated) > HISTORY_MAX:
        updated = updated[-HISTORY_MAX:]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    HISTORY_PATH.write_text(
        json.dumps({"urls": updated, "last_sent_date": today},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ╔══════════════════════════════════════════════════════════════╗
# ║  RSS FETCHING                                                ║
# ╚══════════════════════════════════════════════════════════════╝

def _build_url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _fetch_feeds(feeds: dict, hours: int, per_source: int,
                 arxiv_keywords: list[str], history_urls: set[str]) -> list[dict]:
    """抓取 RSS 源，过滤时间、关键词和历史。"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for source, url in feeds.items():
        print(f"  ⏳ {source}...", end=" ", flush=True)
        try:
            feed = feedparser.parse(
                url,
                request_headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Radar/1.0)"}
            )
            if feed.bozo and not feed.entries:
                print(f"❌ 解析失败")
                continue

            count = 0
            for entry in feed.entries:
                if count >= per_source:
                    break

                # 解析时间
                published = None
                for attr in ("published_parsed", "updated_parsed"):
                    t = getattr(entry, attr, None)
                    if t:
                        published = datetime(*t[:6], tzinfo=timezone.utc)
                        break

                if published and published < cutoff:
                    continue

                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = entry.get("summary", "").strip()

                if not title or not link:
                    continue

                # 去重
                if link in history_urls:
                    continue

                # arxiv 关键词过滤
                if source.lower().startswith("arxiv"):
                    text = (title + " " + summary).lower()
                    if not any(kw in text for kw in arxiv_keywords):
                        continue

                articles.append({
                    "id": _build_url_hash(link),
                    "source": source,
                    "title": title,
                    "url": link,
                    "summary": _strip_html(summary)[:800] if summary else "",
                    "published": published.strftime("%Y-%m-%d %H:%M UTC") if published else "未知",
                })
                count += 1
            print(f"✅ {count} 条")

        except Exception as e:
            print(f"❌ {e}")

    return articles


def _strip_html(text: str) -> str:
    """去除 HTML 标签，保留纯文本。"""
    return re.sub(r"<[^>]+>", " ", text).strip()


# ╔══════════════════════════════════════════════════════════════╗
# ║  TAVILY SEARCH                                               ║
# ╚══════════════════════════════════════════════════════════════╝

def tavily_search(cfg: dict, history_urls: set[str]) -> list[dict]:
    """通过 Tavily 搜索补充 RSS 覆盖不到的动态。"""
    if TavilyClient is None:
        print("  [INFO] tavily-python 未安装，跳过搜索。")
        return []

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        print("  [INFO] TAVILY_API_KEY 未设置，跳过搜索。")
        return []

    searches = cfg.get("tavily_searches", [])
    if not searches:
        return []

    max_results = cfg.get("digest", {}).get("tavily_max_results", 5)
    client = TavilyClient(api_key=api_key)
    results = []

    for item in searches:
        query = item["query"] if isinstance(item, dict) else item
        topic = item.get("topic", "") if isinstance(item, dict) else ""
        try:
            resp = client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                days=1,
            )
            for r in resp.get("results", [])[:max_results]:
                url = r.get("url", "").strip()
                if not url or url in history_urls:
                    continue
                title = r.get("title", "").strip()
                content = r.get("content", "").strip()
                results.append({
                    "id": _build_url_hash(url),
                    "source": f"Tavily · {topic}" if topic else "Tavily",
                    "title": title,
                    "url": url,
                    "summary": content[:800] if content else "",
                    "published": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "score": r.get("score", 0),
                })
            time.sleep(0.5)  # 避免触发频率限制
        except Exception as e:
            print(f"  [WARN] Tavily search '{query[:40]}...': {e}", file=sys.stderr)

    # 按评分排序，去重
    seen = set()
    unique = []
    for a in sorted(results, key=lambda x: x.get("score", 0), reverse=True):
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    return unique


# ╔══════════════════════════════════════════════════════════════╗
# ║  CONTENT COMPILATION                                         ║
# ╚══════════════════════════════════════════════════════════════╝

def fetch_all_content(cfg: dict, history_urls: set[str]) -> dict:
    """抓取所有内容：RSS 新闻 + RSS 博客 + 经典 + Tavily 搜索。"""
    d = cfg.get("digest", {})
    arxiv_kw = cfg.get("arxiv_keywords", [])

    # 1. RSS 新闻
    print("📡 抓取 RSS 新闻...")
    news = _fetch_feeds(
        cfg.get("news_feeds", {}),
        d.get("news_hours", 24),
        d.get("news_per_source", 30),
        arxiv_kw,
        history_urls,
    )
    print(f"   → {len(news)} 条新闻")

    # 2. RSS 博客（回溯 blog_days 天）
    print("📝 抓取 KOL 博客...")
    blog_hours = d.get("blog_days", 90) * 24
    blogs = _fetch_feeds(
        cfg.get("blog_feeds", {}),
        blog_hours,
        d.get("blog_per_source", 15),
        arxiv_kw,  # 复用关键词过滤
        history_urls,
    )
    print(f"   → {len(blogs)} 篇博客")

    # 3. 经典文章（从 config 读取，不限时间）
    classics = [
        {
            "id": _build_url_hash(c.get("url", "")),
            "source": f"{c.get('type', '经典').title()} · {c.get('author', '')}",
            "title": c.get("title", ""),
            "url": c.get("url", ""),
            "summary": c.get("note", ""),
            "published": str(c.get("year", "经典")),
        }
        for c in (cfg.get("classics") or [])
        if c.get("url", "") not in history_urls
    ]

    # 4. Tavily 搜索
    print("🔍 Tavily 搜索...")
    tavily_results = tavily_search(cfg, history_urls)
    print(f"   → {len(tavily_results)} 条搜索结果")

    return {
        "news": news,
        "blogs": blogs + classics,
        "tavily": tavily_results,
    }


# ╔══════════════════════════════════════════════════════════════╗
# ║  LLM SUMMARIZATION (OpenAI-compatible via aiping.cn)         ║
# ╚══════════════════════════════════════════════════════════════╝

def build_prompt(news: list[dict], blogs: list[dict], tavily_results: list[dict],
                 cfg: dict) -> str:
    """构建发给 LLM 的 prompt。"""
    llm_cfg = cfg.get("llm", {})
    topics_str = "、".join(cfg.get("topics", ["AI 前沿"]))
    lang = llm_cfg.get("output_language", "中文")
    today = datetime.now().strftime("%Y年%m月%d日")

    # ── 新闻部分 ──
    news_text = "\n\n---\n\n".join(
        f"[{a['source']}] ({a['published']})\n标题: {a['title']}\n链接: {a['url']}\n摘要: {a['summary']}"
        for a in news
    ) if news else "（今日无新新闻）"

    # ── 博客/经典部分 ──
    blogs_text = "\n\n---\n\n".join(
        f"[{b['source']}] ({b['published']})\n标题: {b['title']}\n链接: {b['url']}\n简介: {b['summary']}"
        for b in blogs
    ) if blogs else "（暂无候选，所有文章均已推送过）"

    # ── Tavily 搜索结果 ──
    tavily_text = "\n\n---\n\n".join(
        f"[{t['source']}] (score: {t.get('score', 'N/A')})\n标题: {t['title']}\n链接: {t['url']}\n摘要: {t['summary']}"
        for t in tavily_results
    ) if tavily_results else "（今日无搜索结果）"

    prompt = f"""你是 AI Radar 的主编，为 AI 领域从业者撰写每日深度情报简报。
读者是熟悉 AI 领域的专业人士（工程师、产品经理、研究员），他们不需要基础概念解释，
需要的是**洞察、判断和可操作的信号**。

用户重点关注：{topics_str}。
所有输出请使用**{lang}**。

【新闻资讯】过去 24 小时，共 {len(news)} 条：

{news_text}

【博客/经典文章候选池】共 {len(blogs)} 篇（含近期博客、经典文章、访谈，均未推送过）：

{blogs_text}

【Tavily 实时搜索】共 {len(tavily_results)} 条补充结果：

{tavily_text}

请完成以下六个部分，严格使用 HTML 格式输出（不要加 markdown 代码块、不要加 ```html）：

**第一部分：🔥 今日必读（5-8 条最值得关注的）**
每条包含：发生了什么（1句）→ 为什么重要（2-3句判断）→ 与其他动态的关联（如有）。
优先选择与用户关注方向（{topics_str}）高度相关的。

**第二部分：📈 趋势分析**
识别 2-3 个值得关注的趋势信号，需引用具体新闻/论文作为证据，给出你的预判。

**第三部分：🔬 值得深挖的论文/报告**
2-3 篇值得精读的（优先 arXiv），说明核心贡献和为什么值得花时间读。

**第四部分：📖 今日推荐深度阅读**
从博客/经典候选池中挑选 1 篇最值得精读的。
给出：为什么今天推荐这篇（结合当下背景）、3 个核心观点（bullet）、适合谁读、大致阅读时间。

**第五部分：🏢 国内厂商动态**
汇总国内 AI 厂商（DeepSeek、智谱、月之暗面、百川、深势科技、面壁智能、字节、阿里、百度、腾讯等）的最新动态，特别关注招聘扩招信号。

**第六部分：💼 求职机会与信号**
从信息源中捕捉 AI 领域的招聘趋势、新增岗位类型、薪资信号、技能需求变化。如果没有直接信息，根据趋势推断可能的机会方向。

**第七部分：⚡ 今日信号**
最关键的一个判断，不超过 80 字。可以是风险预警、机会提示、或一个值得立刻行动的洞察。

HTML 格式要求：
- 每个部分用 <div class="section-title"> 做标题
- 每条新闻用 <div class="item"> 包裹
- 趋势用 <div class="trend">
- 论文推荐用 <div class="deep-read">
- 博客推荐用 <div class="blog-pick">
- 结尾用 <div class="closing"> 放"今日信号"

务必直接输出 HTML，不要包裹在 markdown 代码块中。"""

    return prompt


def summarize_via_aiping(prompt: str, cfg: dict) -> str:
    """通过 aiping.cn (OpenAI 兼容接口) 调用 LLM 生成摘要。"""
    if OpenAI is None:
        sys.exit("❌ openai 库未安装。请运行: pip install openai")

    api_key = os.environ.get("AIPING_API_KEY")
    base_url = os.environ.get("AIPING_BASE_URL", "https://www.aiping.cn/api/v1")

    if not api_key:
        sys.exit("❌ AIPING_API_KEY 未设置。请检查 ~/.ai-config/.env")

    llm_cfg = cfg.get("llm", {})
    model = llm_cfg.get("model", "DeepSeek-V4-Pro")

    client = OpenAI(api_key=api_key, base_url=base_url)

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=llm_cfg.get("max_tokens", 8000),
        temperature=llm_cfg.get("temperature", 0.3),
    )

    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError(f"LLM returned empty response (finish_reason={resp.choices[0].finish_reason})")

    # 清洗：去掉可能的 markdown 代码块包裹
    content = re.sub(r"^```html\s*", "", content.strip())
    content = re.sub(r"\s*```$", "", content)
    return content.strip()


def summarize(content: dict, cfg: dict) -> str:
    """构建 prompt 并调用 LLM 生成摘要。"""
    prompt = build_prompt(
        content["news"], content["blogs"], content["tavily"], cfg
    )
    llm_cfg = cfg.get("llm", {})
    provider = llm_cfg.get("provider", "openai_compatible")
    model = llm_cfg.get("model", "DeepSeek-V4-Pro")

    print(f"🤖 调用 LLM ({provider} / {model})...")
    print(f"   Prompt 长度: {len(prompt)} 字符")

    return summarize_via_aiping(prompt, cfg)


# ╔══════════════════════════════════════════════════════════════╗
# ║  EMAIL DELIVERY                                              ║
# ╚══════════════════════════════════════════════════════════════╝

EMAIL_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
       'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
       background: #f0f0f5; margin: 0; padding: 20px; color: #222; }
.wrapper { max-width: 720px; margin: auto; background: #fff;
           border-radius: 12px; overflow: hidden;
           box-shadow: 0 4px 20px rgba(0,0,0,.08); }
.header { background: linear-gradient(135deg, #0f0f1a 0%, #1a1a3e 100%);
          color: #fff; padding: 32px 40px; }
.header h1 { margin: 0; font-size: 22px; letter-spacing: -.3px; font-weight: 700; }
.header .subtitle { font-size: 13px; opacity: .65; margin-top: 6px; }
.body { padding: 28px 40px; }
h2 { color: #0f0f1a; margin-top: 0; font-size: 20px; }
.intro { color: #888; font-size: 13px; margin-bottom: 28px; }
.section-title { font-weight: 700; font-size: 12px; text-transform: uppercase;
                 letter-spacing: .08em; color: #999; margin: 36px 0 16px;
                 padding-bottom: 8px; border-bottom: 2px solid #eee; }
.item { border-left: 3px solid #4f46e5; padding: 14px 20px;
        margin-bottom: 16px; background: #fafafa; border-radius: 0 10px 10px 0; }
.item h3 { margin: 0 0 6px; font-size: 15px; line-height: 1.5; }
.item h3 a { color: #1a1a2e; text-decoration: none; font-weight: 600; }
.item h3 a:hover { text-decoration: underline; color: #4f46e5; }
.meta { font-size: 11px; color: #aaa; display: block; margin-bottom: 8px; }
.item p { margin: 6px 0 0; font-size: 14px; line-height: 1.75; color: #444; }
.item p.tag { font-size: 12px; color: #7c6fcd; margin-top: 8px; }
.trend { border-left: 3px solid #059669; padding: 14px 20px;
         margin-bottom: 16px; background: #f0fdf4; border-radius: 0 10px 10px 0; }
.trend h3 { margin: 0 0 10px; font-size: 15px; color: #065f46; }
.trend p { margin: 0; font-size: 14px; line-height: 1.75; color: #444; }
.deep-read { border-left: 3px solid #d97706; padding: 14px 20px;
             margin-bottom: 16px; background: #fffbeb; border-radius: 0 10px 10px 0; }
.deep-read h3 { margin: 0 0 10px; font-size: 15px; }
.deep-read h3 a { color: #92400e; text-decoration: none; font-weight: 600; }
.deep-read h3 a:hover { text-decoration: underline; }
.deep-read p { margin: 0; font-size: 14px; line-height: 1.75; color: #444; }
.blog-pick { border-left: 3px solid #db2777; padding: 14px 20px;
             margin-bottom: 16px; background: #fdf2f8; border-radius: 0 10px 10px 0; }
.blog-pick h3 { margin: 0 0 6px; font-size: 15px; }
.blog-pick h3 a { color: #831843; text-decoration: none; font-weight: 600; }
.blog-pick h3 a:hover { text-decoration: underline; }
.blog-why { margin: 10px 0 8px; font-size: 14px; line-height: 1.75; color: #444; }
.blog-pick ul { margin: 8px 0; padding-left: 20px; font-size: 14px;
                line-height: 1.8; color: #444; }
.blog-audience { font-size: 12px; color: #9d174d; margin: 8px 0 0; }
.closing { background: linear-gradient(135deg, #1a1a2e 0%, #2d2d44 100%);
           color: #e0e0ff; border-radius: 10px;
           padding: 18px 24px; margin-top: 32px; font-size: 14px; line-height: 1.7; }
.closing strong { color: #fff; }
.footer { padding: 18px 40px; font-size: 12px; color: #bbb;
          border-top: 1px solid #eee; text-align: center; }
a { color: #4f46e5; }
"""


def build_email_html(html_body: str, content: dict) -> str:
    """构建完整的邮件 HTML。"""
    today = datetime.now().strftime("%Y年%m月%d日")
    news_count = len(content.get("news", []))
    blog_count = len(content.get("blogs", []))
    tavily_count = len(content.get("tavily", []))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>{EMAIL_CSS}</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>🧠 AI Radar</h1>
    <div class="subtitle">{today} · 新闻 {news_count} 条 · 博客 {blog_count} 篇 · 搜索 {tavily_count} 条</div>
  </div>
  <div class="body">{html_body}</div>
  <div class="footer">
    AI Radar · Powered by DeepSeek + Tavily + GitHub Actions<br>
    每日自动生成 · 聚焦 AI 前沿、Agent 工程、AI for Science
  </div>
</div>
</body></html>"""


def send_email(html_body: str, content: dict) -> None:
    """通过 Gmail SMTP 发送邮件。"""
    email_cfg = load_config().get("email", {})

    gmail_user = os.environ.get("GMAIL_USER")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("RECIPIENT_EMAIL", gmail_user)

    if not gmail_user or not gmail_password:
        print("  [WARN] GMAIL_USER 或 GMAIL_APP_PASSWORD 未设置，跳过邮件发送。")
        return

    today = datetime.now().strftime("%m/%d")
    subject = f"🧠 AI Radar · {today}"

    full_html = build_email_html(html_body, content)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = recipient
    msg.attach(MIMEText(full_html, "html", "utf-8"))

    smtp_server = email_cfg.get("smtp_server", "smtp.gmail.com")
    smtp_port = email_cfg.get("smtp_port", 465)

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, recipient, msg.as_string())
        print(f"✅ 邮件已发送至 {recipient}")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}", file=sys.stderr)
        raise


# ╔══════════════════════════════════════════════════════════════╗
# ║  MAIN                                                        ║
# ╚══════════════════════════════════════════════════════════════╝

def extract_urls_from_html(html: str) -> list[str]:
    """从 HTML 中提取所有链接 URL，用于去重记录。"""
    return re.findall(r'href="(https?://[^"]+)"', html)


def main():
    dry_run = "--dry-run" in sys.argv
    no_email = "--no-email" in sys.argv

    print("=" * 60)
    print("🧠 AI Radar — 每日 AI 前沿情报")
    print("=" * 60)

    # 加载配置和历史
    cfg = load_config()
    history = load_history()
    sent_urls = set(history.get("urls", []))
    print(f"📋 已追踪 {len(sent_urls)} 条历史记录")

    # 抓取内容
    content = fetch_all_content(cfg, sent_urls)
    total = len(content["news"]) + len(content["blogs"]) + len(content["tavily"])

    if total == 0:
        print("\n📭 今日无新内容，跳过。")
        return

    print(f"\n📊 合计: {total} 条新内容")

    # LLM 摘要
    summary_html = summarize(content, cfg)

    # 保存日报到本地
    today_str = datetime.now().strftime("%Y-%m-%d")
    output_path = OUTPUT_DIR / f"{today_str}.html"
    full_html = build_email_html(summary_html, content)
    output_path.write_text(full_html, encoding="utf-8")
    print(f"📄 日报已保存: {output_path}")

    if dry_run:
        print("\n" + "=" * 60)
        print("📋 DRY RUN — 日报预览 (前 1500 字符):")
        print("=" * 60)
        print(summary_html[:1500])
        if len(summary_html) > 1500:
            print(f"\n... (共 {len(summary_html)} 字符，已截断)")
        return

    # 发送邮件
    if not no_email:
        print("\n📧 发送邮件...")
        send_email(summary_html, content)
    else:
        print("\n⏭️  跳过邮件发送 (--no-email)")

    # 记录历史
    new_urls = extract_urls_from_html(summary_html)
    # 同时记录所有已抓取的原始 URL
    for a in content["news"] + content["blogs"] + content["tavily"]:
        new_urls.append(a["url"])
    save_history(history, new_urls)
    print(f"💾 历史已更新 (+{len(set(new_urls))} URLs)")

    print("\n✅ 完成!")


if __name__ == "__main__":
    main()
