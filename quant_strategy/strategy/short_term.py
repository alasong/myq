"""
短线交易策略模块
包含多种常用的短线交易策略
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

from .base_strategy import BaseStrategy, Signal, SignalType


class KDJStrategy(BaseStrategy):
    """
    KDJ 短线策略
    
    基于 KDJ 指标的超买超卖信号：
    - K 线上穿 D 线且 J<0：买入
    - K 线下穿 D 线且 J>100：卖出
    """
    
    name = "KDJ 短线策略"
    
    def __init__(self, n: int = 9, m1: int = 3, m2: int = 3, 
                 oversold: float = 20, overbought: float = 80):
        """
        初始化策略
        
        Args:
            n: KDJ 计算周期
            m1: K 值平滑周期
            m2: D 值平滑周期
            oversold: 超卖阈值
            overbought: 超买阈值
        """
        super().__init__()
        self.n = n
        self.m1 = m1
        self.m2 = m2
        self.oversold = oversold
        self.overbought = overbought
        self.prev_kdj = None
    
    def on_init(self, data: pd.DataFrame):
        """初始化指标"""
        self._calculate_kdj(data)
    
    def _calculate_kdj(self, data: pd.DataFrame):
        """计算 KDJ 指标"""
        low_min = data['low'].rolling(window=self.n).min()
        high_min = data['high'].rolling(window=self.n).max()
        rsv = (data['close'] - low_min) / (high_min - low_min) * 100
        
        self.kdj_k = rsv.rolling(window=self.m1).mean()
        self.kdj_d = self.kdj_k.rolling(window=self.m2).mean()
        self.kdj_j = 3 * self.kdj_k - 2 * self.kdj_d
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Optional[Signal]:
        """生成交易信号"""
        if idx < self.n + self.m1 + self.m2:
            return None
        
        k = self.kdj_k.iloc[idx]
        d = self.kdj_d.iloc[idx]
        j = self.kdj_j.iloc[idx]
        
        prev_k = self.kdj_k.iloc[idx - 1]
        prev_d = self.kdj_d.iloc[idx - 1]
        
        # 金叉买入：K 线上穿 D 线，且 J 值较低
        if prev_k <= prev_d and k > d and j < self.overbought:
            return Signal(
                signal_type=SignalType.BUY,
                price=data.iloc[idx]["close"],
                strength=0.8,
                reason=f"KDJ 金叉 K={k:.1f} D={d:.1f} J={j:.1f}"
            )
        
        # 死叉卖出：K 线下穿 D 线，且 J 值较高
        if self.position > 0 and prev_k >= prev_d and k < d and j > self.oversold:
            return Signal(
                signal_type=SignalType.SELL,
                price=data.iloc[idx]["close"],
                strength=0.8,
                reason=f"KDJ 死叉 K={k:.1f} D={d:.1f} J={j:.1f}"
            )
        
        return None


class RSIStrategy(BaseStrategy):
    """
    RSI 短线策略
    
    基于 RSI 指标的超买超卖信号：
    - RSI<30：超卖，买入
    - RSI>70：超买，卖出
    """
    
    name = "RSI 短线策略"
    
    def __init__(self, period: int = 6, oversold: float = 30, overbought: float = 70):
        """
        初始化策略
        
        Args:
            period: RSI 计算周期
            oversold: 超卖阈值
            overbought: 超买阈值
        """
        super().__init__()
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.rsi = None
    
    def on_init(self, data: pd.DataFrame):
        """初始化指标"""
        self._calculate_rsi(data)
    
    def _calculate_rsi(self, data: pd.DataFrame):
        """计算 RSI 指标"""
        delta = data['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=self.period).mean()
        avg_loss = loss.rolling(window=self.period).mean()
        
        rs = avg_gain / avg_loss
        self.rsi = 100 - (100 / (1 + rs))
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Optional[Signal]:
        """生成交易信号"""
        if idx < self.period + 1:
            return None
        
        rsi = self.rsi.iloc[idx]
        prev_rsi = self.rsi.iloc[idx - 1]
        
        # 超卖买入
        if prev_rsi < self.oversold and rsi >= self.oversold and self.position == 0:
            return Signal(
                signal_type=SignalType.BUY,
                price=data.iloc[idx]["close"],
                strength=0.7,
                reason=f"RSI 超卖回升 RSI={rsi:.1f}"
            )
        
        # 超买卖出
        if self.position > 0 and rsi > self.overbought:
            return Signal(
                signal_type=SignalType.SELL,
                price=data.iloc[idx]["close"],
                strength=0.7,
                reason=f"RSI 超买 RSI={rsi:.1f}"
            )
        
        return None


class BOLLStrategy(BaseStrategy):
    """
    布林线短线策略
    
    基于布林带的均值回归信号：
    - 价格触及下轨：买入
    - 价格触及上轨：卖出
    """
    
    name = "布林线策略"
    
    def __init__(self, period: int = 20, num_std: float = 2.0):
        """
        初始化策略
        
        Args:
            period: 均线周期
            num_std: 标准差倍数
        """
        super().__init__()
        self.period = period
        self.num_std = num_std
        self.boll_mid = None
        self.boll_upper = None
        self.boll_lower = None
    
    def on_init(self, data: pd.DataFrame):
        """初始化指标"""
        self._calculate_boll(data)
    
    def _calculate_boll(self, data: pd.DataFrame):
        """计算布林带"""
        self.boll_mid = data['close'].rolling(window=self.period).mean()
        std = data['close'].rolling(window=self.period).std()
        self.boll_upper = self.boll_mid + self.num_std * std
        self.boll_lower = self.boll_mid - self.num_std * std
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Optional[Signal]:
        """生成交易信号"""
        if idx < self.period:
            return None
        
        close = data.iloc[idx]["close"]
        upper = self.boll_upper.iloc[idx]
        lower = self.boll_lower.iloc[idx]
        mid = self.boll_mid.iloc[idx]
        
        # 触及下轨买入
        if close <= lower and self.position == 0:
            return Signal(
                signal_type=SignalType.BUY,
                price=close,
                strength=0.6,
                reason=f"触及布林下轨 close={close:.2f} lower={lower:.2f}"
            )
        
        # 触及上轨卖出
        if self.position > 0 and close >= upper:
            return Signal(
                signal_type=SignalType.SELL,
                price=close,
                strength=0.6,
                reason=f"触及布林上轨 close={close:.2f} upper={upper:.2f}"
            )
        
        # 回归中轨卖出
        if self.position > 0 and close >= mid:
            prev_close = data.iloc[idx - 1]["close"]
            if prev_close < mid:  # 从下向上穿越中轨
                return Signal(
                    signal_type=SignalType.SELL,
                    price=close,
                    strength=0.5,
                    reason=f"穿越布林中轨 close={close:.2f} mid={mid:.2f}"
                )
        
        return None


class DMIStrategy(BaseStrategy):
    """
    DMI 趋向指标策略
    
    基于 PDI、MDI、ADX 的趋势强度信号：
    - PDI 上穿 MDI 且 ADX 上升：买入
    - PDI 下穿 MDI 或 ADX 高位回落：卖出
    """
    
    name = "DMI 趋势策略"
    
    def __init__(self, period: int = 14, adx_period: int = 14):
        """
        初始化策略
        
        Args:
            period: DMI 计算周期
            adx_period: ADX 平滑周期
        """
        super().__init__()
        self.period = period
        self.adx_period = adx_period
        self.pdi = None
        self.mdi = None
        self.adx = None
    
    def on_init(self, data: pd.DataFrame):
        """初始化指标"""
        self._calculate_dmi(data)
    
    def _calculate_dmi(self, data: pd.DataFrame):
        """计算 DMI 指标"""
        high = data['high']
        low = data['low']
        close = data['close']
        
        # 计算 TR
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.period).mean()
        
        # 计算 DM
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)
        
        # 计算 DMI
        self.pdi = 100 * (plus_dm.rolling(window=self.period).mean() / atr)
        self.mdi = 100 * (minus_dm.rolling(window=self.period).mean() / atr)
        
        # 计算 ADX
        dx = 100 * abs(self.pdi - self.mdi) / (self.pdi + self.mdi)
        self.adx = dx.rolling(window=self.adx_period).mean()
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Optional[Signal]:
        """生成交易信号"""
        if idx < self.period + self.adx_period:
            return None
        
        pdi = self.pdi.iloc[idx]
        mdi = self.mdi.iloc[idx]
        adx = self.adx.iloc[idx]
        
        prev_pdi = self.pdi.iloc[idx - 1]
        prev_mdi = self.mdi.iloc[idx - 1]
        prev_adx = self.adx.iloc[idx - 1]
        
        # 金叉买入：PDI 上穿 MDI，ADX 上升
        if prev_pdi <= prev_mdi and pdi > mdi and adx > prev_adx and self.position == 0:
            return Signal(
                signal_type=SignalType.BUY,
                price=data.iloc[idx]["close"],
                strength=0.7,
                reason=f"DMI 金叉 PDI={pdi:.1f} MDI={mdi:.1f} ADX={adx:.1f}"
            )
        
        # 死叉卖出：PDI 下穿 MDI
        if self.position > 0 and prev_pdi >= prev_mdi and pdi < mdi:
            return Signal(
                signal_type=SignalType.SELL,
                price=data.iloc[idx]["close"],
                strength=0.7,
                reason=f"DMI 死叉 PDI={pdi:.1f} MDI={mdi:.1f}"
            )
        
        return None


class CCIStrategy(BaseStrategy):
    """
    CCI 顺势指标策略
    
    基于 CCI 指标的超买超卖信号：
    - CCI<-100：超卖，买入
    - CCI>+100：超买，卖出
    """
    
    name = "CCI 顺势策略"
    
    def __init__(self, period: int = 14, oversold: float = -100, overbought: float = 100):
        """
        初始化策略
        
        Args:
            period: CCI 计算周期
            oversold: 超卖阈值
            overbought: 超买阈值
        """
        super().__init__()
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.cci = None
    
    def on_init(self, data: pd.DataFrame):
        """初始化指标"""
        self._calculate_cci(data)
    
    def _calculate_cci(self, data: pd.DataFrame):
        """计算 CCI 指标"""
        tp = (data['high'] + data['low'] + data['close']) / 3
        sma = tp.rolling(window=self.period).mean()
        mad = tp.rolling(window=self.period).apply(lambda x: abs(x - x.mean()).mean())
        self.cci = (tp - sma) / (0.015 * mad)
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Optional[Signal]:
        """生成交易信号"""
        if idx < self.period:
            return None
        
        cci = self.cci.iloc[idx]
        prev_cci = self.cci.iloc[idx - 1]
        
        # 超卖买入
        if prev_cci < self.oversold and cci >= self.oversold and self.position == 0:
            return Signal(
                signal_type=SignalType.BUY,
                price=data.iloc[idx]["close"],
                strength=0.6,
                reason=f"CCI 超卖回升 CCI={cci:.1f}"
            )
        
        # 超买卖出
        if self.position > 0 and cci > self.overbought:
            return Signal(
                signal_type=SignalType.SELL,
                price=data.iloc[idx]["close"],
                strength=0.6,
                reason=f"CCI 超买 CCI={cci:.1f}"
            )
        
        return None


class MACDStrategy(BaseStrategy):
    """
    MACD 短线策略
    
    基于 MACD 金叉死叉信号：
    - DIF 上穿 DEA：买入
    - DIF 下穿 DEA：卖出
    """
    
    name = "MACD 策略"
    
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        """
        初始化策略
        
        Args:
            fast: 快线周期
            slow: 慢线周期
            signal: 信号线周期
        """
        super().__init__()
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self.dif = None
        self.dea = None
        self.macd = None
    
    def on_init(self, data: pd.DataFrame):
        """初始化指标"""
        self._calculate_macd(data)
    
    def _calculate_macd(self, data: pd.DataFrame):
        """计算 MACD 指标"""
        exp1 = data['close'].ewm(span=self.fast, adjust=False).mean()
        exp2 = data['close'].ewm(span=self.slow, adjust=False).mean()
        self.dif = exp1 - exp2
        self.dea = self.dif.ewm(span=self.signal, adjust=False).mean()
        self.macd = 2 * (self.dif - self.dea)
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Optional[Signal]:
        """生成交易信号"""
        if idx < self.slow + self.signal:
            return None
        
        dif = self.dif.iloc[idx]
        dea = self.dea.iloc[idx]
        prev_dif = self.dif.iloc[idx - 1]
        prev_dea = self.dea.iloc[idx - 1]
        
        # 金叉买入
        if prev_dif <= prev_dea and dif > dea and self.position == 0:
            return Signal(
                signal_type=SignalType.BUY,
                price=data.iloc[idx]["close"],
                strength=0.7,
                reason=f"MACD 金叉 DIF={dif:.3f} DEA={dea:.3f}"
            )
        
        # 死叉卖出
        if self.position > 0 and prev_dif >= prev_dea and dif < dea:
            return Signal(
                signal_type=SignalType.SELL,
                price=data.iloc[idx]["close"],
                strength=0.7,
                reason=f"MACD 死叉 DIF={dif:.3f} DEA={dea:.3f}"
            )
        
        return None


class VolumePriceStrategy(BaseStrategy):
    """
    量价策略
    
    基于成交量和价格的配合：
    - 放量上涨：买入
    - 缩量下跌：卖出
    """
    
    name = "量价策略"
    
    def __init__(self, vol_period: int = 5, price_period: int = 10,
                 vol_ratio: float = 1.5, price_change: float = 0.03):
        """
        初始化策略
        
        Args:
            vol_period: 成交量均线周期
            price_period: 价格均线周期
            vol_ratio: 放量倍数
            price_change: 价格变化阈值
        """
        super().__init__()
        self.vol_period = vol_period
        self.price_period = price_period
        self.vol_ratio = vol_ratio
        self.price_change = price_change
        self.vol_ma = None
        self.price_ma = None
    
    def on_init(self, data: pd.DataFrame):
        """初始化指标"""
        self.vol_ma = data['vol'].rolling(window=self.vol_period).mean()
        self.price_ma = data['close'].rolling(window=self.price_period).mean()
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Optional[Signal]:
        """生成交易信号"""
        if idx < max(self.vol_period, self.price_period):
            return None
        
        close = data.iloc[idx]["close"]
        vol = data.iloc[idx]["vol"]
        prev_close = data.iloc[idx - 1]["close"]
        
        vol_avg = self.vol_ma.iloc[idx]
        
        # 放量上涨买入
        price_pct = (close - prev_close) / prev_close
        vol_ratio = vol / vol_avg if vol_avg > 0 else 0
        
        if price_pct > self.price_change and vol_ratio > self.vol_ratio and self.position == 0:
            return Signal(
                signal_type=SignalType.BUY,
                price=close,
                strength=0.6,
                reason=f"放量上涨 {price_pct:.1%} 量比{vol_ratio:.1f}"
            )
        
        # 高位缩量卖出
        if self.position > 0:
            if close > self.price_ma.iloc[idx] * 1.2 and vol_ratio < 0.8:
                return Signal(
                    signal_type=SignalType.SELL,
                    price=close,
                    strength=0.5,
                    reason=f"高位缩量 量比{vol_ratio:.1f}"
                )
        
        return None
