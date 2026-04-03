#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory-Plus 记忆归档脚本
功能：执行 L3 层记忆的压缩归档和向量索引

版本：1.0.0
创建：2026-04-03
优先级：P1

归档策略:
- 90 天以上记忆压缩为 tar.gz
- 生成向量索引 (LanceDB)
- 可选删除源文件
"""

import os
import sys
import json
import sqlite3
import tarfile
import gzip
import shutil
import logging
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
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
        logging.FileHandler(LOG_DIR / "archive.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MemoryArchive")


@dataclass
class ArchiveRecord:
    """归档记录数据结构"""
    id: str
    content: str
    created_at: datetime
    metadata: Dict
    checksum: str
    archive_file: str
    vector_id: Optional[str] = None


class MemoryArchive:
    """记忆归档管理器"""
    
    def __init__(self, config_path: str = str(CONFIG_FILE)):
        """初始化归档管理器"""
        self.config = self._load_config(config_path)
        self.storage_paths = {
            'l3': Path(self.config['storage']['l3']['path']),
        }
        self.stats = {
            'scanned': 0,
            'archived': 0,
            'vector_indexed': 0,
            'deleted': 0,
            'errors': 0,
            'skipped': 0
        }
        
        # 确保目录存在
        (self.storage_paths['l3'] / 'archive').mkdir(parents=True, exist_ok=True)
        (self.storage_paths['l3'] / 'vector').mkdir(parents=True, exist_ok=True)
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败：{e}")
            return {
                'storage': {
                    'l3': {'path': str(BASE_DIR / 'storage/l3'), 'compress_after_days': 90}
                },
                'archive': {
                    'archive_after_days': 90,
                    'validate_before_archive': True,
                    'delete_after_archive': True,
                    'compression_format': 'tar.gz'
                }
            }
    
    def _calculate_checksum(self, content: str) -> str:
        """计算内容校验和"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def _get_l3_records(self) -> List[ArchiveRecord]:
        """获取 L3 层所有记忆记录"""
        records = []
        l3_db = self.storage_paths['l3'] / 'main.sqlite'
        
        if not l3_db.exists():
            logger.info("L3 数据库不存在，跳过")
            return records
        
        try:
            conn = sqlite3.connect(str(l3_db))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, content, created_at, metadata, checksum
                FROM memories
                WHERE layer = 'L3'
                ORDER BY created_at ASC
            """)
            
            for row in cursor.fetchall():
                record = ArchiveRecord(
                    id=row['id'],
                    content=row['content'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    checksum=row['checksum'] if row['checksum'] else self._calculate_checksum(row['content']),
                    archive_file=''
                )
                records.append(record)
            
            conn.close()
        except Exception as e:
            logger.error(f"读取 L3 数据库失败：{e}")
        
        return records
    
    def _should_archive(self, record: ArchiveRecord) -> bool:
        """判断记录是否应该归档"""
        threshold_days = self.config['archive']['archive_after_days']
        age = datetime.now() - record.created_at
        return age.days >= threshold_days
    
    def _validate_record(self, record: ArchiveRecord) -> bool:
        """验证记录完整性"""
        if not self.config['archive'].get('validate_before_archive', True):
            return True
        
        try:
            # 验证校验和
            calculated_checksum = self._calculate_checksum(record.content)
            if calculated_checksum != record.checksum:
                logger.warning(f"校验和不匹配：{record.id[:8]}...")
                return False
            
            # 验证内容非空
            if not record.content or len(record.content.strip()) == 0:
                logger.warning(f"内容为空：{record.id[:8]}...")
                return False
            
            return True
        except Exception as e:
            logger.error(f"验证失败：{record.id[:8]}... {e}")
            return False
    
    def _create_archive_file(self, records: List[ArchiveRecord], batch_num: int) -> str:
        """创建归档文件"""
        archive_dir = self.storage_paths['l3'] / 'archive'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_name = f"archive_batch{batch_num:04d}_{timestamp}.tar.gz"
        archive_path = archive_dir / archive_name
        
        try:
            with tarfile.open(str(archive_path), "w:gz", compresslevel=6) as tar:
                for record in records:
                    # 创建 JSON 文件
                    json_data = {
                        'id': record.id,
                        'content': record.content,
                        'created_at': record.created_at.isoformat(),
                        'metadata': record.metadata,
                        'checksum': record.checksum,
                        'archived_at': datetime.now().isoformat()
                    }
                    
                    json_content = json.dumps(json_data, ensure_ascii=False, indent=2)
                    
                    # 添加到 tar
                    info = tarfile.TarInfo(name=f"{record.id}.json")
                    info.size = len(json_content.encode('utf-8'))
                    info.mtime = datetime.now().timestamp()
                    tar.addfile(info, fileobj=open('/dev/null', 'rb'))  # 占位
            
            # 重新创建包含实际内容的归档
            with tarfile.open(str(archive_path), "w:gz", compresslevel=6) as tar:
                for record in records:
                    json_data = {
                        'id': record.id,
                        'content': record.content,
                        'created_at': record.created_at.isoformat(),
                        'metadata': record.metadata,
                        'checksum': record.checksum,
                        'archived_at': datetime.now().isoformat()
                    }
                    
                    json_content = json.dumps(json_data, ensure_ascii=False, indent=2).encode('utf-8')
                    
                    info = tarfile.TarInfo(name=f"memories/{record.id}.json")
                    info.size = len(json_content)
                    info.mtime = datetime.now().timestamp()
                    
                    from io import BytesIO
                    tar.addfile(info, fileobj=BytesIO(json_content))
            
            logger.info(f"✓ 创建归档文件：{archive_name}")
            return str(archive_path)
            
        except Exception as e:
            logger.error(f"✗ 创建归档文件失败：{e}")
            return ""
    
    def _create_vector_index(self, records: List[ArchiveRecord]) -> bool:
        """创建向量索引（简化版，使用 JSON 索引）"""
        try:
            vector_dir = self.storage_paths['l3'] / 'vector'
            index_file = vector_dir / f"vector_index_{datetime.now().strftime('%Y%m%d')}.json"
            
            # 创建向量索引数据
            index_data = {
                'created_at': datetime.now().isoformat(),
                'record_count': len(records),
                'records': []
            }
            
            for record in records:
                index_data['records'].append({
                    'id': record.id,
                    'checksum': record.checksum,
                    'created_at': record.created_at.isoformat(),
                    'metadata_summary': {
                        k: str(v)[:100] for k, v in record.metadata.items()
                    } if record.metadata else {}
                })
            
            # 写入索引文件
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✓ 创建向量索引：{index_file.name}")
            return True
            
        except Exception as e:
            logger.error(f"✗ 创建向量索引失败：{e}")
            return False
    
    def _delete_source_records(self, record_ids: List[str]) -> bool:
        """删除源记录"""
        if not self.config['archive'].get('delete_after_archive', True):
            logger.info("配置为保留源文件，跳过删除")
            return True
        
        l3_db = self.storage_paths['l3'] / 'main.sqlite'
        
        if not l3_db.exists():
            return True
        
        try:
            conn = sqlite3.connect(str(l3_db))
            cursor = conn.cursor()
            
            for record_id in record_ids:
                cursor.execute("DELETE FROM memories WHERE id = ?", (record_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✓ 删除 {len(record_ids)} 条源记录")
            return True
            
        except Exception as e:
            logger.error(f"✗ 删除源记录失败：{e}")
            return False
    
    def archive_batch(self, batch_size: int = 100) -> Dict:
        """批量归档记录"""
        logger.info("=" * 60)
        logger.info("开始记忆归档任务")
        logger.info("=" * 60)
        
        records = self._get_l3_records()
        self.stats['scanned'] = len(records)
        logger.info(f"L3 层扫描记录数：{len(records)}")
        
        # 筛选需要归档的记录
        to_archive = [r for r in records if self._should_archive(r)]
        logger.info(f"符合归档条件：{len(to_archive)} 条记录")
        
        if not to_archive:
            logger.info("无需要归档的记录")
            return {
                'status': 'success',
                'archived': 0,
                'message': 'No records to archive'
            }
        
        # 验证记录
        if self.config['archive'].get('validate_before_archive', True):
            valid_records = [r for r in to_archive if self._validate_record(r)]
            invalid_count = len(to_archive) - len(valid_records)
            if invalid_count > 0:
                logger.warning(f"验证失败：{invalid_count} 条记录被跳过")
                self.stats['skipped'] = invalid_count
            to_archive = valid_records
        
        # 分批归档
        batch_num = 0
        total_archived = 0
        
        for i in range(0, len(to_archive), batch_size):
            batch = to_archive[i:i + batch_size]
            batch_num += 1
            
            logger.info(f"\n处理批次 {batch_num}: {len(batch)} 条记录")
            
            # 创建归档文件
            archive_path = self._create_archive_file(batch, batch_num)
            if not archive_path:
                self.stats['errors'] += len(batch)
                continue
            
            # 创建向量索引
            if self.config['archive'].get('vector_index', True):
                if self._create_vector_index(batch):
                    self.stats['vector_indexed'] += len(batch)
            
            # 更新记录状态
            for record in batch:
                record.archive_file = archive_path
                self.stats['archived'] += 1
                total_archived += 1
            
            # 删除源记录
            if self.config['archive'].get('delete_after_archive', True):
                record_ids = [r.id for r in batch]
                if self._delete_source_records(record_ids):
                    self.stats['deleted'] += len(record_ids)
        
        logger.info(f"\n归档完成：{total_archived} 条记录")
        return {
            'status': 'success' if self.stats['errors'] == 0 else 'partial',
            'scanned': self.stats['scanned'],
            'archived': self.stats['archived'],
            'vector_indexed': self.stats['vector_indexed'],
            'deleted': self.stats['deleted'],
            'errors': self.stats['errors'],
            'skipped': self.stats['skipped']
        }
    
    def run(self) -> Dict:
        """执行完整归档流程"""
        start_time = datetime.now()
        logger.info(f"\n{'='*60}")
        logger.info(f"Memory-Plus 归档任务启动")
        logger.info(f"启动时间：{start_time.isoformat()}")
        logger.info(f"{'='*60}\n")
        
        result = self.archive_batch()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 输出统计
        logger.info(f"\n{'='*60}")
        logger.info("归档任务完成统计")
        logger.info(f"{'='*60}")
        logger.info(f"扫描记录：{self.stats['scanned']} 条")
        logger.info(f"归档记录：{self.stats['archived']} 条")
        logger.info(f"向量索引：{self.stats['vector_indexed']} 条")
        logger.info(f"删除源文件：{self.stats['deleted']} 条")
        logger.info(f"错误数：{self.stats['errors']}")
        logger.info(f"跳过数：{self.stats['skipped']}")
        logger.info(f"总耗时：{duration:.2f} 秒")
        logger.info(f"{'='*60}\n")
        
        result['duration_seconds'] = duration
        result['timestamp'] = end_time.isoformat()
        
        return result


def main():
    """主函数"""
    try:
        archiver = MemoryArchive()
        result = archiver.run()
        
        # 输出 JSON 结果
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 根据状态返回退出码
        sys.exit(0 if result['status'] == 'success' else 1)
        
    except Exception as e:
        logger.error(f"归档任务异常：{e}")
        print(json.dumps({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
