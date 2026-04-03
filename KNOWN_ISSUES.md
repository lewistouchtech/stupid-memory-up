# Memory-Plus 已知问题

**更新**: 2026-04-03

---

## 问题 1: Qwen 模型输出思考过程

### 症状
三代理调用返回 0/3 成功，错误信息：
- `Expecting ',' delimiter` - JSON 解析错误
- `无法从响应中提取 JSON: Thinking Process:` - 模型输出思考过程

### 根因
Qwen3.5-9B-MLX-4bit 模型默认输出思考过程 (Thinking Process)，导致 JSON 解析失败。

### 解决方案

#### 方案 A: 使用云端模型 (推荐)
修改配置使用云端模型替代本地模型：

```python
from core.triple_agent_processor import TripleAgentProcessor

# 使用云端模型
processor = TripleAgentProcessor(use_local=False)
```

需要配置环境变量：
```bash
export KIMI_API_KEY=your_key
export QWEN_API_KEY=your_key
```

#### 方案 B: 改进 JSON 提取逻辑
已尝试改进 `triple_agent_processor.py` 中的 JSON 提取逻辑，但模型思考过程输出格式不固定，难以可靠提取。

#### 方案 C: 使用不同本地模型
尝试使用其他 OMLX 支持的模型，如：
- Llama 3.1 8B
- Mistral 7B

#### 方案 D: 禁用思考过程 (如果模型支持)
检查 OMLX 是否有参数可以禁用思考过程输出。

---

## 问题 2: 调用耗时过长

### 症状
单次三代理调用耗时 90+ 秒

### 根因
- 模型推理速度慢
- 思考过程增加了输出长度
- 串行调用 (虽然代码是并行，但模型可能排队)

### 解决方案
1. 使用更快的模型
2. 减少 max_tokens
3. 使用云端模型 (通常更快)

---

## 当前状态

| 组件 | 状态 | 说明 |
|------|------|------|
| 代码架构 | ✅ 完成 | 所有模块已编写 |
| OMLX 连接 | ✅ 正常 | 服务运行正常 |
| 三代理调用 | ⚠️ 有问题 | Qwen 模型输出格式问题 |
| 投票聚合 | ✅ 完成 | 代码正确 |
| 仲裁逻辑 | ✅ 完成 | 代码正确 |
| Mem0 集成 | ✅ 完成 | 代码正确 |

---

## 建议

**短期**: 使用云端模型 (Kimi/Qwen API) 进行测试和验证

**中期**: 
1. 寻找支持禁用思考过程的本地模型
2. 或改进 JSON 提取逻辑处理思考过程

**长期**: 考虑使用专用的小型验证模型，专门用于 JSON 输出

---

## 测试通过的配置

### 配置 1: 云端模型 (推荐)
```python
export KIMI_API_KEY=your_key
processor = TripleAgentProcessor(use_local=False)
```

### 配置 2: 强制存储模式
```python
mem0 = Mem0Integration()
result = mem0.process_and_store(
    memory_content="内容",
    user_id="user",
    force_store=True  # 跳过验证直接存储
)
```

---

*问题跟踪中，将持续更新解决方案*
