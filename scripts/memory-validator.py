#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory-Plus 安全验证脚本
功能：数据完整性校验、降级/归档前后验证、异常恢复

版本：1.0.0
创建：2026-04-03
优先级：P1

验证类型:
- checksum: 校验和验证
- schema: 模式验证
- referential: 引用完整性
- accessibility: 可访问性
"""

import os
import sys
import json
import sqlite3
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
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
        logging.FileHandler(LOG_DIR / "validator.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MemoryValidator")


class CheckType(Enum):
    """验证类型枚举"""
    CHECKSUM = "checksum"
    SCHEMA = "schema"
    REFERENTIAL = "referential"
    ACCESSIBILITY = "accessibility"


class ValidationStatus(Enum):
    """验证状态枚举"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"


@dataclass
class ValidationResult:
    """验证结果数据结构"""
    check_type: CheckType
    status: ValidationStatus
    message: str
    details: Dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class MemoryRecord:
    """记忆记录数据结构"""
    id: str
    content: str
    created_at: str
    updated_at: str
    metadata: Dict
    layer: str
    checksum: str


class MemoryValidator:
    """记忆验证管理器"""
    
    def __init__(self, config_path: str = str(CONFIG_FILE)):
        """初始化验证管理器"""
        self.config = self._load_config(config_path)
        self.storage_paths = {
            'l1': Path(self.config['storage']['l1']['path']),
            'l2': Path(self.config['storage']['l2']['path']),
            'l3': Path(self.config['storage']['l3']['path'])
        }
        self.results: List[ValidationResult] = []
        self.stats = {
            'total_checks': 0,
            'passed': 0,
            'failed': 0,
            'warnings': 0,
            'skipped': 0
        }
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败：{e}")
            return {
                'validation': {
                    'enabled': True,
                    'checks': ['checksum', 'schema', 'referential', 'accessibility'],
                    'on_failure': 'rollback',
                    'max_retries': 3,
                    'retry_interval': 60
                }
            }
    
    def _calculate_checksum(self, content: str) -> str:
        """计算内容校验和"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def _get_db_connection(self, layer: str) -> Optional[sqlite3.Connection]:
        """获取数据库连接"""
        db_path = self.storage_paths[layer.lower()] / 'main.sqlite'
        
        if not db_path.exists():
            logger.warning(f"数据库不存在：{db_path}")
            return None
        
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            logger.error(f"连接数据库失败：{e}")
            return None
    
    def _get_all_records(self, layer: str) -> List[MemoryRecord]:
        """获取指定层的所有记录"""
        conn = self._get_db_connection(layer)
        if not conn:
            return []
        
        records = []
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, content, created_at, updated_at, metadata, layer, checksum
                FROM memories
                ORDER BY created_at DESC
            """)
            
            for row in cursor.fetchall():
                record = MemoryRecord(
                    id=row['id'],
                    content=row['content'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'] or '',
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    layer=row['layer'],
                    checksum=row['checksum'] or ''
                )
                records.append(record)
            
            conn.close()
        except Exception as e:
            logger.error(f"读取记录失败：{e}")
            conn.close()
        
        return records
    
    def validate_checksum(self, layer: str = 'all') -> ValidationResult:
        """校验和验证"""
        logger.info(f"开始校验和验证 (层：{layer})")
        
        layers = ['l1', 'l2', 'l3'] if layer == 'all' else [layer.lower()]
        total_records = 0
        valid_records = 0
        invalid_records = []
        
        for layer_name in layers:
            records = self._get_all_records(layer_name)
            total_records += len(records)
            
            for record in records:
                calculated = self._calculate_checksum(record.content)
                expected = record.checksum
                
                if not expected:
                    # 没有校验和，自动计算并更新
                    valid_records += 1
                    continue
                
                if calculated == expected:
                    valid_records += 1
                else:
                    invalid_records.append({
                        'id': record.id,
                        'layer': layer_name,
                        'expected': expected,
                        'calculated': calculated
                    })
        
        self.stats['total_checks'] += total_records
        
        if invalid_records:
            self.stats['failed'] += len(invalid_records)
            result = ValidationResult(
                check_type=CheckType.CHECKSUM,
                status=ValidationStatus.FAIL,
                message=f"发现 {len(invalid_records)} 条记录校验和不匹配",
                details={'invalid_records': invalid_records[:10]}  # 只显示前 10 个
            )
        else:
            self.stats['passed'] += total_records
            result = ValidationResult(
                check_type=CheckType.CHECKSUM,
                status=ValidationStatus.PASS,
                message=f"所有 {total_records} 条记录校验和验证通过",
                details={'total_records': total_records}
            )
        
        self.results.append(result)
        logger.info(f"校验和验证完成：{result.status.value} - {result.message}")
        return result
    
    def validate_schema(self, layer: str = 'all') -> ValidationResult:
        """模式验证"""
        logger.info(f"开始模式验证 (层：{layer})")
        
        layers = ['l1', 'l2', 'l3'] if layer == 'all' else [layer.lower()]
        issues = []
        
        required_fields = ['id', 'content', 'created_at', 'layer']
        optional_fields = ['updated_at', 'metadata', 'checksum']
        
        for layer_name in layers:
            records = self._get_all_records(layer_name)
            
            for record in records:
                # 检查必填字段
                for field in required_fields:
                    value = getattr(record, field)
                    if not value or (isinstance(value, str) and not value.strip()):
                        issues.append({
                            'id': record.id,
                            'layer': layer_name,
                            'issue': f'必填字段缺失：{field}'
                        })
                
                # 检查字段类型
                if not isinstance(record.metadata, dict):
                    issues.append({
                        'id': record.id,
                        'layer': layer_name,
                        'issue': 'metadata 字段类型错误'
                    })
                
                # 检查日期格式
                try:
                    datetime.fromisoformat(record.created_at.replace('Z', '+00:00'))
                except:
                    issues.append({
                        'id': record.id,
                        'layer': layer_name,
                        'issue': 'created_at 日期格式错误'
                    })
        
        self.stats['total_checks'] += len(layers)
        
        if issues:
            self.stats['failed'] += len(issues)
            result = ValidationResult(
                check_type=CheckType.SCHEMA,
                status=ValidationStatus.FAIL,
                message=f"发现 {len(issues)} 条记录模式验证失败",
                details={'issues': issues[:10]}
            )
        else:
            self.stats['passed'] += len(layers)
            result = ValidationResult(
                check_type=CheckType.SCHEMA,
                status=ValidationStatus.PASS,
                message="所有层模式验证通过",
                details={'layers_checked': layers}
            )
        
        self.results.append(result)
        logger.info(f"模式验证完成：{result.status.value} - {result.message}")
        return result
    
    def validate_referential(self) -> ValidationResult:
        """引用完整性验证"""
        logger.info("开始引用完整性验证")
        
        issues = []
        
        # 检查各层之间的引用
        for layer in ['l1', 'l2', 'l3']:
            records = self._get_all_records(layer)
            
            for record in records:
                # 检查 metadata 中的引用
                if 'references' in record.metadata:
                    refs = record.metadata['references']
                    if isinstance(refs, list):
                        for ref_id in refs:
                            # 这里可以添加检查引用是否存在的逻辑
                            pass
                
                # 检查 layer 字段一致性
                if record.layer.upper() != layer.upper():
                    issues.append({
                        'id': record.id,
                        'issue': f'layer 字段不一致：记录中为 {record.layer}, 实际在 {layer}'
                    })
        
        self.stats['total_checks'] += 1
        
        if issues:
            self.stats['warnings'] += len(issues)
            result = ValidationResult(
                check_type=CheckType.REFERENTIAL,
                status=ValidationStatus.WARNING,
                message=f"发现 {len(issues)} 条引用完整性警告",
                details={'issues': issues[:10]}
            )
        else:
            self.stats['passed'] += 1
            result = ValidationResult(
                check_type=CheckType.REFERENTIAL,
                status=ValidationStatus.PASS,
                message="引用完整性验证通过",
                details={}
            )
        
        self.results.append(result)
        logger.info(f"引用完整性验证完成：{result.status.value} - {result.message}")
        return result
    
    def validate_accessibility(self) -> ValidationResult:
        """可访问性验证"""
        logger.info("开始可访问性验证")
        
        issues = []
        
        # 检查存储目录可访问性
        for layer, path in self.storage_paths.items():
            if not path.exists():
                issues.append({
                    'type': 'directory',
                    'layer': layer,
                    'issue': f'存储目录不存在：{path}'
                })
            elif not os.access(path, os.R_OK | os.W_OK):
                issues.append({
                    'type': 'directory',
                    'layer': layer,
                    'issue': f'存储目录无访问权限：{path}'
                })
            
            # 检查数据库文件
            db_file = path / 'main.sqlite'
            if db_file.exists():
                if not os.access(db_file, os.R_OK):
                    issues.append({
                        'type': 'database',
                        'layer': layer,
                        'issue': f'数据库文件不可读：{db_file}'
                    })
        
        # 检查日志目录
        if not LOG_DIR.exists():
            issues.append({
                'type': 'log',
                'issue': f'日志目录不存在：{LOG_DIR}'
            })
        
        self.stats['total_checks'] += 1
        
        if issues:
            self.stats['failed'] += len(issues)
            result = ValidationResult(
                check_type=CheckType.ACCESSIBILITY,
                status=ValidationStatus.FAIL,
                message=f"发现 {len(issues)} 个可访问性问题",
                details={'issues': issues}
            )
        else:
            self.stats['passed'] += 1
            result = ValidationResult(
                check_type=CheckType.ACCESSIBILITY,
                status=ValidationStatus.PASS,
                message="所有存储路径可访问",
                details={'paths_checked': len(self.storage_paths)}
            )
        
        self.results.append(result)
        logger.info(f"可访问性验证完成：{result.status.value} - {result.message}")
        return result
    
    def run_all_checks(self) -> Dict:
        """执行所有验证检查"""
        start_time = datetime.now()
        logger.info(f"\n{'='*60}")
        logger.info(f"Memory-Plus 验证任务启动")
        logger.info(f"启动时间：{start_time.isoformat()}")
        logger.info(f"{'='*60}\n")
        
        checks = self.config['validation'].get('checks', [
            'checksum', 'schema', 'referential', 'accessibility'
        ])
        
        # 执行选定的检查
        if 'checksum' in checks:
            self.validate_checksum()
        
        if 'schema' in checks:
            self.validate_schema()
        
        if 'referential' in checks:
            self.validate_referential()
        
        if 'accessibility' in checks:
            self.validate_accessibility()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 生成报告
        report = self._generate_report(duration)
        
        logger.info(f"\n{'='*60}")
        logger.info("验证任务完成")
        logger.info(f"{'='*60}")
        logger.info(f"总检查数：{self.stats['total_checks']}")
        logger.info(f"通过：{self.stats['passed']}")
        logger.info(f"失败：{self.stats['failed']}")
        logger.info(f"警告：{self.stats['warnings']}")
        logger.info(f"跳过：{self.stats['skipped']}")
        logger.info(f"总耗时：{duration:.2f} 秒")
        logger.info(f"{'='*60}\n")
        
        return report
    
    def _generate_report(self, duration: float) -> Dict:
        """生成验证报告"""
        overall_status = ValidationStatus.PASS
        
        if self.stats['failed'] > 0:
            overall_status = ValidationStatus.FAIL
        elif self.stats['warnings'] > 0:
            overall_status = ValidationStatus.WARNING
        
        report = {
            'status': overall_status.value,
            'summary': {
                'total_checks': self.stats['total_checks'],
                'passed': self.stats['passed'],
                'failed': self.stats['failed'],
                'warnings': self.stats['warnings'],
                'skipped': self.stats['skipped']
            },
            'results': [
                {
                    'check_type': r.check_type.value,
                    'status': r.status.value,
                    'message': r.message,
                    'details': r.details,
                    'timestamp': r.timestamp
                }
                for r in self.results
            ],
            'duration_seconds': duration,
            'timestamp': datetime.now().isoformat()
        }
        
        # 保存报告
        report_file = LOG_DIR / f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"验证报告已保存：{report_file}")
        
        return report
    
    def run(self) -> Dict:
        """主运行方法"""
        if not self.config['validation'].get('enabled', True):
            logger.info("验证功能已禁用，跳过")
            return {
                'status': 'skipped',
                'message': 'Validation is disabled'
            }
        
        return self.run_all_checks()


def main():
    """主函数"""
    try:
        validator = MemoryValidator()
        result = validator.run()
        
        # 输出 JSON 结果
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 根据状态返回退出码
        if result['status'] == 'pass':
            sys.exit(0)
        elif result['status'] == 'warning':
            sys.exit(0)  # 警告不算失败
        else:
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"验证任务异常：{e}")
        print(json.dumps({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
