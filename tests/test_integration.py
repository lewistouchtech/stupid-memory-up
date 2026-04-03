#!/usr/bin/env python3
"""
Memory-Plus 三代理验证模块 - 集成测试
"""

import sys
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.triple_agent_processor import TripleAgentProcessor
from core.vote_aggregator import VoteAggregator
from core.llm_arbiter import LLMArbiter
from core.mem0_integration import Mem0Integration


def test_triple_agent():
    """测试三代理并行处理"""
    print("\n" + "="*60)
    print("测试 1: 三代理并行处理")
    print("="*60)
    
    processor = TripleAgentProcessor(use_local=True)
    
    test_memory = """
    2026-04-03 18:00 完成 Memory-Plus 架构设计
    采用三代理验证机制确保记忆质量
    """
    
    print(f"输入记忆：{test_memory[:50]}...")
    print("开始处理...")
    
    start = time.time()
    responses = processor.process_memory_sync(test_memory)
    elapsed = time.time() - start
    
    print(f"\n处理耗时：{elapsed:.2f}s")
    
    success_count = 0
    for agent_name, response in responses.items():
        status = "✅" if response.success else "❌"
        print(f"{status} {agent_name}: {response.latency_ms:.0f}ms")
        if response.success:
            success_count += 1
    
    print(f"\n成功率：{success_count}/3")
    return success_count == 3


def test_vote_aggregation():
    """测试投票聚合"""
    print("\n" + "="*60)
    print("测试 2: 投票聚合逻辑")
    print("="*60)
    
    from core.triple_agent_processor import AgentResponse
    
    # 模拟一致通过
    responses_unanimous = {
        "validator": AgentResponse("validator", "test", {
            "suggested_action": "STORE", "total_score": 35, "confidence": 0.9
        }, 100, True),
        "scorer": AgentResponse("scorer", "test", {
            "priority_level": 5, "total_score": 40, "confidence": 0.85
        }, 100, True),
        "reviewer": AgentResponse("reviewer", "test", {
            "recommended_action": "APPROVE", "risk_level": "LOW", "confidence": 0.95
        }, 100, True)
    }
    
    aggregator = VoteAggregator()
    result = aggregator.aggregate(responses_unanimous)
    
    print(f"场景 1: 一致通过")
    print(f"  投票结果：{result.vote_result.value}")
    print(f"  最终决定：{result.final_decision}")
    print(f"  需要仲裁：{result.needs_arbitration}")
    print(f"  是否存储：{aggregator.should_store(result)}")
    
    # 模拟分歧
    responses_split = {
        "validator": AgentResponse("validator", "test", {
            "suggested_action": "STORE", "total_score": 35, "confidence": 0.6
        }, 100, True),
        "scorer": AgentResponse("scorer", "test", {
            "priority_level": 2, "total_score": 20, "confidence": 0.5
        }, 100, True),
        "reviewer": AgentResponse("reviewer", "test", {
            "recommended_action": "REJECT", "risk_level": "HIGH", "confidence": 0.7
        }, 100, True)
    }
    
    result = aggregator.aggregate(responses_split)
    
    print(f"\n场景 2: 意见分歧")
    print(f"  投票结果：{result.vote_result.value}")
    print(f"  投票分布：{result.vote_counts}")
    print(f"  最终决定：{result.final_decision}")
    print(f"  需要仲裁：{result.needs_arbitration}")
    
    return True


def test_arbitration():
    """测试仲裁功能"""
    print("\n" + "="*60)
    print("测试 3: 大模型仲裁")
    print("="*60)
    
    from core.vote_aggregator import AggregatedResult, VoteResult
    from core.triple_agent_processor import AgentResponse
    
    test_memory = "测试仲裁功能的记忆内容"
    
    mock_aggregated = AggregatedResult(
        vote_result=VoteResult.SPLIT_DECISION,
        vote_counts={"STORE": 1, "REVIEW": 1, "REJECT": 1},
        final_decision="REVIEW",
        confidence=0.5,
        reasoning="测试分歧场景",
        needs_arbitration=True,
        agent_responses={
            "validator": AgentResponse("validator", "test", {"suggested_action": "STORE"}, 100, True),
            "scorer": AgentResponse("scorer", "test", {"priority_level": 3}, 100, True),
            "reviewer": AgentResponse("reviewer", "test", {"recommended_action": "REJECT"}, 100, True)
        },
        avg_total_score=25.0,
        risk_level="MEDIUM"
    )
    
    arbiter = LLMArbiter(use_local=True)
    
    print("调用仲裁模型...")
    start = time.time()
    result = arbiter.arbitrate(test_memory, mock_aggregated)
    elapsed = time.time() - start
    
    print(f"仲裁耗时：{elapsed:.2f}s")
    print(f"最终决定：{result.final_decision}")
    print(f"置信度：{result.confidence:.2f}")
    print(f"状态：{'✅ 成功' if result.success else '❌ 失败'}")
    print(f"理由：{result.reasoning[:100]}...")
    
    return result.success


def test_mem0_integration():
    """测试 Mem0 集成"""
    print("\n" + "="*60)
    print("测试 4: Mem0 存储集成")
    print("="*60)
    
    mem0 = Mem0Integration()
    
    test_memory = f"""
    集成测试记忆 {time.strftime('%Y-%m-%d %H:%M:%S')}
    用于验证完整的三代理验证流程
    项目：Memory-Plus
    测试类型：集成测试
    """
    
    print("处理并存储记忆...")
    start = time.time()
    result = mem0.process_and_store(
        memory_content=test_memory,
        user_id="test_user",
        force_store=False
    )
    elapsed = time.time() - start
    
    print(f"总耗时：{elapsed:.2f}s")
    print(f"成功：{result['success']}")
    print(f"决定：{result['decision']}")
    if result.get('memory_id'):
        print(f"记忆 ID: {result['memory_id']}")
    
    if result.get('validation'):
        print(f"验证:")
        print(f"  投票：{result['validation']['vote_counts']}")
        print(f"  置信度：{result['validation']['confidence']:.2f}")
    
    if result.get('arbitration'):
        print(f"仲裁:")
        print(f"  决定：{result['arbitration']['decision']}")
        print(f"  模型：{result['arbitration']['model_used']}")
    
    # 测试搜索
    print("\n搜索刚存储的记忆...")
    memories = mem0.search_memories(query="Memory-Plus", user_id="test_user", limit=5)
    print(f"找到 {len(memories)} 条记录")
    
    return result['success']


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Memory-Plus 三代理验证模块 - 集成测试")
    print("="*60)
    
    tests = [
        ("三代理并行处理", test_triple_agent),
        ("投票聚合逻辑", test_vote_aggregation),
        ("大模型仲裁", test_arbitration),
        ("Mem0 存储集成", test_mem0_integration)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ {name} 测试失败：{e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 汇总
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status}: {name}")
    
    print(f"\n总计：{passed}/{total} 通过")
    print("="*60)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
