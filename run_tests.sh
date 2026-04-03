#!/bin/bash
# Memory-Plus 三代理验证模块 - 测试运行脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Memory-Plus 三代理验证模块 - 测试套件"
echo "=========================================="
echo ""

# 激活虚拟环境
if [ -d "venv" ]; then
    echo "🔧 激活虚拟环境..."
    source venv/bin/activate
else
    echo "⚠️  虚拟环境不存在，创建中..."
    python3 -m venv venv
    source venv/bin/activate
    pip install openai requests --quiet
fi

# 检查 OMLX 服务
echo "🔍 检查 OMLX 服务..."
if curl -s http://localhost:9999/v1/models > /dev/null 2>&1; then
    echo "✅ OMLX 服务运行中"
else
    echo "❌ OMLX 服务未运行，请启动 oMLX.app"
    exit 1
fi

echo ""
echo "=========================================="
echo "运行集成测试"
echo "=========================================="
echo ""

# 运行测试
python3 tests/test_integration.py

echo ""
echo "=========================================="
echo "测试完成!"
echo "=========================================="
