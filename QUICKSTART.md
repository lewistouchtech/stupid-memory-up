# Memory-Plus 三代理验证模块 - 快速开始指南

**版本**: 1.0  
**更新**: 2026-04-03

---

## 前置要求

1. **OMLX 服务运行中**
   ```bash
   # 检查 OMLX 是否运行
   curl http://localhost:9999/v1/models
   ```
   
   如果未运行，请启动 oMLX.app

2. **Python 3.10+**
   ```bash
   python3 --version
   ```

3. **虚拟环境** (已包含在项目中)
   ```bash
   cd ~/.openclaw/workspace/memory-plus
   source venv/bin/activate
   ```

---

## 快速测试

### 方法 1: 运行测试脚本

```bash
cd ~/.openclaw/workspace/memory-plus
bash run_tests.sh
```

### 方法 2: 运行示例

```bash
cd ~/.openclaw/workspace/memory-plus
source venv/bin/activate
python3 examples/basic_usage.py
```

### 方法 3: Python 交互式

```python
import sys
sys.path.insert(0, '/Users/bot-eva/.openclaw/workspace/memory-plus')

from core.mem0_integration import Mem0Integration

# 初始化
mem0 = Mem0Integration()

# 存储记忆
result = mem0.process_and_store(
    memory_content="测试记忆：2026-04-03 完成 Memory-Plus 开发",
    user_id="lewis"
)

print(result)
```

---

## 核心 API

### 1. 基础存储

```python
from memory_plus.core import Mem0Integration

mem0 = Mem0Integration()

# 自动验证后存储
result = mem0.process_and_store(
    memory_content="记忆内容",
    user_id="user123",
    force_store=False  # False=启用验证，True=强制存储
)

if result['success']:
    print(f"记忆已存储，ID: {result['memory_id']}")
else:
    print(f"存储失败：{result['decision']}")
```

### 2. 搜索记忆

```python
# 搜索记忆
memories = mem0.search_memories(
    query="关键词",
    user_id="user123",  # 可选，按用户过滤
    limit=10  # 返回数量限制
)

for mem in memories:
    print(f"{mem.id}: {mem.content}")
```

### 3. 获取单条记忆

```python
memory = mem0.get_memory(memory_id=123)
if memory:
    print(memory.content)
```

---

## 高级用法

### 1. 单独使用三代理

```python
from memory_plus.core import TripleAgentProcessor

processor = TripleAgentProcessor(use_local=True)

responses = processor.process_memory_sync("记忆内容")

for agent_name, response in responses.items():
    print(f"{agent_name}: {response.response_data}")
```

### 2. 单独使用投票聚合

```python
from memory_plus.core import VoteAggregator

aggregator = VoteAggregator()
result = aggregator.aggregate(responses)

print(f"投票结果：{result.vote_result}")
print(f"最终决定：{result.final_decision}")
print(f"需要仲裁：{result.needs_arbitration}")
```

### 3. 单独使用仲裁

```python
from memory_plus.core import LLMArbiter

arbiter = LLMArbiter(use_local=True)
result = arbiter.arbitrate(memory_content, aggregated_result)

print(f"仲裁决定：{result.final_decision}")
print(f"理由：{result.reasoning}")
```

---

## 配置选项

### 环境变量

```bash
# OMLX 配置
export OMLX_BASE_URL=http://localhost:9999/v1
export OMLX_DEFAULT_MODEL=Qwen3.5-9B-MLX-4bit
export OMLX_TIMEOUT=120

# 云端模型配置 (可选，作为备份)
export KIMI_API_KEY=your_key
export QWEN_API_KEY=your_key
export GLM_API_KEY=your_key
```

### 代码配置

```python
from memory_plus.configs.omlx_config import OMLXConfig

config = OMLXConfig(
    base_url="http://localhost:9999/v1",
    default_model="Qwen3.5-9B-MLX-4bit",
    timeout=120,
    temperature=0.7,
    max_tokens=4096
)
```

---

## 输出格式

### process_and_store 返回值

```python
{
    "success": True,  # 是否成功
    "memory_id": 123,  # 记忆 ID
    "decision": "STORE",  # 最终决定
    "validation": {  # 验证结果
        "vote_result": "unanimous_pass",
        "vote_counts": {"STORE": 3},
        "confidence": 0.85,
        "needs_arbitration": False
    },
    "arbitration": None,  # 仲裁结果 (如触发)
    "latency_ms": 2500,  # 总耗时
    "error": None  # 错误信息
}
```

---

## 故障排查

### 问题 1: OMLX 连接失败

```bash
# 检查 OMLX 是否运行
ps aux | grep omlx

# 查看 OMLX 日志
tail -f ~/.omlx/logs/server.log
```

### 问题 2: 模块导入错误

```bash
# 确保激活虚拟环境
cd ~/.openclaw/workspace/memory-plus
source venv/bin/activate

# 检查依赖
pip list | grep openai
```

### 问题 3: 数据库错误

```bash
# 检查数据库文件
ls -lh ~/.openclaw/memory/main.sqlite

# 测试数据库连接
sqlite3 ~/.openclaw/memory/main.sqlite "SELECT COUNT(*) FROM validated_memories;"
```

---

## 性能优化

### 1. 批量处理

```python
# 批量存储多条记忆
memories = ["记忆 1", "记忆 2", "记忆 3"]
results = []

for mem in memories:
    result = mem0.process_and_store(mem, user_id="user123")
    results.append(result)
```

### 2. 异步处理

```python
import asyncio

async def store_memory(content):
    return mem0.process_and_store(content, user_id="user123")

# 并行处理多个记忆
tasks = [store_memory(m) for m in memories]
results = await asyncio.gather(*tasks)
```

---

## 最佳实践

1. **始终启用验证** (force_store=False)，除非是临时笔记
2. **定期备份数据库** (~/.openclaw/memory/main.sqlite)
3. **监控处理延迟**，超过 10s 需要优化
4. **审查仲裁记录**，了解分歧原因
5. **定期清理低价值记忆**

---

## 下一步

1. ✅ 完成基础功能开发
2. 🔄 添加单元测试
3. 🔄 集成到现有记忆系统
4. 🔄 生产环境验证

---

*如有问题，请查看 TASK_COMPLETION_REPORT.md 或联系开发团队*
