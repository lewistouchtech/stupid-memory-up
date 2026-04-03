#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory-Plus 健康检查脚本
功能：监控系统健康状态、存储使用率、性能指标

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
from typing import Dict, List, Optional
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
        logging.FileHandler(LOG_DIR / "health.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MemoryHealth")


class MemoryHealthChecker:
    """记忆系统健康检查器"""
    
    def __init__(self, config_path: str = str(CONFIG_FILE)):
        """初始化健康检查器"""
        self.config = self._load_config(config_path)
        self.storage_paths = {
            'l1': Path(self.config['storage']['l1']['path']),
            'l2': Path(self.config['storage']['l2']['path']),
            'l3': Path(self.config['storage']['l3']['path'])
        }
        self.metrics = {
            'storage': {},
            'database': {},
            'performance': {},
            'alerts': []
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
                    'l1': {'path': str(BASE_DIR / 'storage/l1'), 'max_size_mb': 500},
                    'l2': {'path': str(BASE_DIR / 'storage/l2'), 'max_size_mb': 2000},
                    'l3': {'path': str(BASE_DIR / 'storage/l3')}
                },
                'monitoring': {
                    'enabled': True,
                    'alerts': [
                        {'type': 'storage_threshold', 'threshold': 0.8}
                    ]
                }
            }
    
    def check_storage_usage(self) -> Dict:
        """检查存储使用率"""
        logger.info("检查存储使用率...")
        
        storage_metrics = {}
        
        for layer, path in self.storage_paths.items():
            if not path.exists():
                storage_metrics[layer] = {
                    'exists': False,
                    'size_mb': 0,
                    'usage_percent': 0
                }
                continue
            
            # 计算目录大小
            total_size = 0
            file_count = 0
            for root, dirs, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total_size += os.path.getsize(fp)
                        file_count += 1
                    except:
                        pass
            
            size_mb = total_size / (1024 * 1024)
            max_size_mb = self.config['storage'][layer].get('max_size_mb', 10000)
            usage_percent = (size_mb / max_size_mb) * 100 if max_size_mb > 0 else 0
            
            storage_metrics[layer] = {
                'exists': True,
                'size_mb': round(size_mb, 2),
                'max_size_mb': max_size_mb,
                'usage_percent': round(usage_percent, 2),
                'file_count': file_count
            }
            
            # 检查是否超过阈值
            threshold = 0.8  # 80%
            if usage_percent > threshold * 100:
                self.metrics['alerts'].append({
                    'type': 'storage_threshold',
                    'layer': layer,
                    'severity': 'warning' if usage_percent < 90 else 'critical',
                    'message': f'{layer} 存储使用率超过阈值：{usage_percent:.1f}%',
                    'timestamp': datetime.now().isoformat()
                })
        
        self.metrics['storage'] = storage_metrics
        logger.info(f"存储检查完成：L1={storage_metrics.get('l1', {}).get('usage_percent', 0):.1f}%, "
                   f"L2={storage_metrics.get('l2', {}).get('usage_percent', 0):.1f}%")
        
        return storage_metrics
    
    def check_database_health(self) -> Dict:
        """检查数据库健康状态"""
        logger.info("检查数据库健康...")
        
        db_metrics = {}
        
        for layer, path in self.storage_paths.items():
            db_file = path / 'main.sqlite'
            
            if not db_file.exists():
                db_metrics[layer] = {
                    'exists': False,
                    'status': 'missing'
                }
                continue
            
            try:
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()
                
                # 检查表结构
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                # 检查记录数
                if 'memories' in tables:
                    cursor.execute("SELECT COUNT(*) FROM memories")
                    record_count = cursor.fetchone()[0]
                else:
                    record_count = 0
                
                # 检查数据库大小
                db_size_mb = db_file.stat().st_size / (1024 * 1024)
                
                # 完整性检查
                cursor.execute("PRAGMA integrity_check")
                integrity = cursor.fetchone()[0]
                
                conn.close()
                
                db_metrics[layer] = {
                    'exists': True,
                    'status': 'healthy' if integrity == 'ok' else 'corrupted',
                    'tables': tables,
                    'record_count': record_count,
                    'size_mb': round(db_size_mb, 2),
                    'integrity': integrity
                }
                
            except Exception as e:
                db_metrics[layer] = {
                    'exists': True,
                    'status': 'error',
                    'error': str(e)
                }
                self.metrics['alerts'].append({
                    'type': 'database_error',
                    'layer': layer,
                    'severity': 'critical',
                    'message': f'{layer} 数据库检查失败：{e}',
                    'timestamp': datetime.now().isoformat()
                })
        
        self.metrics['database'] = db_metrics
        logger.info(f"数据库检查完成")
        
        return db_metrics
    
    def check_recent_activity(self) -> Dict:
        """检查最近活动"""
        logger.info("检查最近活动...")
        
        activity_metrics = {}
        
        for layer, path in self.storage_paths.items():
            db_file = path / 'main.sqlite'
            
            if not db_file.exists():
                continue
            
            try:
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()
                
                # 检查最近 24 小时的活动
                cursor.execute("""
                    SELECT COUNT(*) FROM memories 
                    WHERE datetime(created_at) > datetime('now', '-1 day')
                """)
                recent_24h = cursor.fetchone()[0]
                
                # 检查最近 7 天的活动
                cursor.execute("""
                    SELECT COUNT(*) FROM memories 
                    WHERE datetime(created_at) > datetime('now', '-7 days')
                """)
                recent_7d = cursor.fetchone()[0]
                
                conn.close()
                
                activity_metrics[layer] = {
                    'records_24h': recent_24h,
                    'records_7d': recent_7d
                }
                
            except Exception as e:
                activity_metrics[layer] = {
                    'error': str(e)
                }
        
        self.metrics['performance'] = activity_metrics
        return activity_metrics
    
    def generate_report(self) -> Dict:
        """生成健康报告"""
        overall_status = 'healthy'
        
        # 检查是否有严重告警
        critical_alerts = [a for a in self.metrics['alerts'] if a.get('severity') == 'critical']
        warning_alerts = [a for a in self.metrics['alerts'] if a.get('severity') == 'warning']
        
        if critical_alerts:
            overall_status = 'critical'
        elif warning_alerts:
            overall_status = 'warning'
        
        report = {
            'status': overall_status,
            'timestamp': datetime.now().isoformat(),
            'metrics': self.metrics,
            'summary': {
                'total_alerts': len(self.metrics['alerts']),
                'critical_alerts': len(critical_alerts),
                'warning_alerts': len(warning_alerts)
            }
        }
        
        # 保存报告
        metrics_dir = BASE_DIR / 'metrics'
        metrics_dir.mkdir(exist_ok=True)
        
        report_file = metrics_dir / f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"健康报告已保存：{report_file}")
        
        return report
    
    def run(self) -> Dict:
        """执行完整健康检查"""
        start_time = datetime.now()
        logger.info(f"\n{'='*60}")
        logger.info(f"Memory-Plus 健康检查启动")
        logger.info(f"{'='*60}\n")
        
        # 执行各项检查
        self.check_storage_usage()
        self.check_database_health()
        self.check_recent_activity()
        
        # 生成报告
        report = self.generate_report()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"健康检查完成")
        logger.info(f"状态：{report['status']}")
        logger.info(f"告警数：{report['summary']['total_alerts']}")
        logger.info(f"耗时：{duration:.2f} 秒")
        logger.info(f"{'='*60}\n")
        
        report['duration_seconds'] = duration
        
        return report


def main():
    """主函数"""
    try:
        checker = MemoryHealthChecker()
        result = checker.run()
        
        # 输出 JSON 结果
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 根据状态返回退出码
        if result['status'] == 'healthy':
            sys.exit(0)
        elif result['status'] == 'warning':
            sys.exit(0)  # 警告不算失败
        else:
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"健康检查异常：{e}")
        print(json.dumps({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
