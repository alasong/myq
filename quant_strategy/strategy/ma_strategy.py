"""
双均线策略
金叉买入，死叉卖出
支持向量化计算和传统逐 bar 模式
"""
import pandas as pd
import numpy as np
from typing import Dict

from .base_strategy import BaseStrategy, Signal, SignalType
from .vectorized_strategy import VectorizedStrategy, SignalGenerator


class DualMAStrategy(VectorizedStrategy):
    """
    双均线交叉策略

    当短期均线上穿长期均线时产生买入信号
    当短期均线下穿长期均线时产生卖出信号
    
    支持两种模式：
    1. 向量化模式：一次性计算所有信号（推荐）
    2. 逐 bar 模式：向后兼容
    """

    def __init__(self, short_window: int = 5, long_window: int = 20,
                 name: str = "DualMA", params: dict = None):
        """
        初始化双均线策略

        Args:
            short_window: 短期均线周期
            long_window: 长期均线周期
            name: 策略名称
            params: 其他参数
        """
        super().__init__(name, params or {
            "short_window": short_window,
            "long_window": long_window
        })
        self.short_window = short_window
        self.long_window = long_window
        self.prev_short_ma = None
        self.prev_long_ma = None

    def generate_signals_vectorized(self, data: pd.DataFrame) -> Signal:
        """
        向量化信号生成
        
        Args:
            data: 历史数据 DataFrame
            
        Returns:
            VectorizedSignal: 向量化信号
        """
        indicators = self.get_indicators()
        
        # 计算均线（使用缓存）
        short_ma = indicators.sma(data, "close", self.short_window)
        long_ma = indicators.sma(data, "close", self.long_window)
        
        # 检测金叉和死叉
        golden_cross = SignalGenerator.crossover(short_ma, long_ma)
        death_cross = SignalGenerator.crossunder(short_ma, long_ma)
        
        # 生成信号条件
        conditions = {
            SignalType.BUY: golden_cross,
            SignalType.SELL: death_cross
        }
        
        # 计算信号强度（均线差值百分比）
        ma_diff_pct = (short_ma - long_ma) / long_ma
        strengths = np.abs(ma_diff_pct.values) * 100 + 0.5
        strengths = np.clip(strengths, 0, 1.0)
        
        # 生成信号数组
        signal_types, _ = SignalGenerator.generate_signal_array(conditions, strengths)
        
        # 生成原因
        reasons = []
        for i in range(len(data)):
            if golden_cross.iloc[i]:
                reasons.append(f"金叉：MA{self.short_window}上穿 MA{self.long_window}")
            elif death_cross.iloc[i]:
                reasons.append(f"死叉：MA{self.short_window}下穿 MA{self.long_window}")
            else:
                reasons.append("")
        
        from .vectorized_strategy import VectorizedSignal
        return VectorizedSignal(
            signal_types=signal_types,
            strengths=strengths,
            reasons=reasons,
            metadata={
                "short_ma": short_ma,
                "long_ma": long_ma,
                "ma_diff": short_ma - long_ma
            }
        )

    def generate_signal_bar(self, data: pd.DataFrame, current_idx: int) -> Signal:
        """
        逐 bar 模式信号生成（向后兼容）
        """
        if current_idx < self.long_window:
            return Signal(
                signal_type=SignalType.HOLD,
                price=data.iloc[current_idx]["close"],
                reason="数据不足"
            )

        # 计算均线
        close_prices = data["close"].iloc[:current_idx + 1]
        short_ma = close_prices.rolling(window=self.short_window).mean().iloc[-1]
        long_ma = close_prices.rolling(window=self.long_window).mean().iloc[-1]

        current_price = data.iloc[current_idx]["close"]

        # 获取前一周期的均线值
        if current_idx >= 1:
            prev_close = data["close"].iloc[:current_idx]
            self.prev_short_ma = prev_close.rolling(window=self.short_window).mean().iloc[-1]
            self.prev_long_ma = prev_close.rolling(window=self.long_window).mean().iloc[-1]

        signal_type = SignalType.HOLD
        reason = ""
        strength = 0.5

        # 金叉：短期均线上穿长期均线
        if self.prev_short_ma is not None:
            if self.prev_short_ma <= self.prev_long_ma and short_ma > long_ma:
                if self.position <= 0:
                    signal_type = SignalType.BUY
                    reason = f"金叉：MA{self.short_window}上穿 MA{self.long_window}"
                    strength = min(1.0, (short_ma - long_ma) / long_ma * 100 + 0.5)
            # 死叉：短期均线下穿长期均线
            elif self.prev_short_ma >= self.prev_long_ma and short_ma < long_ma:
                if self.position > 0:
                    signal_type = SignalType.SELL
                    reason = f"死叉：MA{self.short_window}下穿 MA{self.long_window}"
                    strength = min(1.0, (long_ma - short_ma) / long_ma * 100 + 0.5)

        # 更新前值
        self.prev_short_ma = short_ma
        self.prev_long_ma = long_ma

        return Signal(
            signal_type=signal_type,
            price=current_price,
            strength=strength,
            reason=reason,
            metadata={
                "short_ma": short_ma,
                "long_ma": long_ma,
                "ma_diff": short_ma - long_ma
            }
        )

    def get_params_description(self) -> Dict[str, dict]:
        """返回参数说明"""
        return {
            "short_window": {
                "type": int,
                "default": 5,
                "range": (3, 30),
                "description": "短期均线周期"
            },
            "long_window": {
                "type": int,
                "default": 20,
                "range": (10, 120),
                "description": "长期均线周期"
            }
        }
