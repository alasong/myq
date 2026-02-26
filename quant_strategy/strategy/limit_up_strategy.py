"""
打板策略模块
支持首板、连板、涨停回马枪等策略
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .base_strategy import BaseStrategy, Signal, SignalType
from .vectorized_strategy import VectorizedStrategy, SignalGenerator


@dataclass
class LimitUpInfo:
    """涨停信息"""
    ts_code: str
    date: str
    continuous_days: int  # 连板天数
    is_first: bool        # 是否首板
    quality_score: float  # 质量评分
    open_pct: float       # 开盘涨幅
    volume_ratio: float   # 量比


class FirstLimitUpStrategy(VectorizedStrategy):
    """
    首板打板策略
    
    核心逻辑：
    1. 识别首次涨停股票（前 10 天无涨停）
    2. 分析涨停质量（封板时间、成交量、市值）
    3. 次日高开时买入
    4. 快进快出（1-3 天），设置止盈止损
    
    适用场景：
    - 强势股市场
    - 题材炒作初期
    - 涨停板较多的交易日
    """
    
    def __init__(self,
                 min_close_ratio: float = 0.095,   # 涨停阈值（9.5%）
                 min_volume_ratio: float = 1.5,    # 最小放量倍数
                 min_market_cap: float = 30,       # 最小市值（亿）
                 max_market_cap: float = 500,      # 最大市值（亿）
                 exclude_st: bool = True,          # 排除 ST
                 hold_days: int = 3,               # 最大持有期
                 stop_loss: float = 0.05,          # 止损线（5%）
                 take_profit: float = 0.15,        # 止盈线（15%）
                 min_open_pct: float = 0.01,       # 最小高开幅度（1%）
                 quality_threshold: float = 0.6):  # 质量评分阈值
        """
        初始化首板打板策略
        
        Args:
            min_close_ratio: 涨停判定阈值
            min_volume_ratio: 成交量放大倍数
            min_market_cap: 最小市值（亿）
            max_market_cap: 最大市值（亿）
            exclude_st: 是否排除 ST 股票
            hold_days: 最大持有天数
            stop_loss: 止损比例
            take_profit: 止盈比例
            min_open_pct: 次日最小高开幅度
            quality_threshold: 涨停质量评分阈值
        """
        super().__init__(params={
            'min_close_ratio': min_close_ratio,
            'min_volume_ratio': min_volume_ratio,
            'min_market_cap': min_market_cap,
            'max_market_cap': max_market_cap,
            'exclude_st': exclude_st,
            'hold_days': hold_days,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'min_open_pct': min_open_pct,
            'quality_threshold': quality_threshold
        })
        
        self.min_close_ratio = min_close_ratio
        self.min_volume_ratio = min_volume_ratio
        self.min_market_cap = min_market_cap
        self.max_market_cap = max_market_cap
        self.exclude_st = exclude_st
        self.hold_days = hold_days
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.min_open_pct = min_open_pct
        self.quality_threshold = quality_threshold
        
        # 状态跟踪
        self.limit_up_stocks = set()
        self.holding_days = 0
        self.entry_price = 0.0
        self.entry_date = None
    
    def is_limit_up(self, data: pd.DataFrame, idx: int) -> Tuple[bool, float]:
        """
        判断是否涨停
        
        Returns:
            (是否涨停，涨停幅度)
        """
        if idx < 1:
            return False, 0.0
        
        close = data.iloc[idx]['close']
        prev_close = data.iloc[idx-1]['close']
        pct = (close - prev_close) / prev_close
        
        return pct >= self.min_close_ratio, pct
    
    def is_first_limit_up(self, data: pd.DataFrame, idx: int, lookback: int = 10) -> bool:
        """
        判断是否为首板（前 lookback 天内无涨停）
        """
        start_idx = max(0, idx - lookback)
        
        for i in range(start_idx, idx):
            is_lu, _ = self.is_limit_up(data, i)
            if is_lu:
                return False
        return True
    
    def check_volume(self, data: pd.DataFrame, idx: int) -> Tuple[bool, float]:
        """
        检查成交量是否放量
        
        Returns:
            (是否放量，量比)
        """
        current_vol = data.iloc[idx]['vol']
        
        # 计算前 5 日平均成交量
        if idx >= 5:
            avg_vol = data.iloc[idx-5:idx]['vol'].mean()
        else:
            avg_vol = current_vol
        
        volume_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
        return volume_ratio >= self.min_volume_ratio, volume_ratio
    
    def quality_score(self, data: pd.DataFrame, idx: int) -> float:
        """
        涨停质量评分（0-1）
        
        评分维度：
        - 涨停幅度（20% 优于 10%）
        - 成交量（适度放量 1.5-5 倍）
        - 收盘价位置（接近最高价）
        """
        score = 0.5
        
        # 涨停幅度评分
        _, pct = self.is_limit_up(data, idx)
        if pct >= 0.19:  # 20% 涨停（创业板/科创板）
            score += 0.2
        elif pct >= 0.095:  # 10% 涨停
            score += 0.1
        
        # 成交量评分
        is_vol, vol_ratio = self.check_volume(data, idx)
        if is_vol:
            if 1.5 <= vol_ratio <= 5:
                score += 0.2
            elif vol_ratio > 5:
                score += 0.05  # 过度放量扣分
        
        # 收盘价位置评分（接近最高价说明封板坚决）
        high = data.iloc[idx]['high']
        close = data.iloc[idx]['close']
        if close >= high * 0.99:  # 收盘价接近最高价
            score += 0.1
        
        return min(score, 1.0)
    
    def generate_signals_vectorized(self, data: pd.DataFrame):
        """向量化信号生成"""
        n = len(data)
        signals = np.full(n, SignalType.HOLD.value, dtype=object)
        strengths = np.full(n, 0.5)
        reasons = [''] * n
        
        # 遍历识别首板
        for i in range(1, n):
            is_lu, lu_pct = self.is_limit_up(data, i)
            
            if is_lu:
                # 检查是否首板
                if self.is_first_limit_up(data, i):
                    # 检查成交量
                    is_vol, vol_ratio = self.check_volume(data, i)
                    
                    if is_vol:
                        # 计算质量评分
                        quality = self.quality_score(data, i)
                        
                        if quality >= self.quality_threshold:
                            # 次日买入信号
                            if i + 1 < n:
                                signals[i+1] = SignalType.BUY.value
                                strengths[i+1] = quality
                                reasons[i+1] = f"首板质量={quality:.2f}, 量比={vol_ratio:.1f}"
        
        from .vectorized_strategy import VectorizedSignal
        return VectorizedSignal(
            signal_types=signals,
            strengths=strengths,
            reasons=reasons,
            metadata={
                'limit_up_dates': np.where(signals == SignalType.BUY.value)[0]
            }
        )
    
    def generate_signal_bar(self, data: pd.DataFrame, idx: int) -> Signal:
        """
        逐 bar 模式信号生成
        
        支持完整的打板逻辑：
        1. 识别首板
        2. 次日高开买入
        3. 止盈止损
        """
        current_price = data.iloc[idx]['close']
        
        # 持有时检查止盈止损
        if self.position > 0:
            self.holding_days += 1
            
            # 止损检查
            pnl_pct = (current_price - self.entry_price) / self.entry_price
            
            if pnl_pct <= -self.stop_loss:
                self.holding_days = 0
                self.position = 0
                return Signal(
                    signal_type=SignalType.SELL,
                    price=current_price,
                    strength=1.0,
                    reason=f"止损 ({pnl_pct:.2%})"
                )
            
            # 止盈检查
            if pnl_pct >= self.take_profit:
                self.holding_days = 0
                self.position = 0
                return Signal(
                    signal_type=SignalType.SELL,
                    price=current_price,
                    strength=1.0,
                    reason=f"止盈 ({pnl_pct:.2%})"
                )
            
            # 持有到期
            if self.holding_days >= self.hold_days:
                self.holding_days = 0
                self.position = 0
                return Signal(
                    signal_type=SignalType.SELL,
                    price=current_price,
                    reason="持有到期"
                )
            
            return Signal(
                signal_type=SignalType.HOLD,
                price=current_price,
                reason=f"持有第{self.holding_days}天"
            )
        
        # 空仓时寻找买入机会
        if idx < 2:
            return Signal(SignalType.HOLD, current_price, "数据不足")
        
        # 检查昨日是否首板
        is_lu, lu_pct = self.is_limit_up(data, idx-1)
        
        if is_lu and self.is_first_limit_up(data, idx-1):
            is_vol, vol_ratio = self.check_volume(data, idx-1)
            
            if is_vol:
                quality = self.quality_score(data, idx-1)
                
                if quality >= self.quality_threshold:
                    # 检查今日是否高开
                    open_price = data.iloc[idx]['open']
                    prev_close = data.iloc[idx-1]['close']
                    open_pct = (open_price - prev_close) / prev_close
                    
                    if open_pct >= self.min_open_pct:
                        self.entry_price = open_price
                        self.entry_date = idx
                        self.holding_days = 0
                        
                        return Signal(
                            signal_type=SignalType.BUY,
                            price=open_price,
                            strength=quality,
                            reason=f"首板高开{open_pct:.2%}, 质量={quality:.2f}"
                        )
        
        return Signal(SignalType.HOLD, current_price, "等待机会")
    
    def get_params_description(self) -> Dict[str, dict]:
        """返回参数说明"""
        return {
            'min_close_ratio': {
                'type': float,
                'default': 0.095,
                'range': (0.08, 0.20),
                'description': '涨停判定阈值'
            },
            'min_volume_ratio': {
                'type': float,
                'default': 1.5,
                'range': (1.0, 5.0),
                'description': '最小放量倍数'
            },
            'hold_days': {
                'type': int,
                'default': 3,
                'range': (1, 10),
                'description': '最大持有天数'
            },
            'stop_loss': {
                'type': float,
                'default': 0.05,
                'range': (0.03, 0.15),
                'description': '止损比例'
            },
            'take_profit': {
                'type': float,
                'default': 0.15,
                'range': (0.05, 0.30),
                'description': '止盈比例'
            }
        }


class ContinuousLimitUpStrategy(BaseStrategy):
    """
    连板打板策略
    
    核心逻辑：
    1. 识别 N 连板股票
    2. 在 N 板时打板买入
    3. 持有至开板或达到目标收益
    
    适用场景：
    - 强势龙头股
    - 题材炒作高潮期
    - 市场情绪高涨
    """
    
    name = "连板打板策略"
    
    def __init__(self,
                 target_continuous: int = 2,     # 目标连板数
                 max_hold_days: int = 5,         # 最大持有期
                 stop_loss: float = 0.08,        # 止损线
                 take_profit: float = 0.20,      # 止盈线
                 min_close_ratio: float = 0.095):# 涨停阈值
        super().__init__(params={
            'target_continuous': target_continuous,
            'max_hold_days': max_hold_days,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'min_close_ratio': min_close_ratio
        })
        
        self.target_continuous = target_continuous
        self.max_hold_days = max_hold_days
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.min_close_ratio = min_close_ratio
        
        # 状态
        self.holding_days = 0
        self.entry_price = 0.0
    
    def count_continuous_limit_up(self, data: pd.DataFrame, idx: int) -> int:
        """计算连续涨停天数"""
        count = 0
        
        for i in range(idx, max(0, idx - 10), -1):
            if i >= 1:
                close = data.iloc[i]['close']
                prev_close = data.iloc[i-1]['close']
                pct = (close - prev_close) / prev_close
                
                if pct >= self.min_close_ratio:
                    count += 1
                else:
                    break
        
        return count
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Signal:
        """生成信号"""
        current_price = data.iloc[idx]['close']
        
        # 持有时检查
        if self.position > 0:
            self.holding_days += 1
            
            pnl_pct = (current_price - self.entry_price) / self.entry_price
            
            # 止盈止损
            if pnl_pct <= -self.stop_loss:
                self.holding_days = 0
                self.position = 0
                return Signal(SignalType.SELL, current_price, 1.0, f"止损 ({pnl_pct:.2%})")
            
            if pnl_pct >= self.take_profit:
                self.holding_days = 0
                self.position = 0
                return Signal(SignalType.SELL, current_price, 1.0, f"止盈 ({pnl_pct:.2%})")
            
            # 开板（未涨停）时卖出
            is_lu, _ = self.is_limit_up(data, idx)
            if not is_lu:
                self.holding_days = 0
                self.position = 0
                return Signal(SignalType.SELL, current_price, 1.0, "开板")
            
            # 持有到期
            if self.holding_days >= self.max_hold_days:
                self.holding_days = 0
                self.position = 0
                return Signal(SignalType.SELL, current_price, 1.0, "持有到期")
            
            return Signal(SignalType.HOLD, current_price, f"连板持有第{self.holding_days}天")
        
        # 空仓时寻找连板机会
        if idx < 2:
            return Signal(SignalType.HOLD, current_price, "数据不足")
        
        # 计算连板数
        continuous = self.count_continuous_limit_up(data, idx-1)
        
        # 昨日达到目标连板数，今日继续涨停时买入
        if continuous == self.target_continuous:
            is_lu, lu_pct = self.is_limit_up(data, idx)
            
            if is_lu:
                self.entry_price = current_price
                self.holding_days = 0
                
                return Signal(
                    SignalType.BUY,
                    current_price,
                    min(1.0, 0.5 + lu_pct),
                    f"{self.target_continuous}连板"
                )
        
        return Signal(SignalType.HOLD, current_price, "等待连板")
    
    def is_limit_up(self, data: pd.DataFrame, idx: int) -> Tuple[bool, float]:
        """判断是否涨停"""
        if idx < 1:
            return False, 0.0
        
        close = data.iloc[idx]['close']
        prev_close = data.iloc[idx-1]['close']
        pct = (close - prev_close) / prev_close
        
        return pct >= self.min_close_ratio, pct


class LimitUpPullbackStrategy(BaseStrategy):
    """
    涨停回马枪策略
    
    核心逻辑：
    1. 识别近期涨停股（5-10 天内）
    2. 等待回调至支撑位（如 10 日线）
    3. 回调企稳后买入
    4. 博弈第二波拉升
    
    适用场景：
    - 强势股回调
    - 龙头股第二波
    - 题材反复炒作
    """
    
    name = "涨停回马枪策略"
    
    def __init__(self,
                 limit_up_lookback: int = 10,    # 涨停回溯期
                 pullback_days: int = 5,         # 回调天数
                 ma_support: int = 10,           # 支撑均线
                 min_rebound: float = 0.03,      # 最小反弹
                 hold_days: int = 5,             # 持有期
                 stop_loss: float = 0.05,        # 止损
                 take_profit: float = 0.15):     # 止盈
        super().__init__(params={
            'limit_up_lookback': limit_up_lookback,
            'pullback_days': pullback_days,
            'ma_support': ma_support,
            'min_rebound': min_rebound,
            'hold_days': hold_days,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        })
        
        self.limit_up_lookback = limit_up_lookback
        self.pullback_days = pullback_days
        self.ma_support = ma_support
        self.min_rebound = min_rebound
        self.hold_days = hold_days
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        
        # 状态
        self.last_limit_up_idx = -1
        self.holding_days = 0
        self.entry_price = 0.0
    
    def has_recent_limit_up(self, data: pd.DataFrame, idx: int) -> Tuple[bool, int]:
        """
        检查近期是否有涨停
        
        Returns:
            (是否有涨停，距离天数)
        """
        for i in range(idx - 1, max(-1, idx - self.limit_up_lookback - 1), -1):
            if i >= 1:
                close = data.iloc[i]['close']
                prev_close = data.iloc[i-1]['close']
                pct = (close - prev_close) / prev_close
                
                if pct >= 0.095:
                    days_ago = idx - i
                    return True, days_ago
        
        return False, -1
    
    def is_at_support(self, data: pd.DataFrame, idx: int) -> bool:
        """检查是否在支撑位附近"""
        if idx < self.ma_support:
            return False
        
        # 计算均线
        ma = data.iloc[idx-self.ma_support:idx]['close'].mean()
        current_price = data.iloc[idx]['close']
        
        # 价格在均线附近（±3%）
        return abs(current_price - ma) / ma <= 0.03
    
    def is_rebounding(self, data: pd.DataFrame, idx: int) -> bool:
        """检查是否开始反弹"""
        if idx < 2:
            return False
        
        # 今日上涨且前一日下跌
        today_ret = (data.iloc[idx]['close'] - data.iloc[idx-1]['close']) / data.iloc[idx-1]['close']
        yesterday_ret = (data.iloc[idx-1]['close'] - data.iloc[idx-2]['close']) / data.iloc[idx-2]['close']
        
        return today_ret >= self.min_rebound and yesterday_ret < 0
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Signal:
        """生成信号"""
        current_price = data.iloc[idx]['close']
        
        # 持有时检查
        if self.position > 0:
            self.holding_days += 1
            
            pnl_pct = (current_price - self.entry_price) / self.entry_price
            
            if pnl_pct <= -self.stop_loss:
                self.holding_days = 0
                self.position = 0
                return Signal(SignalType.SELL, current_price, 1.0, f"止损 ({pnl_pct:.2%})")
            
            if pnl_pct >= self.take_profit:
                self.holding_days = 0
                self.position = 0
                return Signal(SignalType.SELL, current_price, 1.0, f"止盈 ({pnl_pct:.2%})")
            
            if self.holding_days >= self.hold_days:
                self.holding_days = 0
                self.position = 0
                return Signal(SignalType.SELL, current_price, 1.0, "持有到期")
            
            return Signal(SignalType.HOLD, current_price, f"持有第{self.holding_days}天")
        
        # 空仓时寻找回马枪机会
        has_lu, days_ago = self.has_recent_limit_up(data, idx)
        
        if has_lu and days_ago >= self.pullback_days:
            # 检查是否在支撑位且开始反弹
            if self.is_at_support(data, idx) and self.is_rebounding(data, idx):
                self.entry_price = current_price
                self.holding_days = 0
                
                return Signal(
                    SignalType.BUY,
                    current_price,
                    strength=0.7,
                    reason=f"涨停回马枪 (第{days_ago}天)"
                )
        
        return Signal(SignalType.HOLD, current_price, "等待回马枪机会")
