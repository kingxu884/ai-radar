<p align="center">
  <img src="https://img.shields.io/badge/AI_Radar-前沿情报-black?style=for-the-badge" alt="AI Radar">
  <br>
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.11+-green" alt="Python">
  <img src="https://img.shields.io/badge/LLM-DeepSeek_V4_Pro-purple" alt="LLM">
  <img src="https://img.shields.io/badge/自动推送-每天_9:00-orange" alt="Schedule">
</p>

<h3 align="center">每天早上 9 点，一份 AI 前沿日报准时到达你的邮箱。</h3>

---

## 🎯 什么能帮你做到

- **信息过载** → 每天 7 板块精选日报，5 分钟读完
- **信源分散** → 25+ 中英文信源聚合，不用一个一个刷
- **错过信号** → 趋势分析 + 今日信号，帮你抓住关键动向
- **没人帮你盯着** → 全自动运行，每天 9:00 准时到，零人工

## 📡 数据管道

```
                    ┌──────────────────┐
   25+ RSS 源  ──→  │                  │
   11 个 KOL   ──→  │   DeepSeek V4    │  ──→  📧 邮件日报
   10 个搜索词 ──→  │   (via aiping)   │  ──→  📄 HTML 存档
   经典文章    ──→  │                  │
                    └──────────────────┘
```

| 层 | 技术 | 做什么 |
|----|------|--------|
| 采集 | feedparser + Tavily API | 抓 RSS、实时搜索、去重 |
| 分析 | DeepSeek-V4-Pro | 按 7 板块模板生成结构化日报 |
| 推送 | Gmail SMTP | HTML 邮件，适配桌面/移动端 |
| 运维 | GitHub Actions | 每天 9:00 触发，全自动 |

## 📬 日报内容

每天包含 **7 个板块**：

```
🔥 今日必读      — 5-8 条最值得关注的，含判断和关联分析
📈 趋势分析      — 2-3 个值得关注的趋势信号
🔬 值得深挖      — 论文/报告推荐
📖 深度阅读      — 今日推荐博客/经典文章
🏢 厂商动态      — 国内 AI 公司最新动向
💼 求职机会      — 招聘趋势与岗位信号
⚡ 今日信号      — 一句话关键判断
```

## 🚀 5 分钟部署

### 1. Fork → Clone → 装依赖

```bash
git clone https://github.com/kingxu884/ai-intel-tracker.git
cd ai-intel-tracker
pip install -r requirements.txt
```

### 2. 配置 API Keys

```bash
# ~/.ai-config/.env
AIPING_API_KEY=你的_aiping_key
AIPING_BASE_URL=https://www.aiping.cn/api/v1
TAVILY_API_KEY=你的_tavily_key
GMAIL_USER=你的邮箱@gmail.com
GMAIL_APP_PASSWORD=你的_gmail_app密码
RECIPIENT_EMAIL=接收日报的邮箱
```

### 3. 本地测试

```bash
python fetch_news.py --dry-run    # 预览不发送
python fetch_news.py --no-email   # 生成 HTML 不发邮件
python fetch_news.py              # 完整运行
```

### 4. 自动推送（GitHub Actions）

1. 推送到你的 GitHub 仓库
2. Settings → Actions → Workflow permissions → **Read and write**
3. Settings → Secrets → 添加上面的 6 个环境变量
4. 完成。每天早上 9:00 自动推送。

## 📁 项目结构

```
.
├── config.yml              # 核心配置：信源、话题、搜索词、LLM
├── fetch_news.py           # 主引擎 (~400 行单文件)
├── requirements.txt        # feedparser, openai, tavily, pyyaml
├── setup.sh                # 一键初始化
├── .github/workflows/
│   └── daily.yml           # GitHub Actions 定时触发
├── output/daily/           # 日报 HTML 存档
└── sent_history.json       # 推送历史 (自动去重)
```

## ⚙️ 自定义

只需编辑 `config.yml`：

```yaml
# 你关注什么？
topics:
  - AI Agent 与 Harness 工程
  - AI for Science
  - ...

# 想加 RSS 源？
news_feeds:
  新源名称: https://example.com/rss

# 想搜什么关键词？（Tavily 实时搜索）
tavily_searches:
  - query: "你的搜索关键词"
    topic: "分类标签"

# 换模型？
llm:
  model: Kimi-K2.7-Code    # 改成任何 aiping 支持的模型
```

## 🧠 信源覆盖

| 类型 | 数量 | 来源 |
|------|------|------|
| 国际新闻 | 11 | OpenAI, Anthropic, DeepMind, HuggingFace, MIT TR, VB, TC, The Verge, NVIDIA, Meta, MSR |
| 学术论文 | 4 | arXiv (cs.AI, cs.CL, cs.LG, q-bio) |
| 国内媒体 | 3 | 机器之心, 量子位, 36氪 |
| KOL 博客 | 11 | Lilian Weng, S. Raschka, N. Lambert, J. Clark, Karpathy, Jim Fan 等 |
| 实时搜索 | 10 | Tavily — Agent 工程, AI4S, 国内厂商, 求职, KOL 动态 |
| 经典文献 | 9 | Bitter Lesson, Software 2.0, DeepSeek-V3 等 |

## 📄 License

MIT © 2026 — 基于 [AI Dispatch](https://github.com/Yifannnnnnnnw/ai-dispatch) 架构改造。

---

<p align="center">
  <sub>每天早上 9:00 · 准时见 ☕</sub>
</p>
