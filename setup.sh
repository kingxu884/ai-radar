#!/usr/bin/env bash
# ───────────────────────────────────────────────────
# AI Radar — 一键初始化脚本
# 用法: bash setup.sh
# ───────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔════════════════════════════════════════════╗"
echo "║  🧠 AI Radar — 初始化              ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# ── 1. 检查 Python ───────────────────────────
echo "→ 检查 Python..."
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "❌ 请先安装 Python 3.10+"
    exit 1
fi
echo "   ✅ $($PYTHON --version)"

# ── 2. 安装依赖 ──────────────────────────────
echo ""
echo "→ 安装 Python 依赖..."
$PYTHON -m pip install -r requirements.txt --quiet
echo "   ✅ 依赖安装完成"

# ── 3. 检查集中化 env ────────────────────────
ENV_FILE="$HOME/.ai-config/.env"
echo ""
echo "→ 检查 API Key 配置..."
if [ -f "$ENV_FILE" ]; then
    echo "   ✅ 找到 $ENV_FILE"
else
    echo "   ⚠️  $ENV_FILE 不存在"
    echo ""
    echo "   请创建 $ENV_FILE 并填入以下内容："
    echo ""
    echo "   AIPING_API_KEY=你的_aiping_api_key"
    echo "   AIPING_BASE_URL=https://www.aiping.cn/api/v1"
    echo "   TAVILY_API_KEY=你的_tavily_api_key"
    echo "   GMAIL_USER=你的邮箱@gmail.com"
    echo "   GMAIL_APP_PASSWORD=你的_gmail_app_password"
    echo "   RECIPIENT_EMAIL=接收日报的邮箱"
    echo ""
    echo "   Gmail App Password 获取: https://myaccount.google.com/apppasswords"
fi

# ── 4. 创建输出目录 ──────────────────────────
mkdir -p output/daily output/weekly data
echo "   ✅ 输出目录已创建"

# ── 5. 测试运行（dry run）─────────────────────
echo ""
echo "→ 测试运行 (--dry-run)..."
$PYTHON fetch_news.py --dry-run 2>&1 | head -30
echo ""
echo "   ✅ 测试通过！"

# ── 6. 提示下一步 ─────────────────────────────
echo ""
echo "╔════════════════════════════════════════════╗"
echo "║  ✅ 初始化完成！                           ║"
echo "╠════════════════════════════════════════════╣"
echo "║                                            ║"
echo "║  本地运行:                                 ║"
echo "║    python fetch_news.py                    ║"
echo "║    python fetch_news.py --no-email         ║"
echo "║                                            ║"
echo "║  自动推送 (GitHub Actions):                ║"
echo "║    1. 推送此仓库到 GitHub                  ║"
echo "║    2. 在 Settings → Secrets 中填入:        ║"
echo "║       AIPING_API_KEY                       ║"
echo "║       AIPING_BASE_URL                      ║"
echo "║       TAVILY_API_KEY                       ║"
echo "║       GMAIL_USER                           ║"
echo "║       GMAIL_APP_PASSWORD                   ║"
echo "║       RECIPIENT_EMAIL                      ║"
echo "║    3. Actions 会自动每天运行               ║"
echo "║                                            ║"
echo "╚════════════════════════════════════════════╝"
