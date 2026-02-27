"""
模块系统

提供统一的模块接口，支持：
- 数据查看模块
- 策略查看模块
- 回测分析模块
- 配置管理模块
"""
from .base import (
    BaseModule,
    ModuleInfo,
    ModuleType,
    ModuleResult,
    ModuleRegistry,
    get_module_registry,
    register_module,
)

__all__ = [
    'BaseModule',
    'ModuleInfo',
    'ModuleType',
    'ModuleResult',
    'ModuleRegistry',
    'get_module_registry',
    'register_module',
]
