"""
模块系统 - 基础框架

提供统一的模块接口，支持：
- 数据查看模块
- 策略查看模块
- 回测分析模块
- 配置管理模块
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ModuleType(Enum):
    """模块类型"""
    DATA = "data"           # 数据查看
    STRATEGY = "strategy"   # 策略查看
    BACKTEST = "backtest"   # 回测分析
    CONFIG = "config"       # 配置管理
    CACHE = "cache"         # 缓存管理
    CUSTOM = "custom"       # 自定义


@dataclass
class ModuleInfo:
    """模块信息"""
    name: str
    module_type: ModuleType
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class ModuleResult:
    """模块执行结果"""
    success: bool
    message: str
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self):
        status = "[OK]" if self.success else "[FAIL]"
        return f"{status} {self.message}"


class BaseModule(ABC):
    """模块基类"""
    
    def __init__(self, ctx: Dict[str, Any] = None):
        """
        初始化模块
        
        Args:
            ctx: 共享上下文（包含 provider、cache 等）
        """
        self.ctx = ctx or {}
        self.created_at = datetime.now()
        self.stats = {
            'calls': 0,
            'success': 0,
            'failed': 0
        }
    
    @property
    @abstractmethod
    def info(self) -> ModuleInfo:
        """返回模块信息"""
        pass
    
    @abstractmethod
    def execute(self, action: str, **kwargs) -> ModuleResult:
        """
        执行模块操作
        
        Args:
            action: 操作名称
            **kwargs: 操作参数
            
        Returns:
            ModuleResult
        """
        pass
    
    def get_actions(self) -> List[str]:
        """获取支持的操作列表"""
        return []
    
    def get_help(self, action: str = None) -> str:
        """获取帮助信息"""
        if action:
            return f"操作 '{action}' 的帮助信息"
        return f"模块 '{self.info.name}' 支持的操作：{self.get_actions()}"
    
    def _record_call(self, success: bool):
        """记录调用统计"""
        self.stats['calls'] += 1
        if success:
            self.stats['success'] += 1
        else:
            self.stats['failed'] += 1
    
    def get_stats(self) -> Dict:
        """获取模块统计信息"""
        return self.stats.copy()


class ModuleRegistry:
    """模块注册表"""
    
    _instance = None
    _modules: Dict[str, BaseModule] = {}
    _ctx: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def set_context(self, key: str, value: Any):
        """设置共享上下文"""
        self._ctx[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """获取共享上下文"""
        return self._ctx.get(key, default)
    
    def register(self, module: BaseModule):
        """注册模块"""
        name = module.info.name
        self._modules[name] = module
        print(f"[模块已注册] {name} - {module.info.description}")
    
    def unregister(self, name: str):
        """注销模块"""
        if name in self._modules:
            del self._modules[name]
    
    def get(self, name: str) -> Optional[BaseModule]:
        """获取模块"""
        return self._modules.get(name)
    
    def list_modules(self) -> List[str]:
        """列出所有模块"""
        return list(self._modules.keys())
    
    def list_by_type(self, module_type: ModuleType) -> List[str]:
        """按类型列出模块"""
        return [
            name for name, module in self._modules.items()
            if module.info.module_type == module_type
        ]
    
    def search(self, query: str) -> List[str]:
        """搜索模块"""
        query_lower = query.lower()
        results = []
        for name, module in self._modules.items():
            if (query_lower in name.lower() or 
                query_lower in module.info.description.lower() or
                any(query_lower in tag.lower() for tag in module.info.tags)):
                results.append(name)
        return results


# 全局注册表实例
_registry = ModuleRegistry()


def get_module_registry() -> ModuleRegistry:
    """获取全局模块注册表"""
    return _registry


def register_module(name: str = None):
    """模块注册装饰器"""
    def decorator(cls):
        module_name = name or cls.__name__
        # 从注册表获取上下文
        ctx = {
            'provider': _registry.get_context('provider'),
            'cache': _registry.get_context('cache'),
        }
        instance = cls(ctx=ctx)
        _registry.register(instance)
        return cls
    return decorator
