"""
动量策略
基于价格动量和 RSI 指标
"""
import pandas as pd
import numpy as np
from typing import Dict

from .base_strategy import BaseStrategy, Signal, SignalType


class MomentumStrategy(BaseStrategy):
    """
    动量策略
    
    结合价格动量和 RSI 超买超卖指标
    - 当动量为正且 RSI 超卖时买入
    - 当动量为负且 RSI 超买时卖出
    """
    
    def __init__(self, lookback_period: int = 20, rsi_period: int = 14,
                 rsi_oversold: float = 30, rsi_overbought: float = 70,
                 momentum_threshold: float = 0.02,
                 name: str = "Momentum", params: dict = None):
        """
        初始化动量策略
        
        Args:
            lookback_period: 动量计算周期
            rsi_period: RSI 计算周期
            rsi_oversold: RSI 超卖线
            rsi_overbought: RSI 超买线
            momentum_threshold: 动量阈值
            name: 策略名称
            params: 其他参数
        """
        super().__init__(name, params or {
            "lookback_period": lookback_period,
            "rsi_period": rsi_period,
            "rsi_oversold": rsi_oversold,
            "rsi_overbought": rsi_overbought,
            "momentum_threshold": momentum_threshold
        })
        self.lookback_period = lookback_period
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.momentum_threshold = momentum_threshold
    
    def _calculate_rsi(self, prices: pd.Series) -> float:
        """计算 RSI"""
        if len(prices) < self.rsi_period + 1:
            return 50.0
        
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        
        rs = gain / loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50.0
    
    def _calculate_momentum(self, prices: pd.Series) -> float:
        """计算价格动量"""
        if len(prices) < self.lookback_period:
            return 0.0
        
        momentum = (prices.iloc[-1] - prices.iloc[-self.lookback_period]) / prices.iloc[-self.lookback_period]
        return momentum
    
    def generate_signal(self, data: pd.DataFrame, current_idx: int) -> Signal:
        """生成交易信号"""
        min_required = max(self.lookback_period, self.rsi_period) + 5
        
        if current_idx < min_required:
            return Signal(
                signal_type=SignalType.HOLD,
                price=data.iloc[current_idx]["close"],
                reason="数据不足"
            )
        
        # 获取价格序列
        prices = data["close"].iloc[:current_idx + 1]
        current_price = prices.iloc[-1]
        
        # 计算指标
        momentum = self._calculate_momentum(prices)
        rsi = self._calculate_rsi(prices)
        
        signal_type = SignalType.HOLD
        reason = ""
        strength = 0.5
        
        # 买入条件：动量为正且 RSI 超卖
        if momentum > self.momentum_threshold and rsi < self.rsi_oversold:
            if self.position <= 0:
                signal_type = SignalType.BUY
                reason = f"动量买入：momentum={momentum:.2%}, RSI={rsi:.1f}"
                strength = min(1.0, (self.rsi_oversold - rsi) / self.rsi_oversold * 0.5 + 0.5)
        
        # 卖出条件：动量为负且 RSI 超买
        elif momentum < -self.momentum_threshold and rsi > self.rsi_overbought:
            if self.position > 0:
                signal_type = SignalType.SELL
                reason = f"动量卖出：momentum={momentum:.2%}, RSI={rsi:.1f}"
                strength = min(1.0, (rsi - self.rsi_overbought) / (100 - self.rsi_overbought) * 0.5 + 0.5)
        
        # 止损条件：动量大幅反转
        elif self.position > 0 and momentum < -self.momentum_threshold * 2:
            signal_type = SignalType.SELL
            reason = f"动量止损：momentum={momentum:.2%}"
            strength = 0.8
        
        return Signal(
            signal_type=signal_type,
            price=current_price,
            strength=strength,
            reason=reason,
            metadata={
                "momentum": momentum,
                "rsi": rsi,
                "lookback_period": self.lookback_period,
                "rsi_period": self.rsi_period
            }
        )
    
    def get_params_description(self) -> Dict[str, dict]:
        """返回参数说明"""
        return {
            "lookback_period": {
                "type": int,
                "default": 20,
                "range": (10, 60),
                "description": "动量计算周期"
            },
            "rsi_period": {
                "type": int,
                "default": 14,
                "range": (7, 28),
                "description": "RSI 计算周期"
            },
            "rsi_oversold": {
                "type": float,
                "default": 30,
                "range": (20, 40),
                "description": "RSI 超卖线"
            },
            "rsi_overbought": {
                "type": float,
                "default": 70,
                "range": (60, 80),
                "description": "RSI 超买线"
            },
            "momentum_threshold": {
                "type": float,
                "default": 0.02,
                "range": (0.01, 0.05),
                "description": "动量阈值"
            }
        }
