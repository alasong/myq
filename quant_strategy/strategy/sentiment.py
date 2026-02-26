"""
市场情绪策略模块
基于市场情绪指标进行交易决策
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List

from .base_strategy import BaseStrategy, Signal, SignalType


class SentimentStrategy(BaseStrategy):
    """
    市场情绪策略基类
    
    提供情绪指标计算框架
    """
    name = "市场情绪策略"
    
    def __init__(self, lookback: int = 20):
        super().__init__()
        self.lookback = lookback
        self.market_data = None  # 全市场数据
    
    def set_market_data(self, market_data: Dict[str, pd.DataFrame]):
        """
        设置全市场数据用于计算情绪指标
        
        Args:
            market_data: {ts_code: DataFrame} 全市场股票数据
        """
        self.market_data = market_data
    
    def _calculate_market_breadth(self, data: pd.DataFrame, idx: int) -> float:
        """
        计算市场广度（涨跌比）
        
        Returns:
            涨跌比 (上涨家数/下跌家数)
        """
        if self.market_data is None:
            return 1.0
        
        up_count = 0
        down_count = 0
        
        for ts_code, stock_data in self.market_data.items():
            if idx < 1:
                continue
            close = stock_data.iloc[idx]["close"]
            prev_close = stock_data.iloc[idx - 1]["close"]
            
            if close > prev_close:
                up_count += 1
            elif close < prev_close:
                down_count += 1
        
        if down_count == 0:
            return up_count if up_count > 0 else 1.0
        
        return up_count / down_count
    
    def _calculate_limit_up_ratio(self, data: pd.DataFrame, idx: int) -> float:
        """
        计算涨停板比例
        
        Returns:
            涨停家数占比
        """
        if self.market_data is None:
            return 0.0
        
        limit_up_count = 0
        total_count = 0
        
        for ts_code, stock_data in self.market_data.items():
            if idx >= len(stock_data):
                continue
            
            close = stock_data.iloc[idx]["close"]
            prev_close = stock_data.iloc[idx - 1]["close"]
            
            # 涨停判断（10% 或 20%）
            pct_change = (close - prev_close) / prev_close
            if pct_change >= 0.095:  # 考虑四舍五入
                limit_up_count += 1
            total_count += 1
        
        return limit_up_count / max(total_count, 1)


class MarketBreadthStrategy(SentimentStrategy):
    """
    市场广度策略
    
    基于涨跌比（ADR）的情绪指标：
    - 涨跌比 > 2：市场情绪高涨，买入
    - 涨跌比 < 0.5：市场情绪低迷，卖出
    - 使用移动平均平滑
    """
    
    name = "市场广度策略"
    
    def __init__(self, lookback: int = 20, adr_period: int = 5,
                 high_threshold: float = 2.0, low_threshold: float = 0.5):
        """
        初始化策略
        
        Args:
            lookback: 历史数据周期
            adr_period: 涨跌比移动平均周期
            high_threshold: 超买阈值
            low_threshold: 超卖阈值
        """
        super().__init__(lookback)
        self.adr_period = adr_period
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.adr = None
    
    def on_init(self, data: pd.DataFrame):
        """初始化指标"""
        # 计算每日涨跌比
        adr_values = []
        for idx in range(len(data)):
            breadth = self._calculate_market_breadth(data, idx)
            adr_values.append(breadth)
        
        self.adr = pd.Series(adr_values).rolling(window=self.adr_period).mean()
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Optional[Signal]:
        """生成交易信号"""
        if idx < self.adr_period:
            return None
        
        current_adr = self.adr.iloc[idx]
        prev_adr = self.adr.iloc[idx - 1]
        
        # 情绪从低迷转暖：买入
        if prev_adr < self.low_threshold and current_adr >= self.low_threshold:
            return Signal(
                signal_type=SignalType.BUY,
                price=data.iloc[idx]["close"],
                strength=0.7,
                reason=f"市场广度回升 ADR={current_adr:.2f}"
            )
        
        # 情绪过热：卖出
        if self.position > 0 and current_adr > self.high_threshold:
            return Signal(
                signal_type=SignalType.SELL,
                price=data.iloc[idx]["close"],
                strength=0.6,
                reason=f"市场广度过热 ADR={current_adr:.2f}"
            )
        
        return None


class LimitUpStrategy(SentimentStrategy):
    """
    涨停板情绪策略
    
    基于涨停家数占比判断市场情绪：
    - 涨停占比 > 5%：情绪高涨，买入
    - 涨停占比 < 1%：情绪低迷，卖出
    """
    
    name = "涨停情绪策略"
    
    def __init__(self, lookback: int = 20, high_threshold: float = 0.05,
                 low_threshold: float = 0.01):
        """
        初始化策略
        
        Args:
            lookback: 历史数据周期
            high_threshold: 涨停占比高阈值
            low_threshold: 涨停占比低阈值
        """
        super().__init__(lookback)
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.limit_up_ratio = None
    
    def on_init(self, data: pd.DataFrame):
        """初始化指标"""
        lu_values = []
        for idx in range(len(data)):
            ratio = self._calculate_limit_up_ratio(data, idx)
            lu_values.append(ratio)
        
        self.limit_up_ratio = pd.Series(lu_values)
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Optional[Signal]:
        """生成交易信号"""
        if idx < 1:
            return None
        
        current_ratio = self.limit_up_ratio.iloc[idx]
        prev_ratio = self.limit_up_ratio.iloc[idx - 1]
        
        # 涨停潮：买入
        if current_ratio > self.high_threshold and self.position == 0:
            return Signal(
                signal_type=SignalType.BUY,
                price=data.iloc[idx]["close"],
                strength=0.8,
                reason=f"涨停潮 占比={current_ratio:.1%}"
            )
        
        # 情绪冰点：卖出
        if self.position > 0 and current_ratio < self.low_threshold:
            return Signal(
                signal_type=SignalType.SELL,
                price=data.iloc[idx]["close"],
                strength=0.6,
                reason=f"情绪冰点 占比={current_ratio:.1%}"
            )
        
        return None


class VolumeSentimentStrategy(BaseStrategy):
    """
    成交量情绪策略
    
    基于成交量变化判断情绪：
    - 放量上涨：情绪积极，买入
    - 缩量下跌：情绪消极，卖出
    - 天量：情绪过热，卖出
    """
    
    name = "成交量情绪策略"
    
    def __init__(self, vol_period: int = 20, high_vol_ratio: float = 2.0,
                 low_vol_ratio: float = 0.5):
        """
        初始化策略
        
        Args:
            vol_period: 成交量均线周期
            high_vol_ratio: 放量倍数
            low_vol_ratio: 缩量倍数
        """
        super().__init__()
        self.vol_period = vol_period
        self.high_vol_ratio = high_vol_ratio
        self.low_vol_ratio = low_vol_ratio
        self.vol_ma = None
    
    def on_init(self, data: pd.DataFrame):
        """初始化指标"""
        self.vol_ma = data['vol'].rolling(window=self.vol_period).mean()
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Optional[Signal]:
        """生成交易信号"""
        if idx < self.vol_period:
            return None
        
        close = data.iloc[idx]["close"]
        prev_close = data.iloc[idx - 1]["close"]
        vol = data.iloc[idx]["vol"]
        vol_avg = self.vol_ma.iloc[idx]
        
        vol_ratio = vol / vol_avg if vol_avg > 0 else 1.0
        price_change = (close - prev_close) / prev_close
        
        # 放量上涨（情绪积极）
        if price_change > 0.02 and vol_ratio > self.high_vol_ratio and self.position == 0:
            return Signal(
                signal_type=SignalType.BUY,
                price=close,
                strength=0.7,
                reason=f"放量上涨 {price_change:.1%} 量比{vol_ratio:.1f}"
            )
        
        # 天量（情绪过热）
        if self.position > 0 and vol_ratio > 3.0:
            return Signal(
                signal_type=SignalType.SELL,
                price=close,
                strength=0.6,
                reason=f"天量 量比{vol_ratio:.1f}"
            )
        
        # 缩量阴跌（情绪消极）
        if self.position > 0 and price_change < -0.01 and vol_ratio < self.low_vol_ratio:
            return Signal(
                signal_type=SignalType.SELL,
                price=close,
                strength=0.5,
                reason=f"缩量阴跌 量比{vol_ratio:.1f}"
            )
        
        return None


class FearGreedStrategy(BaseStrategy):
    """
    恐惧贪婪策略
    
    综合多个情绪指标计算恐惧贪婪指数：
    - 指标 < 25：极度恐惧，买入
    - 指标 > 75：极度贪婪，卖出
    """
    
    name = "恐惧贪婪策略"
    
    def __init__(self, lookback: int = 20, rsi_period: int = 14):
        """
        初始化策略
        
        Args:
            lookback: 历史数据周期
            rsi_period: RSI 计算周期
        """
        super().__init__()
        self.lookback = lookback
        self.rsi_period = rsi_period
        self.fear_greed_index = None
        self.rsi = None
    
    def on_init(self, data: pd.DataFrame):
        """初始化指标"""
        # 计算 RSI
        delta = data['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss
        self.rsi = 100 - (100 / (1 + rs))
        
        # 计算恐惧贪婪指数（简化版）
        # 1. RSI 反向指标（RSI 低=恐惧）
        # 2. 价格位置（接近低位=恐惧）
        
        lowest = data['low'].rolling(window=self.lookback).min()
        highest = data['high'].rolling(window=self.lookback).max()
        price_position = (data['close'] - lowest) / (highest - lowest) * 100
        
        # 综合指数（RSI 权重 60%，价格位置权重 40%）
        self.fear_greed_index = self.rsi * 0.6 + price_position * 0.4
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Optional[Signal]:
        """生成交易信号"""
        if idx < self.lookback:
            return None
        
        fg = self.fear_greed_index.iloc[idx]
        prev_fg = self.fear_greed_index.iloc[idx - 1]
        
        # 极度恐惧（买入机会）
        if fg < 25 and prev_fg < 25 and self.position == 0:
            return Signal(
                signal_type=SignalType.BUY,
                price=data.iloc[idx]["close"],
                strength=0.8,
                reason=f"极度恐惧 FGI={fg:.1f}"
            )
        
        # 极度贪婪（卖出信号）
        if self.position > 0 and fg > 75:
            return Signal(
                signal_type=SignalType.SELL,
                price=data.iloc[idx]["close"],
                strength=0.7,
                reason=f"极度贪婪 FGI={fg:.1f}"
            )
        
        return None


class OpenInterestStrategy(BaseStrategy):
    """
    开盘情绪策略
    
    基于开盘价和跳空缺口判断情绪：
    - 大幅高开 + 放量：情绪积极，买入
    - 大幅低开 + 放量：情绪消极，卖出
    """
    
    name = "开盘情绪策略"
    
    def __init__(self, gap_threshold: float = 0.02, vol_period: int = 20):
        """
        初始化策略
        
        Args:
            gap_threshold: 跳空阈值
            vol_period: 成交量均线周期
        """
        super().__init__()
        self.gap_threshold = gap_threshold
        self.vol_period = vol_period
        self.vol_ma = None
    
    def on_init(self, data: pd.DataFrame):
        """初始化指标"""
        self.vol_ma = data['vol'].rolling(window=self.vol_period).mean()
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Optional[Signal]:
        """生成交易信号"""
        if idx < self.vol_period:
            return None
        
        open_price = data.iloc[idx]["open"]
        prev_close = data.iloc[idx - 1]["close"]
        close = data.iloc[idx]["close"]
        vol = data.iloc[idx]["vol"]
        vol_avg = self.vol_ma.iloc[idx]
        
        # 跳空幅度
        gap = (open_price - prev_close) / prev_close
        vol_ratio = vol / vol_avg if vol_avg > 0 else 1.0
        
        # 大幅高开 + 放量 + 收阳
        if gap > self.gap_threshold and vol_ratio > 1.5 and close > open_price:
            if self.position == 0:
                return Signal(
                    signal_type=SignalType.BUY,
                    price=close,
                    strength=0.7,
                    reason=f"跳空高开 {gap:.1%} 量比{vol_ratio:.1f}"
                )
        
        # 大幅低开 + 放量 + 收阴
        if gap < -self.gap_threshold and vol_ratio > 1.5 and close < open_price:
            if self.position > 0:
                return Signal(
                    signal_type=SignalType.SELL,
                    price=close,
                    strength=0.6,
                    reason=f"跳空低开 {gap:.1%} 量比{vol_ratio:.1f}"
                )
        
        return None
