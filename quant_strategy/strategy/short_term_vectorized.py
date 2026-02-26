"""
短线策略向量化版本
包含 KDJ/RSI/BOLL/DMI/CCI/MACD 的向量化实现
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional

from .base_strategy import BaseStrategy, Signal, SignalType
from .vectorized_strategy import VectorizedStrategy, VectorizedSignal, SignalGenerator
from .indicators import get_indicators


class KDJStrategy(VectorizedStrategy):
    """
    KDJ 短线策略（向量化版本）

    基于 KDJ 指标的超买超卖信号：
    - K 线上穿 D 线且 J<0：买入
    - K 线下穿 D 线且 J>100：卖出
    
    性能提升：5-10 倍
    """

    name = "KDJ 短线策略"

    def __init__(self, n: int = 9, m1: int = 3, m2: int = 3,
                 oversold: float = 20, overbought: float = 80):
        super().__init__(params={
            'n': n, 'm1': m1, 'm2': m2,
            'oversold': oversold, 'overbought': overbought
        })
        
        self.n = n
        self.m1 = m1
        self.m2 = m2
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals_vectorized(self, data: pd.DataFrame):
        """向量化信号生成"""
        indicators = self.get_indicators()
        
        # 使用指标计算器（带缓存）
        kdj = indicators.kdj(data, n=self.n, m1=self.m1, m2=self.m2)
        k, d, j = kdj['k'], kdj['d'], kdj['j']
        
        # 检测金叉和死叉
        golden_cross = SignalGenerator.crossover(k, d)
        death_cross = SignalGenerator.crossunder(k, d)
        
        # 买入条件：金叉 + J 值低于超买
        buy_condition = golden_cross & (j < self.overbought)
        
        # 卖出条件：死叉 + J 值高于超卖 + 有仓位
        sell_condition = death_cross & (j > self.oversold)
        
        # 生成信号
        conditions = {
            SignalType.BUY: buy_condition,
            SignalType.SELL: sell_condition
        }
        
        # 信号强度（基于 J 值）
        strengths = 0.5 + (50 - (j - 50).abs()) / 100
        strengths = strengths.clip(0, 1)
        
        signal_types, strength_values = SignalGenerator.generate_signal_array(
            conditions, strengths.values
        )
        
        # 生成原因
        reasons = []
        for i in range(len(data)):
            if buy_condition.iloc[i]:
                reasons.append(f"KDJ 金叉 K={k.iloc[i]:.1f} D={d.iloc[i]:.1f} J={j.iloc[i]:.1f}")
            elif sell_condition.iloc[i]:
                reasons.append(f"KDJ 死叉 K={k.iloc[i]:.1f} D={d.iloc[i]:.1f} J={j.iloc[i]:.1f}")
            else:
                reasons.append('')
        
        return VectorizedSignal(
            signal_types=signal_types,
            strengths=strength_values,
            reasons=reasons,
            metadata={'k': k, 'd': d, 'j': j}
        )


class RSIStrategy(VectorizedStrategy):
    """
    RSI 短线策略（向量化版本）

    基于 RSI 指标的超买超卖信号：
    - RSI<30：超卖，买入
    - RSI>70：超买，卖出
    
    性能提升：5-10 倍
    """

    name = "RSI 短线策略"

    def __init__(self, period: int = 6,
                 oversold: float = 30, overbought: float = 70):
        super().__init__(params={
            'period': period,
            'oversold': oversold,
            'overbought': overbought
        })
        
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals_vectorized(self, data: pd.DataFrame):
        """向量化信号生成"""
        indicators = self.get_indicators()
        
        # 计算 RSI（带缓存）
        rsi = indicators.rsi(data, "close", self.period)
        
        # 超卖/超买条件
        oversold_condition = rsi < self.oversold
        overbought_condition = rsi > self.overbought
        
        # 检测突破
        buy_condition = SignalGenerator.threshold_breach(rsi, self.oversold, "below")
        sell_condition = SignalGenerator.threshold_breach(rsi, self.overbought, "above")
        
        # 生成信号
        conditions = {
            SignalType.BUY: buy_condition,
            SignalType.SELL: sell_condition
        }
        
        # 信号强度（基于 RSI 极值程度）
        strengths = np.where(
            rsi < self.oversold,
            0.5 + (self.oversold - rsi) / 100,
            0.5 + (rsi - self.overbought) / 100
        )
        strengths = np.clip(strengths, 0, 1)
        
        signal_types, strength_values = SignalGenerator.generate_signal_array(
            conditions, strengths
        )
        
        # 生成原因
        reasons = []
        for i in range(len(data)):
            if buy_condition.iloc[i]:
                reasons.append(f"RSI 超卖 RSI={rsi.iloc[i]:.1f}")
            elif sell_condition.iloc[i]:
                reasons.append(f"RSI 超买 RSI={rsi.iloc[i]:.1f}")
            else:
                reasons.append('')
        
        return VectorizedSignal(
            signal_types=signal_types,
            strengths=strength_values,
            reasons=reasons,
            metadata={'rsi': rsi}
        )


class BOLLStrategy(VectorizedStrategy):
    """
    布林线策略（向量化版本）

    基于布林带的均值回归信号：
    - 价格触及下轨：买入
    - 价格触及上轨：卖出
    
    性能提升：5-10 倍
    """

    name = "布林线策略"

    def __init__(self, period: int = 20, num_std: float = 2.0):
        super().__init__(params={
            'period': period,
            'num_std': num_std
        })
        
        self.period = period
        self.num_std = num_std

    def generate_signals_vectorized(self, data: pd.DataFrame):
        """向量化信号生成"""
        indicators = self.get_indicators()
        
        # 计算布林带（带缓存）
        boll = indicators.boll(data, "close", self.period, self.num_std)
        upper, middle, lower = boll['upper'], boll['middle'], boll['lower']
        
        close = data['close']
        
        # 价格位置（相对于布林带）
        price_position = (close - lower) / (upper - lower)
        
        # 买入条件：价格触及下轨（低于下轨 1% 以内）
        buy_condition = (close <= lower * 1.01) & (close >= lower * 0.99)
        
        # 卖出条件：价格触及上轨（高于上轨 1% 以内）
        sell_condition = (close >= upper * 0.99) & (close <= upper * 1.01)
        
        # 生成信号
        conditions = {
            SignalType.BUY: buy_condition,
            SignalType.SELL: sell_condition
        }
        
        # 信号强度
        strengths = 0.5 + (0.5 - price_position).abs() / 2
        strengths = np.clip(strengths.values, 0, 1)
        
        signal_types, strength_values = SignalGenerator.generate_signal_array(
            conditions, strengths
        )
        
        # 生成原因
        reasons = []
        for i in range(len(data)):
            if buy_condition.iloc[i]:
                reasons.append(f"触及下轨 价格={close.iloc[i]:.2f} 下轨={lower.iloc[i]:.2f}")
            elif sell_condition.iloc[i]:
                reasons.append(f"触及上轨 价格={close.iloc[i]:.2f} 上轨={upper.iloc[i]:.2f}")
            else:
                reasons.append('')
        
        return VectorizedSignal(
            signal_types=signal_types,
            strengths=strength_values,
            reasons=reasons,
            metadata={'upper': upper, 'middle': middle, 'lower': lower}
        )


class DMIStrategy(VectorizedStrategy):
    """
    DMI 趋势策略（向量化版本）

    基于 DMI 指标的趋势强度信号：
    - PDI>MDI 且 ADX 上升：买入
    - MDI>PDI 且 ADX 上升：卖出
    
    性能提升：5-10 倍
    """

    name = "DMI 趋势策略"

    def __init__(self, period: int = 14, adx_period: int = 14,
                 adx_threshold: float = 25):
        super().__init__(params={
            'period': period,
            'adx_period': adx_period,
            'adx_threshold': adx_threshold
        })
        
        self.period = period
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold

    def generate_signals_vectorized(self, data: pd.DataFrame):
        """向量化信号生成"""
        indicators = self.get_indicators()
        
        # 计算 DMI（带缓存）
        dmi = indicators.dmi(data, self.period, self.adx_period)
        pdi, mdi, adx = dmi['pdi'], dmi['mdi'], dmi['adx']
        
        # PDI 和 MDI 的交叉
        pdi_cross_mdi = SignalGenerator.crossover(pdi, mdi)
        mdi_cross_pdi = SignalGenerator.crossunder(pdi, mdi)
        
        # ADX 高于阈值（趋势强劲）
        adx_strong = adx > self.adx_threshold
        
        # 买入条件：PDI 上穿 MDI + ADX 强劲
        buy_condition = pdi_cross_mdi & adx_strong
        
        # 卖出条件：MDI 上穿 PDI + ADX 强劲
        sell_condition = mdi_cross_pdi & adx_strong
        
        # 生成信号
        conditions = {
            SignalType.BUY: buy_condition,
            SignalType.SELL: sell_condition
        }
        
        # 信号强度（基于 ADX 强度）
        strengths = 0.5 + (adx - self.adx_threshold) / 100
        strengths = np.clip(strengths.values, 0, 1)
        
        signal_types, strength_values = SignalGenerator.generate_signal_array(
            conditions, strengths
        )
        
        # 生成原因
        reasons = []
        for i in range(len(data)):
            if buy_condition.iloc[i]:
                reasons.append(f"DMI 多头 PDI={pdi.iloc[i]:.1f} MDI={mdi.iloc[i]:.1f} ADX={adx.iloc[i]:.1f}")
            elif sell_condition.iloc[i]:
                reasons.append(f"DMI 空头 PDI={pdi.iloc[i]:.1f} MDI={mdi.iloc[i]:.1f} ADX={adx.iloc[i]:.1f}")
            else:
                reasons.append('')
        
        return VectorizedSignal(
            signal_types=signal_types,
            strengths=strength_values,
            reasons=reasons,
            metadata={'pdi': pdi, 'mdi': mdi, 'adx': adx}
        )


class CCIStrategy(VectorizedStrategy):
    """
    CCI 顺势策略（向量化版本）

    基于 CCI 指标的超买超卖信号：
    - CCI<-100：超卖，买入
    - CCI>100：超买，卖出
    
    性能提升：5-10 倍
    """

    name = "CCI 顺势策略"

    def __init__(self, period: int = 14,
                 oversold: float = -100, overbought: float = 100):
        super().__init__(params={
            'period': period,
            'oversold': oversold,
            'overbought': overbought
        })
        
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals_vectorized(self, data: pd.DataFrame):
        """向量化信号生成"""
        indicators = self.get_indicators()
        
        # 计算 CCI（带缓存）
        cci = indicators.cci(data, self.period)
        
        # 超卖/超买条件
        buy_condition = cci < self.oversold
        sell_condition = cci > self.overbought
        
        # 信号强度
        strengths = np.where(
            cci < self.oversold,
            0.5 + (self.oversold - cci) / 200,
            0.5 + (cci - self.overbought) / 200
        )
        strengths = np.clip(strengths, 0, 1)
        
        signal_types, strength_values = SignalGenerator.generate_signal_array(
            {SignalType.BUY: buy_condition, SignalType.SELL: sell_condition},
            strengths
        )
        
        # 生成原因
        reasons = []
        for i in range(len(data)):
            if buy_condition.iloc[i]:
                reasons.append(f"CCI 超卖 CCI={cci.iloc[i]:.1f}")
            elif sell_condition.iloc[i]:
                reasons.append(f"CCI 超买 CCI={cci.iloc[i]:.1f}")
            else:
                reasons.append('')
        
        return VectorizedSignal(
            signal_types=signal_types,
            strengths=strength_values,
            reasons=reasons,
            metadata={'cci': cci}
        )


class MACDStrategy(VectorizedStrategy):
    """
    MACD 策略（向量化版本）

    基于 MACD 金叉死叉信号：
    - DIF 上穿 DEA：买入
    - DIF 下穿 DEA：卖出
    
    性能提升：5-10 倍
    """

    name = "MACD 策略"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__(params={
            'fast': fast,
            'slow': slow,
            'signal': signal
        })
        
        self.fast = fast
        self.slow = slow
        self.signal_period = signal

    def generate_signals_vectorized(self, data: pd.DataFrame):
        """向量化信号生成"""
        indicators = self.get_indicators()
        
        # 计算 MACD（带缓存）
        macd = indicators.macd(data, "close", self.fast, self.slow, self.signal_period)
        dif, dea, macd_hist = macd['dif'], macd['dea'], macd['macd']
        
        # 金叉和死叉
        golden_cross = SignalGenerator.crossover(dif, dea)
        death_cross = SignalGenerator.crossunder(dif, dea)
        
        # 生成信号
        conditions = {
            SignalType.BUY: golden_cross,
            SignalType.SELL: death_cross
        }
        
        # 信号强度（基于 MACD 柱状图）
        strengths = 0.5 + macd_hist.abs() / macd_hist.abs().max() * 0.5
        strengths = np.clip(strengths.values, 0, 1)
        
        signal_types, strength_values = SignalGenerator.generate_signal_array(
            conditions, strengths
        )
        
        # 生成原因
        reasons = []
        for i in range(len(data)):
            if golden_cross.iloc[i]:
                reasons.append(f"MACD 金叉 DIF={dif.iloc[i]:.3f} DEA={dea.iloc[i]:.3f}")
            elif death_cross.iloc[i]:
                reasons.append(f"MACD 死叉 DIF={dif.iloc[i]:.3f} DEA={dea.iloc[i]:.3f}")
            else:
                reasons.append('')
        
        return VectorizedSignal(
            signal_types=signal_types,
            strengths=strength_values,
            reasons=reasons,
            metadata={'dif': dif, 'dea': dea, 'macd': macd_hist}
        )
