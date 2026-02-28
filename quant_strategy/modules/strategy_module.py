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
    
    def list_strategies(self, by_category: bool = True, **kwargs) -> ModuleResult:
        """列出所有策略"""
        try:
            # 策略分类定义
            strategies_by_category = {
                "趋势跟踪": {
                    'dual_ma': {'name': '双均线策略', 'class': 'DualMAStrategy', 'desc': '短线/长线均线交叉'},
                    'momentum': {'name': '动量策略', 'class': 'MomentumStrategy', 'desc': '基于价格动量'},
                },
                "震荡指标": {
                    'kdj': {'name': 'KDJ 策略', 'class': 'KDJStrategy', 'desc': '随机指标，适合震荡市'},
                    'rsi': {'name': 'RSI 策略', 'class': 'RSIStrategy', 'desc': '相对强弱指标'},
                    'cci': {'name': 'CCI 策略', 'class': 'CCIStrategy', 'desc': '商品通道指标'},
                },
                "波动率指标": {
                    'boll': {'name': '布林线策略', 'class': 'BOLLStrategy', 'desc': '基于标准差通道'},
                    'dmi': {'name': 'DMI 策略', 'class': 'DMIStrategy', 'desc': '方向移动指标'},
                },
                "趋势动量": {
                    'macd': {'name': 'MACD 策略', 'class': 'MACDStrategy', 'desc': '移动平均收敛发散'},
                },
                "量价分析": {
                    'volume_price': {'name': '量价策略', 'class': 'VolumePriceStrategy', 'desc': '成交量与价格结合'},
                },
                "情绪指标": {
                    'sentiment': {'name': '情绪策略', 'class': 'SentimentStrategy', 'desc': '市场情绪分析'},
                    'fear_greed': {'name': '恐慌贪婪策略', 'class': 'FearGreedStrategy', 'desc': '恐慌贪婪指数'},
                    'volume_sentiment': {'name': '量能情绪策略', 'class': 'VolumeSentimentStrategy', 'desc': '成交量情绪'},
                    'open_interest': {'name': '持仓量策略', 'class': 'OpenInterestStrategy', 'desc': '期货持仓量分析'},
                },
                "板块轮动": {
                    'sector_momentum': {'name': '板块动量策略', 'class': 'SectorMomentumRotationStrategy', 'desc': '板块动量轮动'},
                    'sector_flow': {'name': '板块资金流策略', 'class': 'SectorFlowStrategy', 'desc': '板块资金流向'},
                },
                "涨停板": {
                    'first_limit_up': {'name': '首板策略', 'class': 'FirstLimitUpStrategy', 'desc': '首个涨停板捕捉'},
                    'continuous_limit_up': {'name': '连板策略', 'class': 'ContinuousLimitUpStrategy', 'desc': '连续涨停板'},
                    'limit_up_pullback': {'name': '涨停回调策略', 'class': 'LimitUpPullbackStrategy', 'desc': '涨停后回调'},
                },
            }

            # 统计总数
            total_count = sum(len(strats) for strats in strategies_by_category.values())

            # 构建返回数据
            if by_category:
                data = {
                    category: {
                        key: {'name': info['name'], 'class': info['class'], 'desc': info.get('desc', '')}
                        for key, info in strats.items()
                    }
                    for category, strats in strategies_by_category.items()
                }
                message_lines = [f"共 {total_count} 个策略，分为 {len(strategies_by_category)} 类"]
                for category, strats in strategies_by_category.items():
                    message_lines.append(f"  {category}: {len(strats)} 个")
                message = "\n".join(message_lines)
            else:
                # 扁平化列表
                data = {}
                for category, strats in strategies_by_category.items():
                    for key, info in strats.items():
                        data[key] = {**info, 'category': category}
                message = f"共 {total_count} 个策略"

            return ModuleResult(
                success=True,
                message=message,
                data=data,
                metadata={
                    'count': total_count,
                    'categories': len(strategies_by_category),
                    'by_category': by_category
                }
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

            # 使用 query 方法查询
            df = history.query(ts_code=ts_code, limit=limit)

            if df.empty:
                return ModuleResult(
                    success=True,
                    message="暂无回测记录",
                    data=[],
                    metadata={'count': 0}
                )

            # 转换为字典列表
            records = df.to_dict('records')

            return ModuleResult(
                success=True,
                message=f"回测历史 (共 {len(records)} 条)",
                data=records,
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
            
            # 查找指定 ID 的记录
            for record in history.records:
                if record.record_id == backtest_id:
                    return ModuleResult(
                        success=True,
                        message=f"回测详情：{backtest_id}",
                        data=record.to_dict()
                    )
            
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
