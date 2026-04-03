"""
OMLX 本地模型连接配置

OMLX 服务运行在 localhost:9999，提供 OpenAI 兼容的 API 接口
"""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class OMLXConfig:
    """OMLX 本地模型配置"""
    
    # 服务地址
    base_url: str = "http://localhost:9999/v1"
    
    # API Key (oMLX 使用固定 key)
    api_key: str = "omlx-local-key"
    
    # 默认模型
    default_model: str = "Qwen3.5-9B-MLX-4bit"
    
    # 超时设置 (秒)
    timeout: int = 120
    
    # 最大重试次数
    max_retries: int = 3
    
    # 重试延迟 (秒)
    retry_delay: float = 1.0
    
    # 温度参数
    temperature: float = 0.7
    
    # 最大 tokens
    max_tokens: int = 4096
    
    # 上下文窗口
    context_window: int = 32768


def get_omlx_config() -> OMLXConfig:
    """获取 OMLX 配置，支持环境变量覆盖"""
    
    config = OMLXConfig()
    
    # 从环境变量读取配置（如果存在）
    if env_url := os.getenv("OMLX_BASE_URL"):
        config.base_url = env_url
    
    if env_api_key := os.getenv("OMLX_API_KEY"):
        config.api_key = env_api_key
    
    if env_model := os.getenv("OMLX_DEFAULT_MODEL"):
        config.default_model = env_model
    
    if env_timeout := os.getenv("OMLX_TIMEOUT"):
        config.timeout = int(env_timeout)
    
    return config


def check_omlx_connection(config: Optional[OMLXConfig] = None) -> bool:
    """
    检查 OMLX 服务连接状态
    
    Returns:
        bool: 连接是否成功
    """
    import requests
    
    if config is None:
        config = get_omlx_config()
    
    try:
        response = requests.get(
            f"{config.base_url.replace('/v1', '')}/v1/models",
            headers={"Authorization": f"Bearer {config.api_key}"},
            timeout=10
        )
        response.raise_for_status()
        models = response.json()
        
        if "data" in models and len(models["data"]) > 0:
            print(f"✅ OMLX 连接成功，可用模型：{len(models['data'])} 个")
            for model in models["data"]:
                print(f"   - {model['id']}")
            return True
        else:
            print("❌ OMLX 服务返回空模型列表")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ OMLX 服务未启动或无法连接")
        print(f"   请检查服务是否运行在 {config.base_url}")
        return False
    except Exception as e:
        print(f"❌ OMLX 连接检查失败：{e}")
        return False


def create_omlx_client(config: Optional[OMLXConfig] = None):
    """
    创建 OpenAI 兼容的客户端
    
    Returns:
        OpenAI 客户端实例
    """
    from openai import OpenAI
    
    if config is None:
        config = get_omlx_config()
    
    client = OpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        timeout=config.timeout
    )
    
    return client


if __name__ == "__main__":
    # 测试连接
    print("=== OMLX 连接测试 ===\n")
    
    config = get_omlx_config()
    print(f"配置:")
    print(f"  Base URL: {config.base_url}")
    print(f"  默认模型：{config.default_model}")
    print(f"  超时：{config.timeout}s\n")
    
    if check_omlx_connection(config):
        print("\n✅ OMLX 服务就绪")
        
        # 测试创建客户端
        client = create_omlx_client(config)
        print(f"✅ 客户端创建成功")
    else:
        print("\n❌ OMLX 服务不可用")
        exit(1)
