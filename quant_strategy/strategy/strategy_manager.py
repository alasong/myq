"""
策略管理器模块
支持策略的激活/停用管理，以及激活策略的批量回测
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger


@dataclass
class StrategyStatus:
    """策略状态"""
    name: str
    enabled: bool = True
    disabled_reason: str = ""
    disabled_at: Optional[str] = None
    notes: str = ""


class StrategyManager:
    """
    策略管理器
    
    功能：
    - 管理策略的激活/停用状态
    - 获取激活策略列表
    - 批量回测激活策略
    """
    
    DEFAULT_STRATEGIES = [
        "dual_ma", "momentum", "kdj", "rsi", "boll",
        "dmi", "cci", "macd", "volume_price",
        "volume_sentiment", "fear_greed", "open_interest"
    ]
    
    def __init__(self, config_file: str = None):
        """
        初始化策略管理器
        
        Args:
            config_file: 配置文件路径，默认使用 ~/.qwen/strategy_config.json
        """
        if config_file is None:
            config_dir = Path.home() / ".qwen"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.config_file = config_dir / "strategy_config.json"
        else:
            self.config_file = Path(config_file)
        
        self.strategies: Dict[str, StrategyStatus] = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        if not self.config_file.exists():
            # 初始化默认配置，所有策略默认激活
            for name in self.DEFAULT_STRATEGIES:
                self.strategies[name] = StrategyStatus(name=name, enabled=True)
            self._save_config()
            logger.info(f"创建默认策略配置文件：{self.config_file}")
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for name, status_data in data.get("strategies", {}).items():
                self.strategies[name] = StrategyStatus(
                    name=name,
                    enabled=status_data.get("enabled", True),
                    disabled_reason=status_data.get("disabled_reason", ""),
                    disabled_at=status_data.get("disabled_at"),
                    notes=status_data.get("notes", "")
                )
            
            # 检查是否有新策略需要添加
            for name in self.DEFAULT_STRATEGIES:
                if name not in self.strategies:
                    self.strategies[name] = StrategyStatus(name=name, enabled=True)
            
            logger.debug(f"策略配置加载成功：{len(self.strategies)} 个策略")
        except Exception as e:
            logger.error(f"加载策略配置失败：{e}")
            # 初始化默认配置
            for name in self.DEFAULT_STRATEGIES:
                self.strategies[name] = StrategyStatus(name=name, enabled=True)
    
    def _save_config(self):
        """保存配置文件"""
        data = {
            "strategies": {
                name: {
                    "enabled": status.enabled,
                    "disabled_reason": status.disabled_reason,
                    "disabled_at": status.disabled_at,
                    "notes": status.notes
                }
                for name, status in self.strategies.items()
            },
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def enable(self, name: str) -> bool:
        """
        激活策略
        
        Args:
            name: 策略名称
            
        Returns:
            是否成功激活
        """
        if name not in self.strategies:
            logger.warning(f"未知策略：{name}")
            return False
        
        self.strategies[name].enabled = True
        self.strategies[name].disabled_reason = ""
        self.strategies[name].disabled_at = None
        self._save_config()
        
        logger.info(f"策略已激活：{name}")
        return True
    
    def disable(self, name: str, reason: str = "") -> bool:
        """
        停用策略
        
        Args:
            name: 策略名称
            reason: 停用原因
            
        Returns:
            是否成功停用
        """
        if name not in self.strategies:
            logger.warning(f"未知策略：{name}")
            return False
        
        self.strategies[name].enabled = False
        self.strategies[name].disabled_reason = reason
        self.strategies[name].disabled_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_config()
        
        logger.info(f"策略已停用：{name}, 原因：{reason}")
        return True
    
    def is_enabled(self, name: str) -> bool:
        """
        检查策略是否激活
        
        Args:
            name: 策略名称
            
        Returns:
            是否激活
        """
        if name not in self.strategies:
            return False
        return self.strategies[name].enabled
    
    def get_enabled_strategies(self) -> List[str]:
        """获取所有激活的策略名称列表"""
        return [name for name, status in self.strategies.items() if status.enabled]
    
    def get_disabled_strategies(self) -> List[str]:
        """获取所有停用的策略名称列表"""
        return [name for name, status in self.strategies.items() if not status.enabled]
    
    def get_all_strategies(self) -> List[str]:
        """获取所有策略名称列表"""
        return list(self.strategies.keys())
    
    def get_strategy_status(self, name: str) -> Optional[StrategyStatus]:
        """
        获取策略状态详情
        
        Args:
            name: 策略名称
            
        Returns:
            策略状态对象，如果策略不存在则返回 None
        """
        return self.strategies.get(name)
    
    def list_strategies(self, show_all: bool = True) -> str:
        """
        列出策略状态
        
        Args:
            show_all: 是否显示所有策略，否则只显示激活的
            
        Returns:
            格式化的策略列表字符串
        """
        lines = []
        lines.append("\n" + "=" * 70)
        lines.append("策略状态列表")
        lines.append("=" * 70)
        
        if show_all:
            lines.append(f"{'策略名称':20} | {'状态':8} | {'停用原因':30}")
            lines.append("-" * 70)
            for name, status in sorted(self.strategies.items()):
                status_str = "激活" if status.enabled else "停用"
                reason = status.disabled_reason[:28] + ".." if len(status.disabled_reason) > 30 else status.disabled_reason
                lines.append(f"{name:20} | {status_str:8} | {reason}")
        else:
            enabled = self.get_enabled_strategies()
            if not enabled:
                lines.append("没有激活的策略")
            else:
                lines.append("激活的策略:")
                for name in sorted(enabled):
                    lines.append(f"  - {name}")
        
        lines.append("=" * 70)
        lines.append(f"总计：{len(self.strategies)} 个策略，激活：{len(self.get_enabled_strategies())} 个，停用：{len(self.get_disabled_strategies())} 个")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def add_custom_strategy(self, name: str, notes: str = "") -> bool:
        """
        添加自定义策略
        
        Args:
            name: 策略名称
            notes: 备注信息
            
        Returns:
            是否成功添加
        """
        if name in self.strategies:
            logger.warning(f"策略已存在：{name}")
            return False
        
        self.strategies[name] = StrategyStatus(
            name=name,
            enabled=True,
            notes=notes
        )
        self._save_config()
        
        logger.info(f"已添加自定义策略：{name}")
        return True
    
    def remove_strategy(self, name: str) -> bool:
        """
        移除策略（仅支持自定义策略）
        
        Args:
            name: 策略名称
            
        Returns:
            是否成功移除
        """
        if name not in self.strategies:
            logger.warning(f"策略不存在：{name}")
            return False
        
        if name in self.DEFAULT_STRATEGIES:
            logger.warning(f"不能移除内置策略：{name}")
            return False
        
        del self.strategies[name]
        self._save_config()
        
        logger.info(f"已移除策略：{name}")
        return True
