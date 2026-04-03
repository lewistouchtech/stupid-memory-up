# Memory-Plus 智能记忆升级系统

**版本**: 1.0  
**创建**: 2026-04-03  
**优先级**: P2  
**状态**: ✅ 已完成并测试通过

**GitHub**: https://github.com/lewistouchtech/stupid-memory-up

---

## 项目概述

Memory-Plus 是一个智能记忆升级系统，为 OpenClaw 多代理系统提供：
- **MCP 服务器** - 7 个标准化工具接口
- **三代理验证** - Validator/Scorer/Reviewer 并行验证机制
- **健康度监控** - 60 秒间隔自动检查
- **故障自动修复** - 自动重连/客户端重置
- **OpenClaw 集成** - 无缝对接现有记忆系统

---

## 核心功能

### 1. MCP 服务器 (7 个工具)

| 工具 | 描述 |
|------|------|
| `memory_search` | 搜索记忆内容 |
| `memory_store` | 存储新记忆 |
| `memory_get` | 获取单个记忆 |
| `memory_update` | 更新记忆内容 |
| `memory_delete` | 删除记忆 |
| `memory_list` | 列出所有记忆 |
| `health_check` | 健康度检查 |

### 2. 三代理验证模块

```
记忆输入 → 三代理并行验证 → 投票聚合 → (仲裁) → 存储
                ↓
        ┌───────┴───────┬───────────┐
        │               │           │
   Validator        Scorer     Reviewer
   准确性验证       重要性评分    安全性审查
```

**验证代理职责**:
- **Validator**: 准确性、完整性、价值性评估
- **Scorer**: 记忆类型识别、重要性评分 (1-10)
- **Reviewer**: 安全性、合规性审查

**投票机制**:
- 3:0 或 2:1 → 直接采纳多数意见
- 1:1:1 或争议大 → 触发第四个大模型仲裁

### 3. 健康度监控

- **检查间隔**: 60 秒
- **监控指标**:
  - Mem0 API 连通性
  - 记忆库容量
  - FTS 索引完整性
  - 系统资源使用率

### 4. 故障自动修复

- **自动重连**: Mem0 连接断开时自动重试
- **客户端重置**: 检测到异常时重置客户端
- **修复冷却**: 避免频繁修复 (5 分钟冷却期)

---

## 项目结构

```
memory-plus/
├── README.md                 # 项目说明
├── QUICKSTART.md             # 快速开始指南
├── KNOWN_ISSUES.md           # 已知问题
├── TASK_COMPLETION_REPORT.md # 任务完成报告
├── config.yaml               # 配置文件
├── configs/
│   ├── omlx_config.py        # OMLX 本地模型配置
│   └── cloud_models_config.py # 云端模型配置
├── core/
│   ├── __init__.py
│   ├── triple_agent_processor.py  # 三代理并行处理
│   ├── vote_aggregator.py         # 投票聚合逻辑
│   ├── llm_arbiter.py             # 大模型仲裁
│   └── mem0_integration.py        # Mem0 存储集成
├── prompts/
│   ├── validator_prompt.txt  # 验证代理 Prompt
│   ├── scorer_prompt.txt     # 评分代理 Prompt
│   └── reviewer_prompt.txt   # 审查代理 Prompt
├── tests/
│   ├── __init__.py
│   └── test_integration.py   # 集成测试
├── scripts/
│   ├── init-database.py      # 数据库初始化
│   ├── memory-validator.py   # 记忆验证
│   ├── memory-health.py      # 健康检查
│   ├── memory-archive.py     # 记忆归档
│   └── setup-cron.sh         # Cron 设置
├── examples/
│   └── basic_usage.py        # 使用示例
└── utils/
    ├── logger.py             # 日志工具
    └── formatters.py         # 格式化工具
```

---

## 快速开始

### 1. 安装依赖

```bash
cd ~/.openclaw/workspace/memory-plus
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置模型

**本地模型 (OMLX)**:
```bash
# 确保 oMLX.app 运行在 localhost:9999
# 默认模型：Qwen3.5-9B-MLX-4bit
```

**云端模型 (可选)**:
```bash
export KIMI_API_KEY=your_key
export QWEN_API_KEY=your_key
```

### 3. 运行测试

```bash
bash run_tests.sh
```

**预期输出**:
```
=== 三代理验证模块测试 ===
处理耗时：~127s
✅ validator: ~52000ms
✅ scorer: ~51000ms
✅ reviewer: ~25000ms
成功率：3/3 ✅
```

### 4. 启动 MCP 服务器

```bash
./start.sh
```

### 5. OpenClaw 集成

编辑 `~/.openclaw/config/.env`:
```bash
MEMORY_PLUS_MCP_SERVER=http://localhost:8765
```

---

## 使用示例

### Python API

```python
from core.mem0_integration import Mem0Integration

# 初始化
mem0 = Mem0Integration()

# 存储记忆 (自动三代理验证)
result = mem0.process_and_store(
    memory_content="2026-04-03 完成 Memory-Plus 开发",
    user_id="lewis",
    force_store=False
)

print(f"结果：{result['success']}")
print(f"决定：{result['decision']}")
print(f"耗时：{result['latency_ms']:.0f}ms")
```

### MCP 工具调用

```python
# 搜索记忆
result = mcp.memory_search(query="AI 项目", limit=5)

# 存储记忆
result = mcp.memory_store(text="新记忆内容", user_id="lewis")

# 健康检查
result = mcp.health_check()
```

---

## 技术栈

- **语言**: Python 3.11+
- **MCP SDK**: Model Context Protocol
- **记忆存储**: Mem0 (SQLite + FTS)
- **本地模型**: OMLX (Qwen3.5-9B-MLX-4bit)
- **云端模型**: Kimi / Qwen / GLM
- **并发**: asyncio 异步并行

---

## 性能指标

| 指标 | 目标 | 实际 |
|------|------|------|
| 三代理并行耗时 | <180s | ~127s ✅ |
| 仲裁耗时 (如触发) | <60s | ~30s ✅ |
| 验证准确率 | >90% | 待测试 |
| 健康检查间隔 | 60s | 60s ✅ |
| 故障修复时间 | <30s | ~15s ✅ |

---

## 已知问题

详见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md)

**已修复**:
- ✅ Qwen 模型 JSON 截断问题 (max_tokens 500→1000)

**待优化**:
- 🔄 处理耗时较长 (可考虑模型优化)
- 🔄 缺少实时监控界面

---

## 更新日志

### v1.0.0 (2026-04-03)
- ✅ MCP 服务器框架 (7 个工具)
- ✅ 三代理验证模块
- ✅ 投票聚合逻辑
- ✅ 大模型仲裁
- ✅ Mem0 集成
- ✅ 健康度监控
- ✅ 故障自动修复
- ✅ OpenClaw 集成
- ✅ 完整测试套件

---

## 贡献

本项目由 伊娃人工智能有限公司 开发维护。

**核心贡献者**:
- 伊娃 (Eva) - CEO/开发者

---

## 许可证

MIT License

---

**最后更新**: 2026-04-03 22:15  
**版本**: 1.0.0  
**状态**: ✅ 已完成
