"""
Skill 机制框架

支持可插拔的技能系统，每个 Skill 代表一个可执行的功能单元。
支持复杂指令的解析和执行。
"""
import re
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
from enum import Enum


class SkillStatus(Enum):
    """Skill 执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SkillResult:
    """Skill 执行结果"""
    success: bool
    message: str
    data: Any = None
    error: Optional[str] = None
    context_updates: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self):
        status = "[OK]" if self.success else "[FAIL]"
        return f"{status} {self.message}"


@dataclass
class SkillDefinition:
    """Skill 定义"""
    name: str
    description: str
    aliases: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    examples: List[str] = field(default_factory=list)
    category: str = "general"
    requires_context: List[str] = field(default_factory=list)
    provides_context: List[str] = field(default_factory=list)


class Skill(ABC):
    """Skill 基类"""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.status = SkillStatus.PENDING
        self.progress = 0  # 0-100
        self.result: Optional[SkillResult] = None
    
    @property
    @abstractmethod
    def definition(self) -> SkillDefinition:
        """返回 Skill 定义"""
        pass
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any], **kwargs) -> SkillResult:
        """
        执行 Skill
        
        Args:
            context: 上下文数据
            **kwargs: 参数
            
        Returns:
            SkillResult
        """
        pass
    
    def validate(self, context: Dict[str, Any], **kwargs) -> Tuple[bool, Optional[str]]:
        """
        验证参数
        
        Returns:
            (是否有效，错误信息)
        """
        return True, None
    
    def on_progress(self, progress: int, message: str):
        """进度回调"""
        self.progress = progress
        logger.info(f"[{self.name}] {progress}%: {message}")
    
    def __repr__(self):
        return f"Skill({self.name}, status={self.status.value})"


class SkillRegistry:
    """Skill 注册表"""
    
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._aliases: Dict[str, str] = {}
        self._categories: Dict[str, List[str]] = {}
    
    def register(self, skill: Skill):
        """注册 Skill"""
        name = skill.definition.name
        self._skills[name] = skill
        
        # 注册别名
        for alias in skill.definition.aliases:
            self._aliases[alias.lower()] = name
        
        # 注册分类
        category = skill.definition.category
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(name)
        
        logger.info(f"Skill 已注册：{name}")
    
    def unregister(self, name: str):
        """注销 Skill"""
        if name in self._skills:
            skill = self._skills[name]
            del self._skills[name]
            
            # 删除别名
            for alias, skill_name in list(self._aliases.items()):
                if skill_name == name:
                    del self._aliases[alias]
            
            # 从分类中删除
            for category, names in self._categories.items():
                if name in names:
                    names.remove(name)
            
            logger.info(f"Skill 已注销：{name}")
    
    def get(self, name: str) -> Optional[Skill]:
        """获取 Skill"""
        # 直接查找
        if name in self._skills:
            return self._skills[name]
        
        # 通过别名查找
        name_lower = name.lower()
        if name_lower in self._aliases:
            return self._skills.get(self._aliases[name_lower])
        
        return None
    
    def list_skills(self) -> List[str]:
        """列出所有 Skill 名称"""
        return list(self._skills.keys())
    
    def list_by_category(self, category: str) -> List[str]:
        """按分类列出 Skill"""
        return self._categories.get(category, [])
    
    def list_categories(self) -> List[str]:
        """列出所有分类"""
        return list(self._categories.keys())
    
    def search(self, query: str) -> List[Tuple[str, float]]:
        """
        搜索 Skill
        
        Returns:
            [(Skill 名称，匹配度)] 列表
        """
        results = []
        query_lower = query.lower()
        
        for name, skill in self._skills.items():
            score = 0
            
            # 名称匹配
            if query_lower in name.lower():
                score += 0.5
            
            # 描述匹配
            if query_lower in skill.definition.description.lower():
                score += 0.3
            
            # 别名匹配
            if query_lower in [a.lower() for a in skill.definition.aliases]:
                score += 0.4
            
            # 分类匹配
            if query_lower in skill.definition.category.lower():
                score += 0.2
            
            if score > 0:
                results.append((name, score))
        
        # 按匹配度排序
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    def get_help(self, name: str) -> str:
        """获取 Skill 帮助信息"""
        skill = self.get(name)
        if not skill:
            return f"❌ 未找到 Skill: {name}"
        
        defn = skill.definition
        help_text = f"""
📖 {defn.name} - {defn.description}

分类：{defn.category}
别名：{', '.join(defn.aliases) if defn.aliases else '无'}

参数:
"""
        for param, spec in defn.parameters.items():
            required = spec.get('required', False)
            desc = spec.get('description', '')
            default = spec.get('default', '无')
            help_text += f"  - {param}: {desc} (必填：{required}, 默认：{default})\n"
        
        if defn.examples:
            help_text += "\n示例:\n"
            for example in defn.examples:
                help_text += f"  • {example}\n"
        
        return help_text.strip()


class SkillExecutor:
    """Skill 执行器"""
    
    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self.running_tasks: Dict[str, asyncio.Task] = {}
    
    async def execute(self, skill_name: str, context: Dict[str, Any], **kwargs) -> SkillResult:
        """执行 Skill"""
        skill = self.registry.get(skill_name)
        if not skill:
            return SkillResult(
                success=False,
                message=f"未找到 Skill: {skill_name}"
            )
        
        # 验证参数
        valid, error = skill.validate(context, **kwargs)
        if not valid:
            return SkillResult(
                success=False,
                message=f"参数验证失败：{error}"
            )
        
        try:
            skill.status = SkillStatus.RUNNING
            result = await skill.execute(context, **kwargs)
            skill.result = result
            skill.status = SkillStatus.SUCCESS if result.success else SkillStatus.FAILED
            return result
        except asyncio.CancelledError:
            skill.status = SkillStatus.CANCELLED
            return SkillResult(
                success=False,
                message="任务已取消"
            )
        except Exception as e:
            skill.status = SkillStatus.FAILED
            logger.exception(f"Skill 执行失败：{skill_name}")
            return SkillResult(
                success=False,
                message=f"执行失败：{str(e)}",
                error=str(e)
            )
    
    def cancel(self, skill_name: str):
        """取消正在执行的 Skill"""
        if skill_name in self.running_tasks:
            self.running_tasks[skill_name].cancel()
            del self.running_tasks[skill_name]


# 全局注册表
_global_registry: Optional[SkillRegistry] = None
_global_executor: Optional[SkillExecutor] = None


def get_registry() -> SkillRegistry:
    """获取全局注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry


def get_executor() -> SkillExecutor:
    """获取全局执行器"""
    global _global_executor
    if _global_executor is None:
        _global_executor = SkillExecutor(get_registry())
    return _global_executor


def register_skill(skill: Skill):
    """装饰器：注册 Skill"""
    def decorator(cls):
        instance = cls()
        get_registry().register(instance)
        return cls
    return decorator
