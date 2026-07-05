# 🧠 AI Intel Tracker

**每日 AI 前沿情报日报** — 自动抓取、智能摘要、邮件推送。

聚焦：**Agent/Harness 工程 · AI for Science · 大模型前沿 · 国内厂商动态 · 求职机会**

---

## 架构

```
RSS 源 (25+)  ─┐
KOL 博客 (11)  ─┤
Tavily 搜索 (10)─┤
经典文章        ─┤
                ▼
         DeepSeek-V4-Pro
         (via aiping.cn)
                │
                ▼
         📧 邮件日报 (HTML)
         📄 本地存档 (output/)
```

## 快速开始

```bash
# 1. 安装
bash setup.sh

# 2. 确保 ~/.ai-config/.env 已配置 API Keys
#    (AIPING_API_KEY, TAVILY_API_KEY, GMAIL_USER, GMAIL_APP_PASSWORD)

# 3. 运行
python fetch_news.py              # 完整运行：抓取 → 摘要 → 发邮件
python fetch_news.py --no-email   # 不发邮件，保存 HTML 到本地
python fetch_news.py --dry-run    # 预览模式，输出到终端
```

## 自动推送 (GitHub Actions)

1. 推送仓库到 GitHub
2. Settings → Secrets and variables → Actions → 添加以下 Secrets：
   - `AIPING_API_KEY`
   - `AIPING_BASE_URL`
   - `TAVILY_API_KEY`
   - `GMAIL_USER`
   - `GMAIL_APP_PASSWORD`
   - `RECIPIENT_EMAIL`
3. GitHub Actions 每天 UTC 22:00（北京时间 06:00）自动运行

## 项目结构

```
ai-intel-tracker/
├── config.yml          # 所有配置：信源、关键词、LLM、邮件
├── fetch_news.py       # 核心引擎（单文件）
├── requirements.txt    # Python 依赖
├── setup.sh            # 一键初始化
├── .github/workflows/
│   └── daily.yml       # GitHub Actions 定时任务
├── output/daily/       # 日报 HTML 存档
├── sent_history.json   # 已推送记录（自动去重）
└── README.md
```

## 信源覆盖

| 类别 | 数量 | 来源 |
|------|------|------|
| 国际 AI 新闻 | 11 | OpenAI, Anthropic, DeepMind, HuggingFace, MIT TR, VB, TC, The Verge, NVIDIA, Meta, MSR |
| 论文 | 4 | arXiv cs.AI, cs.CL, cs.LG, q-bio |
| 国内 AI 媒体 | 3 | 机器之心, 量子位, 36氪 |
| KOL 博客 | 11 | Lilian Weng, S. Raschka, N. Lambert, J. Clark, Karpathy, Jim Fan 等 |
| 经典文章 | 9 | The Bitter Lesson, Software 2.0, DeepSeek-V3 等 |
| Tavily 搜索 | 10 | Agent 工程, AI4S, 国内厂商, 求职, KOL 动态 |

## 自定义

只需编辑 `config.yml`：

- 添加/删除 RSS 源：修改 `news_feeds`
- 调整关注方向：修改 `topics`
- 更换 LLM：修改 `llm.provider` 和 `llm.model`（任何 OpenAI 兼容 API）
- 调整推送时间：修改 `email.send_hour_utc`
- 添加追踪关键词：修改 `tavily_searches`

## 致谢

基于 [AI Dispatch](https://github.com/Yifannnnnnnnw/ai-dispatch) 架构，感谢原作者。
