"""
多桶上下文管理器

支持多个独立的上下文桶，每个桶可以存储不同类型的上下文信息：
- default: 默认上下文
- backtest: 回测上下文
- data: 数据下载上下文
- analysis: 分析上下文
- custom: 自定义上下文
"""
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from loguru import logger


class ContextBucket:
    """单个上下文桶"""
    
    def __init__(self, name: str = "default", max_history: int = 10):
        """
        初始化上下文桶
        
        Args:
            name: 桶名称
            max_history: 最大历史记录数
        """
        self.name = name
        self.max_history = max_history
        self.data: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.metadata: Dict[str, Any] = {}
    
    def set(self, key: str, value: Any, persistent: bool = True):
        """设置上下文变量"""
        self.data[key] = {
            'value': value,
            'persistent': persistent,
            'updated_at': datetime.now().isoformat()
        }
        self.updated_at = datetime.now()
        self._save_history()
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文变量"""
        if key in self.data:
            return self.data[key]['value']
        return default
    
    def delete(self, key: str):
        """删除上下文变量"""
        if key in self.data:
            del self.data[key]
            self.updated_at = datetime.now()
    
    def clear(self, keep_persistent: bool = False):
        """清空上下文"""
        if keep_persistent:
            self.data = {k: v for k, v in self.data.items() if v.get('persistent', False)}
        else:
            self.data = {}
        self.updated_at = datetime.now()
    
    def _save_history(self):
        """保存历史记录"""
        self.history.append({
            'timestamp': datetime.now().isoformat(),
            'data': dict(self.data)
        })
        # 限制历史记录数量
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
    
    def get_history(self, limit: int = 5) -> List[Dict]:
        """获取历史记录"""
        return self.history[-limit:]
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'name': self.name,
            'data': {k: v['value'] for k, v in self.data.items()},
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata
        }
    
    def __repr__(self):
        return f"ContextBucket(name={self.name}, vars={len(self.data)})"


class ContextManager:
    """多桶上下文管理器"""
    
    def __init__(self, save_path: Optional[str] = None):
        """
        初始化上下文管理器
        
        Args:
            save_path: 持久化保存路径
        """
        self.buckets: Dict[str, ContextBucket] = {
            'default': ContextBucket('default')
        }
        self.current_bucket = 'default'
        self.save_path = Path(save_path) if save_path else None
        self.global_vars: Dict[str, Any] = {}
        
        # 加载已保存的上下文
        if self.save_path and self.save_path.exists():
            self.load()
    
    def create_bucket(self, name: str) -> ContextBucket:
        """创建新的上下文桶"""
        if name not in self.buckets:
            self.buckets[name] = ContextBucket(name)
        return self.buckets[name]
    
    def get_bucket(self, name: str) -> Optional[ContextBucket]:
        """获取指定的上下文桶"""
        return self.buckets.get(name)
    
    def delete_bucket(self, name: str):
        """删除上下文桶"""
        if name in self.buckets and name != 'default':
            del self.buckets[name]
            if self.current_bucket == name:
                self.current_bucket = 'default'
    
    def switch_bucket(self, name: str):
        """切换当前上下文桶"""
        if name not in self.buckets:
            self.create_bucket(name)
        self.current_bucket = name
    
    def current(self) -> ContextBucket:
        """获取当前上下文桶"""
        return self.buckets[self.current_bucket]
    
    def set(self, key: str, value: Any, bucket: Optional[str] = None, persistent: bool = True):
        """设置上下文变量"""
        bucket_name = bucket or self.current_bucket
        if bucket_name not in self.buckets:
            self.create_bucket(bucket_name)
        self.buckets[bucket_name].set(key, value, persistent)
    
    def get(self, key: str, default: Any = None, bucket: Optional[str] = None) -> Any:
        """获取上下文变量"""
        bucket_name = bucket or self.current_bucket
        if bucket_name not in self.buckets:
            return default
        return self.buckets[bucket_name].get(key, default)
    
    def set_global(self, key: str, value: Any):
        """设置全局变量（跨桶共享）"""
        self.global_vars[key] = value
    
    def get_global(self, key: str, default: Any = None) -> Any:
        """获取全局变量"""
        return self.global_vars.get(key, default)
    
    def get_all(self, bucket: Optional[str] = None) -> Dict:
        """获取指定桶的所有上下文"""
        bucket_name = bucket or self.current_bucket
        if bucket_name not in self.buckets:
            return {}
        return self.buckets[bucket_name].to_dict()
    
    def get_all_buckets(self) -> Dict[str, Dict]:
        """获取所有桶的上下文"""
        return {name: bucket.to_dict() for name, bucket in self.buckets.items()}
    
    def clear(self, bucket: Optional[str] = None, keep_persistent: bool = False):
        """清空上下文"""
        if bucket:
            if bucket in self.buckets:
                self.buckets[bucket].clear(keep_persistent)
        else:
            for bucket_obj in self.buckets.values():
                bucket_obj.clear(keep_persistent)
    
    def save(self):
        """持久化保存上下文"""
        if not self.save_path:
            return
        
        data = {
            'buckets': {name: bucket.to_dict() for name, bucket in self.buckets.items()},
            'global_vars': self.global_vars,
            'current_bucket': self.current_bucket,
            'saved_at': datetime.now().isoformat()
        }
        
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"上下文已保存至：{self.save_path}")
    
    def load(self):
        """从持久化存储加载上下文"""
        if not self.save_path or not self.save_path.exists():
            return
        
        try:
            with open(self.save_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 恢复桶
            self.buckets = {}
            for name, bucket_data in data.get('buckets', {}).items():
                bucket = ContextBucket(name)
                for key, value in bucket_data.get('data', {}).items():
                    bucket.set(key, value)
                bucket.created_at = datetime.fromisoformat(bucket_data['created_at'])
                bucket.updated_at = datetime.fromisoformat(bucket_data['updated_at'])
                bucket.metadata = bucket_data.get('metadata', {})
                self.buckets[name] = bucket
            
            # 恢复全局变量
            self.global_vars = data.get('global_vars', {})
            self.current_bucket = data.get('current_bucket', 'default')
            
            logger.info(f"上下文已从 {self.save_path} 加载")
            
        except Exception as e:
            logger.error(f"加载上下文失败：{e}")
    
    def __repr__(self):
        return f"ContextManager(buckets={list(self.buckets.keys())}, current={self.current_bucket})"


# 全局上下文管理器实例
_global_context: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """获取全局上下文管理器"""
    global _global_context
    if _global_context is None:
        _global_context = ContextManager()
    return _global_context


def reset_context_manager():
    """重置全局上下文管理器"""
    global _global_context
    _global_context = ContextManager()
