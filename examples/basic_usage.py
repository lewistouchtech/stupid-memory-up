#!/usr/bin/env python3
"""
Memory-Plus 三代理验证模块 - 基础使用示例

展示如何使用三代理验证模块存储记忆
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.mem0_integration import Mem0Integration


def main():
    """主函数"""
    print("=" * 60)
    print("Memory-Plus 三代理验证模块 - 使用示例")
    print("=" * 60)
    print()
    
    # 初始化集成模块
    print("🔧 初始化 Mem0 集成...")
    mem0 = Mem0Integration()
    print("✅ 初始化完成\n")
    
    # 示例 1: 存储一条普通记忆
    print("📝 示例 1: 存储会议记录")
    print("-" * 60)
    
    meeting_memory = """
    2026-04-03 18:00 产品评审会议
    参会人员：张三、李四、王五
    讨论内容:
    1. Memory-Plus 三代理验证模块架构确认
    2. 决定采用 Qwen3.5-9B-MLX 作为本地验证模型
    3. 投票机制：3 代理并行 + 投票聚合 + 大模型仲裁
    下一步行动:
    - 完成核心模块开发 (负责人：伊娃)
    - 编写单元测试 (负责人：伊娃)
    - 集成到现有记忆系统 (负责人：伊娃)
    """
    
    result = mem0.process_and_store(
        memory_content=meeting_memory,
        user_id="lewis",
        force_store=False
    )
    
    print(f"处理结果：{result['success']}")
    print(f"最终决定：{result['decision']}")
    if result.get('memory_id'):
        print(f"记忆 ID: {result['memory_id']}")
    print(f"耗时：{result['latency_ms']:.0f}ms")
    print()
    
    # 示例 2: 存储技术决策
    print("📝 示例 2: 存储技术决策")
    print("-" * 60)
    
    tech_decision = """
    技术决策记录 2026-04-03
    主题：本地模型选择
    决策内容：
    - 选择 OMLX 作为本地模型推理服务
    - 模型：Qwen3.5-9B-MLX-4bit
    - 原因：
      1. 完全本地运行，保护隐私
      2. 性能优秀 (63 tok/s on M4 Pro)
      3. 支持 128K 上下文
      4. OpenAI 兼容 API，集成简单
    备选方案：Ollama (已排除，性能不如 OMLX)
    """
    
    result = mem0.process_and_store(
        memory_content=tech_decision,
        user_id="lewis",
        force_store=False
    )
    
    print(f"处理结果：{result['success']}")
    print(f"最终决定：{result['decision']}")
    if result.get('memory_id'):
        print(f"记忆 ID: {result['memory_id']}")
    if result.get('validation'):
        print(f"投票分布：{result['validation']['vote_counts']}")
    print(f"耗时：{result['latency_ms']:.0f}ms")
    print()
    
    # 示例 3: 强制存储
    print("📝 示例 3: 强制存储 (跳过验证)")
    print("-" * 60)
    
    quick_note = "临时笔记：记得下午 3 点开会"
    
    result = mem0.process_and_store(
        memory_content=quick_note,
        user_id="lewis",
        force_store=True
    )
    
    print(f"处理结果：{result['success']}")
    print(f"记忆 ID: {result['memory_id']}")
    print(f"耗时：{result['latency_ms']:.0f}ms")
    print()
    
    # 示例 4: 搜索记忆
    print("📝 示例 4: 搜索记忆")
    print("-" * 60)
    
    memories = mem0.search_memories(query="Memory-Plus", user_id="lewis", limit=5)
    
    print(f"找到 {len(memories)} 条相关记忆:")
    for mem in memories:
        print(f"  - ID:{mem.id} [{mem.memory_type}] {mem.content[:50]}...")
    print()
    
    print("=" * 60)
    print("示例完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
