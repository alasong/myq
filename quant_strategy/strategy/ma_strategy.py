"""
双均线策略
金叉买入，死叉卖出
"""
import pandas as pd
import numpy as np
from typing import Dict

from .base_strategy import BaseStrategy, Signal, SignalType


class DualMAStrategy(BaseStrategy):
    """
    双均线交叉策略
    
    当短期均线上穿长期均线时产生买入信号
    当短期均线下穿长期均线时产生卖出信号
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
    
    def generate_signal(self, data: pd.DataFrame, current_idx: int) -> Signal:
        """生成交易信号"""
        if current_idx < self.long_window:
            # 数据不足，返回持有信号
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
                if self.position <= 0:  # 空仓或空仓时才买入
                    signal_type = SignalType.BUY
                    reason = f"金叉：MA{self.short_window}上穿 MA{self.long_window}"
                    strength = min(1.0, (short_ma - long_ma) / long_ma * 100 + 0.5)
            # 死叉：短期均线下穿长期均线
            elif self.prev_short_ma >= self.prev_long_ma and short_ma < long_ma:
                if self.position > 0:  # 有仓位时才卖出
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
