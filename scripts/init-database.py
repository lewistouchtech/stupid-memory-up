#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory-Plus 数据库初始化脚本
功能：创建 L1/L2/L3 各层数据库表结构

版本：1.0.0
创建：2026-04-03
优先级：P1
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict
import yaml

# 配置路径
BASE_DIR = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / "config.yaml"

# 日志配置
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "init.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MemoryInit")


class DatabaseInitializer:
    """数据库初始化器"""
    
    def __init__(self, config_path: str = str(CONFIG_FILE)):
        """初始化数据库"""
        self.config = self._load_config(config_path)
        self.storage_paths = {
            'l1': Path(self.config['storage']['l1']['path']),
            'l2': Path(self.config['storage']['l2']['path']),
            'l3': Path(self.config['storage']['l3']['path'])
        }
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败：{e}")
            return {
                'storage': {
                    'l1': {'path': str(BASE_DIR / 'storage/l1'), 'db_mode': 'WAL'},
                    'l2': {'path': str(BASE_DIR / 'storage/l2'), 'db_mode': 'DELETE'},
                    'l3': {'path': str(BASE_DIR / 'storage/l3')}
                }
            }
    
    def _create_database(self, layer: str) -> bool:
        """创建指定层的数据库"""
        db_path = self.storage_paths[layer] / 'main.sqlite'
        
        # 确保目录存在
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 设置 PRAGMA
            db_mode = self.config['storage'][layer].get('db_mode', 'WAL')
            if db_mode == 'WAL':
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
            
            # 创建 memories 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    metadata TEXT,
                    layer TEXT NOT NULL,
                    checksum TEXT
                )
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_created_at 
                ON memories(created_at DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_layer 
                ON memories(layer)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_checksum 
                ON memories(checksum)
            """)
            
            # 创建 metadata 索引表（用于快速查询）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_index (
                    memory_id TEXT PRIMARY KEY,
                    layer TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    tags TEXT,
                    category TEXT,
                    FOREIGN KEY (memory_id) REFERENCES memories(id)
                )
            """)
            
            # 创建系统配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )
            """)
            
            # 插入初始化配置
            cursor.execute("""
                INSERT OR REPLACE INTO system_config (key, value, updated_at)
                VALUES ('version', '1.0.0', ?)
            """, (datetime.now().isoformat(),))
            
            cursor.execute("""
                INSERT OR REPLACE INTO system_config (key, value, updated_at)
                VALUES ('initialized_at', ?, ?)
            """, (datetime.now().isoformat(), datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✓ {layer.upper()} 数据库初始化成功：{db_path}")
            return True
            
        except Exception as e:
            logger.error(f"✗ {layer.upper()} 数据库初始化失败：{e}")
            return False
    
    def initialize_all(self) -> Dict:
        """初始化所有层的数据库"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Memory-Plus 数据库初始化")
        logger.info(f"{'='*60}\n")
        
        results = {}
        
        for layer in ['l1', 'l2', 'l3']:
            logger.info(f"初始化 {layer.upper()} 层数据库...")
            success = self._create_database(layer)
            results[layer] = 'success' if success else 'failed'
        
        # 输出统计
        success_count = sum(1 for v in results.values() if v == 'success')
        total_count = len(results)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"数据库初始化完成")
        logger.info(f"成功：{success_count}/{total_count}")
        logger.info(f"{'='*60}\n")
        
        return {
            'status': 'success' if success_count == total_count else 'partial',
            'results': results,
            'timestamp': datetime.now().isoformat()
        }


def main():
    """主函数"""
    try:
        initializer = DatabaseInitializer()
        result = initializer.initialize_all()
        
        # 输出 JSON 结果
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 根据状态返回退出码
        sys.exit(0 if result['status'] == 'success' else 1)
        
    except Exception as e:
        logger.error(f"初始化异常：{e}")
        print(json.dumps({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
