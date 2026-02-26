"""
策略基类模块
定义策略接口和信号类型
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, List
import pandas as pd
import numpy as np


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"           # 买入
    SELL = "sell"         # 卖出
    HOLD = "hold"         # 持有
    COVER = "cover"       # 平仓 (空头)
    SHORT = "short"       # 做空


@dataclass
class Signal:
    """
    交易信号
    
    Attributes:
        signal_type: 信号类型
        price: 信号价格
        strength: 信号强度 (0-1)
        reason: 信号原因
        metadata: 额外元数据
    """
    signal_type: SignalType
    price: float
    strength: float = 1.0
    reason: str = ""
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseStrategy(ABC):
    """
    策略基类
    
    所有策略都需要继承此类并实现相应方法
    """
    
    def __init__(self, name: str = None, params: dict = None):
        """
        初始化策略
        
        Args:
            name: 策略名称
            params: 策略参数
        """
        self.name = name or self.__class__.__name__
        self.params = params or {}
        self.position = 0  # 当前仓位 (股数)
        self.cash = 0  # 当前现金
        self.data: Optional[pd.DataFrame] = None  # 当前股票数据
        self.current_idx = 0  # 当前 K 线索引
        self.trade_log: List[dict] = []  # 交易日志
        
    @abstractmethod
    def generate_signal(self, data: pd.DataFrame, current_idx: int) -> Signal:
        """
        生成交易信号 (必须实现)
        
        Args:
            data: 历史数据 (包含当前 bar)
            current_idx: 当前 K 线索引
            
        Returns:
            Signal: 交易信号
        """
        pass
    
    def init_position(self, cash: float):
        """初始化仓位"""
        self.cash = cash
        self.position = 0
        self.trade_log = []
    
    def update_position(self, shares: int, price: float, trade_type: str):
        """
        更新仓位
        
        Args:
            shares: 股数 (正数买入，负数卖出)
            price: 成交价格
            trade_type: 交易类型
        """
        cost = shares * price
        self.position += shares
        self.cash -= cost
        
        # 记录交易
        self.trade_log.append({
            "idx": self.current_idx,
            "trade_type": trade_type,
            "shares": shares,
            "price": price,
            "cost": cost,
            "position": self.position,
            "cash": self.cash
        })
    
    def get_current_price(self, data: pd.DataFrame, current_idx: int) -> float:
        """获取当前价格 (默认使用收盘价)"""
        return data.iloc[current_idx]["close"]
    
    def get_portfolio_value(self, current_price: float) -> float:
        """计算组合总价值"""
        return self.cash + self.position * current_price
    
    def calculate_position_size(self, price: float, portfolio_value: float, 
                                max_position_pct: float = 1.0) -> int:
        """
        计算仓位大小
        
        Args:
            price: 当前价格
            portfolio_value: 组合总价值
            max_position_pct: 最大仓位比例
            
        Returns:
            股数 (100 的整数倍)
        """
        target_value = portfolio_value * max_position_pct
        shares = int(target_value / price / 100) * 100  # A 股最小交易单位 100 股
        return max(0, shares)
    
    def on_bar_start(self, data: pd.DataFrame, current_idx: int):
        """Bar 开始时的回调 (可选实现)"""
        pass
    
    def on_bar_end(self, data: pd.DataFrame, current_idx: int, signal: Signal):
        """Bar 结束时的回调 (可选实现)"""
        pass
    
    def on_backtest_complete(self):
        """回测完成时的回调 (可选实现)"""
        pass
    
    def get_params_description(self) -> dict:
        """返回参数说明 (用于优化)"""
        return {}
