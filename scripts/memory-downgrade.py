#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory-Plus 记忆降级脚本
功能：执行 L1→L2→L3 的记忆降级操作

版本：1.0.0
创建：2026-04-03
优先级：P1

降级策略:
- L1→L2: 记忆创建 ≥7 天
- L2→L3: 记忆创建 ≥30 天
"""

import os
import sys
import json
import sqlite3
import shutil
import logging
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        logging.FileHandler(LOG_DIR / "downgrade.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MemoryDowngrade")


@dataclass
class MemoryRecord:
    """记忆记录数据结构"""
    id: str
    content: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict
    layer: str  # L1, L2, L3
    checksum: str


class MemoryDowngrade:
    """记忆降级管理器"""
    
    def __init__(self, config_path: str = str(CONFIG_FILE)):
        """初始化降级管理器"""
        self.config = self._load_config(config_path)
        self.storage_paths = {
            'l1': Path(self.config['storage']['l1']['path']),
            'l2': Path(self.config['storage']['l2']['path']),
            'l3': Path(self.config['storage']['l3']['path'])
        }
        self.stats = {
            'l1_to_l2': 0,
            'l2_to_l3': 0,
            'errors': 0,
            'skipped': 0
        }
        
        # 确保目录存在
        for path in self.storage_paths.values():
            path.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败：{e}")
            # 返回默认配置
            return {
                'storage': {
                    'l1': {'path': str(BASE_DIR / 'storage/l1'), 'max_age_days': 7},
                    'l2': {'path': str(BASE_DIR / 'storage/l2'), 'max_age_days': 30},
                    'l3': {'path': str(BASE_DIR / 'storage/l3'), 'compress_after_days': 90}
                },
                'downgrade': {
                    'l1_to_l2_days': 7,
                    'l2_to_l3_days': 30,
                    'batch_size': 100,
                    'max_workers': 4
                }
            }
    
    def _calculate_checksum(self, content: str) -> str:
        """计算内容校验和"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def _get_l1_records(self) -> List[MemoryRecord]:
        """获取 L1 层所有记忆记录"""
        records = []
        l1_db = self.storage_paths['l1'] / 'main.sqlite'
        
        if not l1_db.exists():
            logger.info("L1 数据库不存在，跳过")
            return records
        
        try:
            conn = sqlite3.connect(str(l1_db))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 查询所有 L1 记录
            cursor.execute("""
                SELECT id, content, created_at, updated_at, metadata, layer
                FROM memories
                WHERE layer = 'L1'
                ORDER BY created_at ASC
            """)
            
            for row in cursor.fetchall():
                record = MemoryRecord(
                    id=row['id'],
                    content=row['content'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.now(),
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    layer=row['layer'],
                    checksum=self._calculate_checksum(row['content'])
                )
                records.append(record)
            
            conn.close()
        except Exception as e:
            logger.error(f"读取 L1 数据库失败：{e}")
        
        return records
    
    def _get_l2_records(self) -> List[MemoryRecord]:
        """获取 L2 层所有记忆记录"""
        records = []
        l2_db = self.storage_paths['l2'] / 'main.sqlite'
        
        if not l2_db.exists():
            logger.info("L2 数据库不存在，跳过")
            return records
        
        try:
            conn = sqlite3.connect(str(l2_db))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, content, created_at, updated_at, metadata, layer
                FROM memories
                WHERE layer = 'L2'
                ORDER BY created_at ASC
            """)
            
            for row in cursor.fetchall():
                record = MemoryRecord(
                    id=row['id'],
                    content=row['content'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.now(),
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    layer=row['layer'],
                    checksum=self._calculate_checksum(row['content'])
                )
                records.append(record)
            
            conn.close()
        except Exception as e:
            logger.error(f"读取 L2 数据库失败：{e}")
        
        return records
    
    def _should_downgrade_l1_to_l2(self, record: MemoryRecord) -> bool:
        """判断 L1 记录是否应该降级到 L2"""
        threshold_days = self.config['downgrade']['l1_to_l2_days']
        age = datetime.now() - record.created_at
        return age.days >= threshold_days
    
    def _should_downgrade_l2_to_l3(self, record: MemoryRecord) -> bool:
        """判断 L2 记录是否应该降级到 L3"""
        threshold_days = self.config['downgrade']['l2_to_l3_days']
        age = datetime.now() - record.created_at
        return age.days >= threshold_days
    
    def _migrate_record(self, record: MemoryRecord, from_layer: str, to_layer: str) -> bool:
        """迁移单个记录"""
        try:
            # 写入目标层
            target_db = self.storage_paths[to_layer.lower()] / 'main.sqlite'
            
            conn = sqlite3.connect(str(target_db))
            cursor = conn.cursor()
            
            # 创建表（如果不存在）
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
            
            # 插入或替换记录
            cursor.execute("""
                INSERT OR REPLACE INTO memories (id, content, created_at, updated_at, metadata, layer, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                record.id,
                record.content,
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
                json.dumps(record.metadata, ensure_ascii=False),
                to_layer,
                record.checksum
            ))
            
            conn.commit()
            conn.close()
            
            # 从源层删除
            source_db = self.storage_paths[from_layer.lower()] / 'main.sqlite'
            if source_db.exists():
                conn = sqlite3.connect(str(source_db))
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memories WHERE id = ?", (record.id,))
                conn.commit()
                conn.close()
            
            logger.info(f"✓ 迁移成功：{record.id[:8]}... {from_layer} → {to_layer}")
            return True
            
        except Exception as e:
            logger.error(f"✗ 迁移失败：{record.id[:8]}... {e}")
            return False
    
    def downgrade_l1_to_l2(self) -> int:
        """执行 L1→L2 降级"""
        logger.info("=" * 60)
        logger.info("开始 L1→L2 降级检查")
        logger.info("=" * 60)
        
        records = self._get_l1_records()
        logger.info(f"L1 层当前记录数：{len(records)}")
        
        migrated_count = 0
        batch_size = self.config['downgrade']['batch_size']
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            
            with ThreadPoolExecutor(max_workers=self.config['downgrade']['max_workers']) as executor:
                futures = []
                for record in batch:
                    if self._should_downgrade_l1_to_l2(record):
                        futures.append(executor.submit(
                            self._migrate_record, record, 'L1', 'L2'
                        ))
                
                for future in as_completed(futures):
                    if future.result():
                        migrated_count += 1
                        self.stats['l1_to_l2'] += 1
                    else:
                        self.stats['errors'] += 1
        
        logger.info(f"L1→L2 降级完成：迁移 {migrated_count} 条记录")
        return migrated_count
    
    def downgrade_l2_to_l3(self) -> int:
        """执行 L2→L3 降级"""
        logger.info("=" * 60)
        logger.info("开始 L2→L3 降级检查")
        logger.info("=" * 60)
        
        records = self._get_l2_records()
        logger.info(f"L2 层当前记录数：{len(records)}")
        
        migrated_count = 0
        batch_size = self.config['downgrade']['batch_size']
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            
            with ThreadPoolExecutor(max_workers=self.config['downgrade']['max_workers']) as executor:
                futures = []
                for record in batch:
                    if self._should_downgrade_l2_to_l3(record):
                        futures.append(executor.submit(
                            self._migrate_record, record, 'L2', 'L3'
                        ))
                
                for future in as_completed(futures):
                    if future.result():
                        migrated_count += 1
                        self.stats['l2_to_l3'] += 1
                    else:
                        self.stats['errors'] += 1
        
        logger.info(f"L2→L3 降级完成：迁移 {migrated_count} 条记录")
        return migrated_count
    
    def run(self) -> Dict:
        """执行完整降级流程"""
        start_time = datetime.now()
        logger.info(f"\n{'='*60}")
        logger.info(f"Memory-Plus 降级任务启动")
        logger.info(f"启动时间：{start_time.isoformat()}")
        logger.info(f"{'='*60}\n")
        
        # 执行 L1→L2 降级
        l1_count = self.downgrade_l1_to_l2()
        
        # 执行 L2→L3 降级
        l2_count = self.downgrade_l2_to_l3()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 输出统计
        logger.info(f"\n{'='*60}")
        logger.info("降级任务完成统计")
        logger.info(f"{'='*60}")
        logger.info(f"L1→L2 迁移：{self.stats['l1_to_l2']} 条")
        logger.info(f"L2→L3 迁移：{self.stats['l2_to_l3']} 条")
        logger.info(f"错误数：{self.stats['errors']}")
        logger.info(f"跳过数：{self.stats['skipped']}")
        logger.info(f"总耗时：{duration:.2f} 秒")
        logger.info(f"{'='*60}\n")
        
        return {
            'status': 'success' if self.stats['errors'] == 0 else 'partial',
            'l1_to_l2': self.stats['l1_to_l2'],
            'l2_to_l3': self.stats['l2_to_l3'],
            'errors': self.stats['errors'],
            'duration_seconds': duration,
            'timestamp': end_time.isoformat()
        }


def main():
    """主函数"""
    try:
        downgrader = MemoryDowngrade()
        result = downgrader.run()
        
        # 输出 JSON 结果（便于 cron 调用）
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 根据状态返回退出码
        sys.exit(0 if result['status'] == 'success' else 1)
        
    except Exception as e:
        logger.error(f"降级任务异常：{e}")
        print(json.dumps({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
