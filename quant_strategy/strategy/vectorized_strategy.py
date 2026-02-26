"""
向量化策略基类模块
支持高效的向量化信号生成
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .base_strategy import BaseStrategy, Signal, SignalType
from .indicators import TechnicalIndicators, get_indicators


@dataclass
class VectorizedSignal:
    """
    向量化交易信号
    
    Attributes:
        signal_types: 信号类型数组 (与数据索引对应)
        strengths: 信号强度数组
        reasons: 信号原因列表
    """
    signal_types: np.ndarray
    strengths: np.ndarray
    reasons: List[str] = None
    metadata: Dict = None


class VectorizedStrategy(BaseStrategy):
    """
    向量化策略基类
    
    与传统逐 bar 策略不同，向量化策略一次性处理所有数据，
    利用 numpy/pandas 的向量化操作大幅提升性能。
    
    使用方式：
    1. 继承此类并实现 generate_signals_vectorized() 方法
    2. 可选实现 generate_signal() 以支持逐 bar 模式（向后兼容）
    """
    
    def __init__(self, name: str = None, params: dict = None):
        """
        初始化向量化策略
        
        Args:
            name: 策略名称
            params: 策略参数
        """
        super().__init__(name, params)
        self.indicators: Optional[TechnicalIndicators] = None
        self._precomputed_signals: Optional[VectorizedSignal] = None
        self._signal_series: Optional[pd.Series] = None
    
    def set_indicators(self, indicators: TechnicalIndicators):
        """
        设置指标计算器
        
        Args:
            indicators: 指标计算器实例
        """
        self.indicators = indicators
    
    def get_indicators(self) -> TechnicalIndicators:
        """获取指标计算器"""
        if self.indicators is None:
            self.indicators = get_indicators()
        return self.indicators
    
    def precompute(self, data: pd.DataFrame):
        """
        预计算所有信号
        
        在回测开始前一次性计算所有信号，避免重复计算。
        
        Args:
            data: 历史数据
        """
        self._precomputed_signals = self.generate_signals_vectorized(data)
        self._build_signal_series(data)
    
    def _build_signal_series(self, data: pd.DataFrame):
        """
        构建信号序列
        
        将向量化信号转换为按索引访问的 Series
        
        Args:
            data: 历史数据
        """
        if self._precomputed_signals is None:
            return
        
        # 从预计算结果中获取信号和强度
        sigs = self._precomputed_signals.signal_types
        strengths = self._precomputed_signals.strengths
        
        # 创建信号映射
        signal_map = {
            'buy': 1,
            'sell': -1,
            'hold': 0
        }
        
        # 转换为数值数组
        signals = np.zeros(len(data), dtype=int)
        signal_strengths = np.full(len(data), 0.5)  # 默认强度
        
        for i in range(len(sigs)):
            sig_value = sigs[i]
            # 处理 SignalType 枚举和字符串
            if hasattr(sig_value, 'value'):
                sig_key = sig_value.value
            else:
                sig_key = str(sig_value)
            
            if sig_key in signal_map:
                signals[i] = signal_map[sig_key]
            
            if i < len(strengths) and not (isinstance(strengths[i], float) and np.isnan(strengths[i])):
                signal_strengths[i] = strengths[i]
        
        self._signal_series = pd.Series(signals, index=data.index)
        self._strength_series = pd.Series(signal_strengths, index=data.index)
    
    def generate_signal(self, data: pd.DataFrame, current_idx: int) -> Signal:
        """
        生成单个信号（使用预计算结果）
        
        Args:
            data: 历史数据
            current_idx: 当前 K 线索引
            
        Returns:
            交易信号
        """
        if self._precomputed_signals is None:
            # 如果没有预计算，回退到逐 bar 模式
            return self.generate_signal_bar(data, current_idx)
        
        if self._signal_series is None:
            self._build_signal_series(data)
        
        # 从预计算结果中获取信号
        signal_value = self._signal_series.iloc[current_idx]
        strength_value = self._strength_series.iloc[current_idx] if hasattr(self, '_strength_series') and self._strength_series is not None else 0.5
        
        if signal_value > 0:
            signal_type = SignalType.BUY
        elif signal_value < 0:
            signal_type = SignalType.SELL
        else:
            signal_type = SignalType.HOLD
        
        current_price = data.iloc[current_idx]["close"]
        
        # 获取原因
        reason = ""
        if self._precomputed_signals.reasons and current_idx < len(self._precomputed_signals.reasons):
            reason = self._precomputed_signals.reasons[current_idx]
        
        return Signal(
            signal_type=signal_type,
            price=current_price,
            strength=strength_value,
            reason=reason
        )
    
    def generate_signal_bar(self, data: pd.DataFrame, current_idx: int) -> Signal:
        """
        逐 bar 信号生成（向后兼容）
        
        子类可以实现此方法以支持逐 bar 模式
        
        Args:
            data: 历史数据
            current_idx: 当前 K 线索引
            
        Returns:
            交易信号
        """
        # 默认实现：如果没有预计算，返回持有信号
        return Signal(
            signal_type=SignalType.HOLD,
            price=data.iloc[current_idx]["close"],
            reason="未实现逐 bar 模式"
        )
    
    def generate_signals_vectorized(self, data: pd.DataFrame) -> VectorizedSignal:
        """
        向量化信号生成（必须实现）
        
        子类必须实现此方法，利用向量化操作一次性生成所有信号。
        
        Args:
            data: 历史数据 DataFrame
            
        Returns:
            VectorizedSignal: 向量化信号
        """
        raise NotImplementedError("子类必须实现 generate_signals_vectorized() 方法")
    
    def get_all_signals(self, data: pd.DataFrame) -> VectorizedSignal:
        """
        获取所有信号
        
        Args:
            data: 历史数据
            
        Returns:
            向量化信号
        """
        if self._precomputed_signals is None:
            self.precompute(data)
        return self._precomputed_signals
    
    def clear_cache(self):
        """清空预计算缓存"""
        self._precomputed_signals = None
        self._signal_series = None


class SignalGenerator:
    """
    信号生成器
    
    提供常用的信号生成辅助函数
    """
    
    @staticmethod
    def crossover(signal1: pd.Series, signal2: pd.Series) -> pd.Series:
        """
        检测金叉（上穿）
        
        Args:
            signal1: 信号 1
            signal2: 信号 2
            
        Returns:
            布尔 Series，True 表示发生金叉
        """
        above = signal1 > signal2
        was_below = above.shift(1) == False
        return above & was_below
    
    @staticmethod
    def crossunder(signal1: pd.Series, signal2: pd.Series) -> pd.Series:
        """
        检测死叉（下穿）
        
        Args:
            signal1: 信号 1
            signal2: 信号 2
            
        Returns:
            布尔 Series，True 表示发生死叉
        """
        below = signal1 < signal2
        was_above = below.shift(1) == False
        return below & was_above
    
    @staticmethod
    def threshold_breach(signal: pd.Series, threshold: float, direction: str = "above") -> pd.Series:
        """
        检测阈值突破
        
        Args:
            signal: 信号序列
            threshold: 阈值
            direction: "above" 或 "below"
            
        Returns:
            布尔 Series，True 表示突破阈值
        """
        if direction == "above":
            above = signal > threshold
            was_below = above.shift(1, fill_value=False) == False
            return above & was_below
        else:
            below = signal < threshold
            was_above = below.shift(1, fill_value=False) == False
            return below & was_above
    
    @staticmethod
    def generate_signal_array(
        conditions: Dict[SignalType, pd.Series],
        strengths: pd.Series = None,
        default: SignalType = SignalType.HOLD
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        根据条件生成信号数组
        
        Args:
            conditions: {信号类型：条件 Series}
            strengths: 信号强度 Series 或 ndarray
            default: 默认信号类型
            
        Returns:
            (signal_types, strengths) 元组
        """
        n = len(next(iter(conditions.values())))
        signals = np.full(n, default.value, dtype=object)
        
        if strengths is None:
            strength_values = np.full(n, 0.5)
        else:
            # 支持 Series 和 ndarray
            strength_values = strengths.values if hasattr(strengths, 'values') else strengths
        
        # 按优先级应用信号（BUY > SELL > HOLD）
        priority = [SignalType.BUY, SignalType.SELL, SignalType.HOLD]
        
        for sig_type in priority:
            if sig_type in conditions:
                mask = conditions[sig_type].values
                signals[mask] = sig_type.value
        
        return signals, strength_values
