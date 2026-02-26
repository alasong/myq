"""
指标计算模块
提供高效的技术指标计算，支持缓存和向量化操作
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, Union
from functools import lru_cache
from dataclasses import dataclass


@dataclass
class IndicatorResult:
    """指标计算结果"""
    values: pd.Series
    metadata: dict = None


class IndicatorCache:
    """
    指标缓存
    
    使用 LRU 策略管理缓存，避免重复计算
    """
    
    def __init__(self, max_size: int = 1000):
        """
        初始化指标缓存
        
        Args:
            max_size: 最大缓存条目数
        """
        self._cache: Dict[str, IndicatorResult] = {}
        self._access_order = []
        self.max_size = max_size
    
    def _make_key(self, name: str, data_id: str, params: dict) -> str:
        """生成缓存键"""
        param_str = "_".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{name}:{data_id}:{param_str}"
    
    def get(self, key: str) -> Optional[IndicatorResult]:
        """获取缓存"""
        if key in self._cache:
            # 更新访问顺序
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        return None
    
    def set(self, key: str, result: IndicatorResult):
        """设置缓存"""
        if len(self._cache) >= self.max_size:
            # LRU 淘汰
            oldest = self._access_order.pop(0)
            del self._cache[oldest]
        
        self._cache[key] = result
        self._access_order.append(key)
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._access_order.clear()
    
    def stats(self) -> dict:
        """返回缓存统计"""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "memory_mb": sum(
                len(r.values) * 8 / 1024 / 1024 
                for r in self._cache.values()
            )
        }


class TechnicalIndicators:
    """
    技术指标计算器
    
    提供常用技术指标的高效计算，支持缓存
    """
    
    def __init__(self, cache: IndicatorCache = None):
        """
        初始化指标计算器
        
        Args:
            cache: 指标缓存实例
        """
        self.cache = cache or IndicatorCache()
    
    def _get_data_id(self, data: pd.DataFrame) -> str:
        """生成数据标识"""
        return f"{len(data)}_{data.index[0] if len(data) > 0 else 'empty'}"
    
    def sma(self, data: pd.DataFrame, column: str = "close", window: int = 20) -> pd.Series:
        """
        简单移动平均 (SMA)
        
        Args:
            data: 数据 DataFrame
            column: 列名
            window: 周期
            
        Returns:
            SMA 序列
        """
        key = self.cache._make_key("sma", self._get_data_id(data), {"column": column, "window": window})
        cached = self.cache.get(key)
        if cached:
            return cached.values
        
        result = data[column].rolling(window=window).mean()
        self.cache.set(key, IndicatorResult(values=result))
        return result
    
    def ema(self, data: pd.DataFrame, column: str = "close", window: int = 20) -> pd.Series:
        """
        指数移动平均 (EMA)
        
        Args:
            data: 数据 DataFrame
            column: 列名
            window: 周期
            
        Returns:
            EMA 序列
        """
        key = self.cache._make_key("ema", self._get_data_id(data), {"column": column, "window": window})
        cached = self.cache.get(key)
        if cached:
            return cached.values
        
        result = data[column].ewm(span=window, adjust=False).mean()
        self.cache.set(key, IndicatorResult(values=result))
        return result
    
    def macd(self, data: pd.DataFrame, column: str = "close", 
             fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """
        MACD 指标
        
        Args:
            data: 数据 DataFrame
            column: 列名
            fast: 快线周期
            slow: 慢线周期
            signal: 信号线周期
            
        Returns:
            包含 MACD/DIF/DEA/HIST 的字典
        """
        key = self.cache._make_key("macd", self._get_data_id(data), 
                                   {"column": column, "fast": fast, "slow": slow, "signal": signal})
        cached = self.cache.get(key)
        if cached:
            return cached.values
        
        ema_fast = data[column].ewm(span=fast, adjust=False).mean()
        ema_slow = data[column].ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        hist = 2 * (dif - dea)
        
        result = {
            "dif": dif,
            "dea": dea,
            "macd": hist
        }
        self.cache.set(key, IndicatorResult(values=pd.DataFrame(result)))
        return result
    
    def rsi(self, data: pd.DataFrame, column: str = "close", window: int = 14) -> pd.Series:
        """
        RSI 相对强弱指标
        
        Args:
            data: 数据 DataFrame
            column: 列名
            window: 周期
            
        Returns:
            RSI 序列
        """
        key = self.cache._make_key("rsi", self._get_data_id(data), {"column": column, "window": window})
        cached = self.cache.get(key)
        if cached:
            return cached.values
        
        delta = data[column].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=window).mean()
        avg_loss = loss.rolling(window=window).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        self.cache.set(key, IndicatorResult(values=rsi))
        return rsi
    
    def kdj(self, data: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> Dict[str, pd.Series]:
        """
        KDJ 指标
        
        Args:
            data: 数据 DataFrame
            n: RSV 计算周期
            m1: K 值平滑周期
            m2: D 值平滑周期
            
        Returns:
            包含 K/D/J 的字典
        """
        key = self.cache._make_key("kdj", self._get_data_id(data), {"n": n, "m1": m1, "m2": m2})
        cached = self.cache.get(key)
        if cached:
            return cached.values
        
        low_n = data["low"].rolling(window=n).min()
        high_n = data["high"].rolling(window=n).max()
        rsv = (data["close"] - low_n) / (high_n - low_n) * 100
        
        k = rsv.ewm(span=m1, adjust=False).mean()
        d = k.ewm(span=m2, adjust=False).mean()
        j = 3 * k - 2 * d
        
        result = {"k": k, "d": d, "j": j}
        self.cache.set(key, IndicatorResult(values=pd.DataFrame(result)))
        return result
    
    def boll(self, data: pd.DataFrame, column: str = "close", 
             window: int = 20, num_std: float = 2.0) -> Dict[str, pd.Series]:
        """
        布林带指标
        
        Args:
            data: 数据 DataFrame
            column: 列名
            window: 周期
            num_std: 标准差倍数
            
        Returns:
            包含 upper/middle/lower 的字典
        """
        key = self.cache._make_key("boll", self._get_data_id(data), 
                                   {"column": column, "window": window, "num_std": num_std})
        cached = self.cache.get(key)
        if cached:
            return cached.values
        
        middle = data[column].rolling(window=window).mean()
        std = data[column].rolling(window=window).std()
        upper = middle + num_std * std
        lower = middle - num_std * std
        
        result = {"upper": upper, "middle": middle, "lower": lower}
        self.cache.set(key, IndicatorResult(values=pd.DataFrame(result)))
        return result
    
    def atr(self, data: pd.DataFrame, window: int = 14) -> pd.Series:
        """
        平均真实波幅 (ATR)
        
        Args:
            data: 数据 DataFrame
            window: 周期
            
        Returns:
            ATR 序列
        """
        key = self.cache._make_key("atr", self._get_data_id(data), {"window": window})
        cached = self.cache.get(key)
        if cached:
            return cached.values
        
        high = data["high"]
        low = data["low"]
        close = data["close"].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(window=window).mean()
        self.cache.set(key, IndicatorResult(values=atr))
        return atr
    
    def dmi(self, data: pd.DataFrame, period: int = 14, adx_period: int = 14) -> Dict[str, pd.Series]:
        """
        DMI 趋向指标
        
        Args:
            data: 数据 DataFrame
            period: 计算周期
            adx_period: ADX 平滑周期
            
        Returns:
            包含 PDI/MDI/ADX 的字典
        """
        key = self.cache._make_key("dmi", self._get_data_id(data), 
                                   {"period": period, "adx_period": adx_period})
        cached = self.cache.get(key)
        if cached:
            return cached.values
        
        high = data["high"]
        low = data["low"]
        close = data["close"].shift(1)
        
        # 计算 +DM 和 -DM
        high_diff = high.diff()
        low_diff = -low.diff()
        
        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
        
        # 计算 TR
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # 平滑
        tr_smooth = tr.rolling(window=period).sum()
        plus_dm_smooth = plus_dm.rolling(window=period).sum()
        minus_dm_smooth = minus_dm.rolling(window=period).sum()
        
        # 计算 +DI 和 -DI
        plus_di = 100 * plus_dm_smooth / tr_smooth
        minus_di = 100 * minus_dm_smooth / tr_smooth
        
        # 计算 DX 和 ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(span=adx_period, adjust=False).mean()
        
        result = {"pdi": plus_di, "mdi": minus_di, "adx": adx}
        self.cache.set(key, IndicatorResult(values=pd.DataFrame(result)))
        return result
    
    def cci(self, data: pd.DataFrame, window: int = 14) -> pd.Series:
        """
        CCI 顺势指标
        
        Args:
            data: 数据 DataFrame
            window: 周期
            
        Returns:
            CCI 序列
        """
        key = self.cache._make_key("cci", self._get_data_id(data), {"window": window})
        cached = self.cache.get(key)
        if cached:
            return cached.values
        
        tp = (data["high"] + data["low"] + data["close"]) / 3
        tp_sma = tp.rolling(window=window).mean()
        tp_std = tp.rolling(window=window).std()
        
        cci = (tp - tp_sma) / (0.015 * tp_std)
        self.cache.set(key, IndicatorResult(values=cci))
        return cci
    
    def momentum(self, data: pd.DataFrame, column: str = "close", window: int = 20) -> pd.Series:
        """
        动量指标
        
        Args:
            data: 数据 DataFrame
            column: 列名
            window: 周期
            
        Returns:
            动量序列
        """
        key = self.cache._make_key("momentum", self._get_data_id(data), {"column": column, "window": window})
        cached = self.cache.get(key)
        if cached:
            return cached.values
        
        result = data[column].pct_change(periods=window)
        self.cache.set(key, IndicatorResult(values=result))
        return result
    
    def volume_ma(self, data: pd.DataFrame, window: int = 20) -> pd.Series:
        """
        成交量移动平均
        
        Args:
            data: 数据 DataFrame
            window: 周期
            
        Returns:
            成交量 MA 序列
        """
        key = self.cache._make_key("volume_ma", self._get_data_id(data), {"window": window})
        cached = self.cache.get(key)
        if cached:
            return cached.values
        
        result = data["vol"].rolling(window=window).mean()
        self.cache.set(key, IndicatorResult(values=result))
        return result
    
    def stats(self) -> dict:
        """返回缓存统计"""
        return self.cache.stats()


# 全局指标计算器实例
_global_indicators: Optional[TechnicalIndicators] = None


def get_indicators(cache: IndicatorCache = None) -> TechnicalIndicators:
    """获取全局指标计算器实例"""
    global _global_indicators
    if _global_indicators is None:
        _global_indicators = TechnicalIndicators(cache)
    return _global_indicators


def clear_indicator_cache():
    """清空全局指标缓存"""
    global _global_indicators
    if _global_indicators:
        _global_indicators.cache.clear()
