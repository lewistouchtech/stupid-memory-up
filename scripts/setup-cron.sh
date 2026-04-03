#!/bin/bash
# Memory-Plus Cron 配置脚本
# 功能：设置定时任务

# 路径配置
MEMORY_PLUS_DIR="/Users/bot-eva/.openclaw/workspace/memory-plus"
SCRIPTS_DIR="$MEMORY_PLUS_DIR/scripts"
PYTHON="/opt/homebrew/bin/python3"

echo "======================================"
echo "Memory-Plus Cron 配置"
echo "======================================"

# 备份现有 crontab
crontab -l > /tmp/crontab.backup.$$ 2>/dev/null || true

# 创建新的 crontab 配置
cat > /tmp/memory_plus_cron.$$ <<EOF
# Memory-Plus 定时任务
# 生成时间：$(date '+%Y-%m-%d %H:%M:%S')

# 健康检查 - 每 5 分钟
*/5 * * * * $PYTHON $SCRIPTS_DIR/memory-health.py >> $MEMORY_PLUS_DIR/logs/cron_health.log 2>&1

# 降级检查 - 每小时
0 * * * * $PYTHON $SCRIPTS_DIR/memory-downgrade.py >> $MEMORY_PLUS_DIR/logs/cron_downgrade.log 2>&1

# 归档检查 - 每天凌晨 3 点
0 3 * * * $PYTHON $SCRIPTS_DIR/memory-archive.py >> $MEMORY_PLUS_DIR/logs/cron_archive.log 2>&1

# 验证检查 - 每 2 小时
0 */2 * * * $PYTHON $SCRIPTS_DIR/memory-validator.py >> $MEMORY_PLUS_DIR/logs/cron_validator.log 2>&1
EOF

# 安装 crontab
crontab /tmp/memory_plus_cron.$$

# 清理临时文件
rm -f /tmp/crontab.backup.$$ /tmp/memory_plus_cron.$$

echo ""
echo "✓ Cron 配置完成"
echo ""
echo "已配置的定时任务:"
echo "  - 健康检查：每 5 分钟"
echo "  - 降级检查：每小时"
echo "  - 归档检查：每天 03:00"
echo "  - 验证检查：每 2 小时"
echo ""
echo "查看任务：crontab -l"
echo "查看日志：tail -f $MEMORY_PLUS_DIR/logs/cron_*.log"
echo "======================================"
