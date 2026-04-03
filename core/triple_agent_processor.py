"""
三代理并行处理模块

并行调用三个独立的代理 (Validator, Scorer, Reviewer) 对记忆内容进行验证
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

# 添加项目根目录到路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from configs.omlx_config import get_omlx_config, create_omlx_client, check_omlx_connection
from configs.cloud_models_config import get_cloud_config, create_cloud_client


@dataclass
class AgentResponse:
    """代理响应数据结构"""
    agent_name: str
    model_used: str
    response_data: dict
    latency_ms: float
    success: bool
    error_message: Optional[str] = None


class TripleAgentProcessor:
    """三代理并行处理器"""
    
    def __init__(self, use_local: bool = True):
        """
        初始化三代理处理器
        
        Args:
            use_local: 是否使用本地 OMLX 模型 (否则使用云端)
        """
        self.use_local = use_local
        self.omlx_config = None
        self.cloud_config = None
        self.clients = {}
        
        # 加载 Prompt 模板
        self.prompts = self._load_prompts()
        
        # 初始化配置
        self._init_configs()
    
    def _load_prompts(self) -> Dict[str, str]:
        """加载三个代理的 Prompt 模板"""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        prompts = {}
        
        for name in ["validator", "scorer", "reviewer"]:
            prompt_file = prompts_dir / f"{name}_prompt.txt"
            if prompt_file.exists():
                with open(prompt_file, "r", encoding="utf-8") as f:
                    prompts[name] = f.read()
            else:
                raise FileNotFoundError(f"Prompt 文件不存在：{prompt_file}")
        
        return prompts
    
    def _init_configs(self):
        """初始化模型配置"""
        if self.use_local:
            self.omlx_config = get_omlx_config()
            if not check_omlx_connection(self.omlx_config):
                raise ConnectionError("OMLX 服务不可用")
            self.clients["default"] = create_omlx_client(self.omlx_config)
        else:
            self.cloud_config = get_cloud_config()
            available = get_cloud_config().get_available_cloud_models(self.cloud_config)
            if not available:
                raise ValueError("未配置任何云端模型")
            
            # 为每个可用模型创建客户端
            for model_info in available:
                client, model_name = create_cloud_client(model_info["name"], self.cloud_config)
                self.clients[model_info["name"]] = (client, model_name)
    
    async def _call_agent(
        self,
        agent_name: str,
        prompt_template: str,
        memory_content: str,
        client=None,
        model_name: str = None
    ) -> AgentResponse:
        """
        调用单个代理
        
        Args:
            agent_name: 代理名称
            prompt_template: Prompt 模板
            memory_content: 记忆内容
            client: OpenAI 客户端
            model_name: 模型名称
        
        Returns:
            AgentResponse: 代理响应
        """
        start_time = time.time()
        
        try:
            # 填充 Prompt
            prompt = prompt_template.replace("{memory_content}", memory_content)
            
            # 选择客户端和模型
            if client is None:
                client = self.clients["default"]
                if self.use_local:
                    model_name = self.omlx_config.default_model
                else:
                    # 使用第一个云端模型
                    model_name = list(self.clients.keys())[0]
                    client, model_name = self.clients[model_name]
            
            # 调用 API
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "你必须只输出纯 JSON，不要任何解释、思考或额外文本。直接以 { 开始，以 } 结束。"},
                    {"role": "user", "content": prompt + "\n\n重要：只输出 JSON，不要其他内容。"}
                ],
                temperature=0.1,  # 更低温度减少思考
                max_tokens=1000,  # 增加 token 数量避免截断
                timeout=120  # 增加超时时间
            )
            
            # 解析响应
            content = response.choices[0].message.content.strip()
            
            # 提取 JSON (处理思考过程输出)
            # 尝试多种方式提取 JSON
            json_str = None
            
            # 方法 1: 直接解析整个内容
            if content.startswith('{') and content.endswith('}'): 
                json_str = content
            
            # 方法 2: 从 markdown 代码块提取
            elif '```json' in content:
                start = content.find('```json') + 7
                end = content.find('```', start)
                if end > start:
                    json_str = content[start:end].strip()
            elif '```' in content:
                start = content.find('```') + 3
                end = content.find('```', start)
                if end > start:
                    json_str = content[start:end].strip()
            
            # 方法 3: 查找 JSON 对象边界
            if json_str is None:
                start = content.find('{')
                if start >= 0:
                    # 找到最后一个 }
                    end = content.rfind('}')
                    if end > start:
                        json_str = content[start:end+1]
            
            if json_str is None:
                raise ValueError(f"无法从响应中提取 JSON: {content[:100]}")
            
            response_data = json.loads(json_str)
            
            latency_ms = (time.time() - start_time) * 1000
            
            return AgentResponse(
                agent_name=agent_name,
                model_used=model_name,
                response_data=response_data,
                latency_ms=latency_ms,
                success=True
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return AgentResponse(
                agent_name=agent_name,
                model_used=model_name or "unknown",
                response_data={},
                latency_ms=latency_ms,
                success=False,
                error_message=str(e)
            )
    
    async def process_memory(self, memory_content: str) -> Dict[str, AgentResponse]:
        """
        并行处理记忆内容
        
        Args:
            memory_content: 待处理的记忆内容
        
        Returns:
            Dict[str, AgentResponse]: 三个代理的响应
        """
        # 创建三个代理的调用任务
        tasks = [
            self._call_agent("validator", self.prompts["validator"], memory_content),
            self._call_agent("scorer", self.prompts["scorer"], memory_content),
            self._call_agent("reviewer", self.prompts["reviewer"], memory_content)
        ]
        
        # 并行执行
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 整理结果
        results = {}
        for i, response in enumerate(responses):
            agent_names = ["validator", "scorer", "reviewer"]
            agent_name = agent_names[i]
            
            if isinstance(response, Exception):
                results[agent_name] = AgentResponse(
                    agent_name=agent_name,
                    model_used="unknown",
                    response_data={},
                    latency_ms=0,
                    success=False,
                    error_message=str(response)
                )
            else:
                results[agent_name] = response
        
        return results
    
    def process_memory_sync(self, memory_content: str) -> Dict[str, AgentResponse]:
        """同步版本的处理方法"""
        return asyncio.run(self.process_memory(memory_content))


if __name__ == "__main__":
    # 测试三代理处理
    print("=== 三代理处理测试 ===\n")
    
    test_memory = """
    2026-04-03 18:00 完成 Memory-Plus 三代理验证模块的架构设计。
    决定采用 Qwen3.5-9B-MLX 作为本地验证模型，Kimi 和 GLM 作为云端备选。
    模块包含 Validator、Scorer、Reviewer 三个独立代理，通过投票机制确保准确性。
    """
    
    processor = TripleAgentProcessor(use_local=True)
    
    print(f"处理记忆内容:\n{test_memory}\n")
    print("开始并行调用三个代理...\n")
    
    results = processor.process_memory_sync(test_memory)
    
    for agent_name, response in results.items():
        print(f"\n{agent_name.upper()}:")
        print(f"  模型：{response.model_used}")
        print(f"  耗时：{response.latency_ms:.0f}ms")
        print(f"  状态：{'✅ 成功' if response.success else '❌ 失败'}")
        
        if response.success:
            print(f"  结果：{json.dumps(response.response_data, indent=2, ensure_ascii=False)[:200]}...")
        else:
            print(f"  错误：{response.error_message}")
    
    print("\n=== 测试完成 ===")
