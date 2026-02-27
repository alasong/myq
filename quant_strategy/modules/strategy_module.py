"""
策略查看模块

支持：
- 查看策略列表
- 查看策略详情
- 查看策略配置
- 查看回测历史
- 查看回测详情
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from .base import BaseModule, ModuleInfo, ModuleType, ModuleResult, register_module


@register_module("strategy")
class StrategyModule(BaseModule):
    """策略查看模块"""
    
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="strategy",
            module_type=ModuleType.STRATEGY,
            description="策略查看与配置管理",
            tags=["策略", "配置", "回测"]
        )
    
    def get_actions(self) -> List[str]:
        return [
            "list",             # 列出策略
            "info",             # 策略详情
            "config",           # 策略配置
            "history",          # 回测历史
            "backtest-info",    # 回测详情
            "compare",          # 策略对比
        ]
    
    def execute(self, action: str, **kwargs) -> ModuleResult:
        """执行模块操作"""
        self._record_call(True)
        
        actions = {
            'list': self.list_strategies,
            'info': self.strategy_info,
            'config': self.strategy_config,
            'history': self.backtest_history,
            'backtest-info': self.backtest_info,
            'compare': self.compare_strategies,
        }
        
        if action not in actions:
            return ModuleResult(
                success=False,
                message=f"未知操作：{action}",
                error=f"支持的操作：{list(actions.keys())}"
            )
        
        try:
            return actions[action](**kwargs)
        except Exception as e:
            self._record_call(False)
            return ModuleResult(
                success=False,
                message=f"执行失败：{str(e)}",
                error=str(e)
            )
    
    def list_strategies(self, **kwargs) -> ModuleResult:
        """列出所有策略"""
        try:
            from quant_strategy.strategy import (
                DualMAStrategy, MomentumStrategy,
                KDJStrategy, RSIStrategy, BOLLStrategy,
                DMIStrategy, CCIStrategy, MACDStrategy, VolumePriceStrategy
            )
            
            strategies = {
                'dual_ma': {'name': '双均线策略', 'class': 'DualMAStrategy'},
                'momentum': {'name': '动量策略', 'class': 'MomentumStrategy'},
                'kdj': {'name': 'KDJ 策略', 'class': 'KDJStrategy'},
                'rsi': {'name': 'RSI 策略', 'class': 'RSIStrategy'},
                'boll': {'name': '布林线策略', 'class': 'BOLLStrategy'},
                'dmi': {'name': 'DMI 策略', 'class': 'DMIStrategy'},
                'cci': {'name': 'CCI 策略', 'class': 'CCIStrategy'},
                'macd': {'name': 'MACD 策略', 'class': 'MACDStrategy'},
                'volume_price': {'name': '量价策略', 'class': 'VolumePriceStrategy'},
            }
            
            return ModuleResult(
                success=True,
                message=f"共 {len(strategies)} 个策略",
                data=strategies,
                metadata={'count': len(strategies)}
            )
            
        except ImportError as e:
            return ModuleResult(
                success=False,
                message=f"导入策略模块失败：{str(e)}",
                error=str(e)
            )
    
    def strategy_info(self, name: str = None, **kwargs) -> ModuleResult:
        """查看策略详情"""
        if not name:
            return ModuleResult(
                success=False,
                message="请指定策略名称，例如：info name=dual_ma"
            )
        
        try:
            from quant_strategy.strategy import get_strategy_class
            
            strategy_class = get_strategy_class(name)
            
            # 获取策略参数
            params = {}
            if hasattr(strategy_class, '__init__'):
                import inspect
                sig = inspect.signature(strategy_class.__init__)
                for param_name, param in sig.parameters.items():
                    if param_name != 'self':
                        params[param_name] = {
                            'default': param.default if param.default != inspect.Parameter.empty else None,
                            'annotation': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any'
                        }
            
            info = {
                'name': name,
                'class_name': strategy_class.__name__,
                'description': strategy_class.__doc__ or '',
                'parameters': params
            }
            
            return ModuleResult(
                success=True,
                message=f"策略：{name}",
                data=info
            )
            
        except Exception as e:
            return ModuleResult(
                success=False,
                message=f"获取策略信息失败：{str(e)}",
                error=str(e)
            )
    
    def strategy_config(self, name: str = None, **kwargs) -> ModuleResult:
        """查看/设置策略配置"""
        if not name:
            return ModuleResult(
                success=False,
                message="请指定策略名称"
            )
        
        config_dir = Path('configs/strategies')
        config_file = config_dir / f"{name}.yaml"
        
        # 如果是获取配置
        if not kwargs:
            if config_file.exists():
                try:
                    import yaml
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                    return ModuleResult(
                        success=True,
                        message=f"策略 {name} 配置",
                        data=config
                    )
                except Exception as e:
                    return ModuleResult(
                        success=False,
                        message=f"读取配置失败：{str(e)}",
                        error=str(e)
                    )
            else:
                # 返回默认配置
                return ModuleResult(
                    success=True,
                    message=f"策略 {name} 无自定义配置，使用默认配置",
                    data=self._get_default_config(name)
                )
        
        # 如果是保存配置
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            import yaml
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(kwargs, f, allow_unicode=True, default_flow_style=False)
            
            return ModuleResult(
                success=True,
                message=f"策略 {name} 配置已保存",
                data=kwargs
            )
        except Exception as e:
            return ModuleResult(
                success=False,
                message=f"保存配置失败：{str(e)}",
                error=str(e)
            )
    
    def _get_default_config(self, name: str) -> Dict:
        """获取默认策略配置"""
        default_configs = {
            'dual_ma': {
                'short_window': 5,
                'long_window': 20,
            },
            'kdj': {
                'n': 9,
                'm1': 3,
                'm2': 3,
            },
            'rsi': {
                'window': 14,
                'overbought': 70,
                'oversold': 30,
            },
            'macd': {
                'fast_period': 12,
                'slow_period': 26,
                'signal_period': 9,
            }
        }
        return default_configs.get(name, {})
    
    def backtest_history(self, ts_code: str = None, limit: int = 10, **kwargs) -> ModuleResult:
        """查看回测历史"""
        try:
            from quant_strategy.analyzer.backtest_history import BacktestHistory
            
            history = BacktestHistory()
            
            if ts_code:
                records = history.get_by_ts_code(ts_code, limit=limit)
            else:
                records = history.get_all(limit=limit)
            
            return ModuleResult(
                success=True,
                message=f"回测历史 (共 {len(records)} 条)",
                data=[self._record_to_dict(r) for r in records],
                metadata={'count': len(records)}
            )
            
        except Exception as e:
            return ModuleResult(
                success=False,
                message=f"获取回测历史失败：{str(e)}",
                error=str(e)
            )
    
    def backtest_info(self, backtest_id: str = None, **kwargs) -> ModuleResult:
        """查看回测详情"""
        if not backtest_id:
            return ModuleResult(
                success=False,
                message="请指定回测 ID"
            )
        
        try:
            from quant_strategy.analyzer.backtest_history import BacktestHistory
            
            history = BacktestHistory()
            record = history.get_by_id(backtest_id)
            
            if record:
                return ModuleResult(
                    success=True,
                    message=f"回测详情：{backtest_id}",
                    data=self._record_to_dict(record)
                )
            else:
                return ModuleResult(
                    success=False,
                    message=f"未找到回测记录：{backtest_id}"
                )
                
        except Exception as e:
            return ModuleResult(
                success=False,
                message=f"获取回测详情失败：{str(e)}",
                error=str(e)
            )
    
    def compare_strategies(self, strategies: List[str] = None, ts_code: str = None, **kwargs) -> ModuleResult:
        """策略对比"""
        if not strategies:
            return ModuleResult(
                success=False,
                message="请指定策略列表，例如：compare strategies=['dual_ma','kdj'] ts_code=000001.SZ"
            )
        
        if not ts_code:
            return ModuleResult(
                success=False,
                message="请指定股票代码"
            )
        
        # TODO: 实现策略对比逻辑
        return ModuleResult(
            success=True,
            message=f"策略对比：{strategies} on {ts_code}",
            data={
                'strategies': strategies,
                'ts_code': ts_code,
                'note': '功能开发中...'
            }
        )
    
    def _record_to_dict(self, record) -> Dict:
        """将回测记录转换为字典"""
        if hasattr(record, '__dict__'):
            return record.__dict__
        return dict(record)
    
    def get_help(self, action: str = None) -> str:
        """获取帮助信息"""
        help_text = {
            'list': "列出所有可用策略",
            'info': "查看策略详情\n  参数：name - 策略名称 (必需)",
            'config': "查看/设置策略配置\n  参数：name - 策略名称，其他为配置项",
            'history': "查看回测历史\n  参数：ts_code - 股票代码，limit - 显示数量",
            'backtest-info': "查看回测详情\n  参数：backtest_id - 回测 ID (必需)",
            'compare': "策略对比\n  参数：strategies - 策略列表，ts_code - 股票代码",
        }
        
        if action:
            return help_text.get(action, f"未知操作：{action}")
        
        return "策略模块 - 支持策略查看、配置管理、回测历史\n" + "\n".join(
            f"  {k}: {v.split(chr(10))[0]}" for k, v in help_text.items()
        )
