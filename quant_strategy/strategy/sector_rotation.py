"""
板块轮动策略模块
支持板块动量轮动、资金流向轮动等策略
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .base_strategy import BaseStrategy, Signal, SignalType
from .vectorized_strategy import VectorizedStrategy


@dataclass
class SectorData:
    """板块数据结构"""
    name: str
    stocks: List[str]
    momentum: float = 0.0
    flow_score: float = 0.0
    rank: int = 0


class SectorMomentumRotationStrategy(VectorizedStrategy):
    """
    板块动量轮动策略
    
    核心逻辑：
    1. 计算各板块 N 日动量
    2. 选择动量最强的 TopK 板块
    3. 买入板块内龙头股（成交量最大）
    4. 定期调仓（默认 5 天）
    
    适用场景：
    - 板块轮动明显的市场环境
    - 趋势性行情
    """
    
    def __init__(self,
                 lookback: int = 20,           # 动量计算周期
                 top_k: int = 3,               # 选择板块数量
                 rebalance_days: int = 5,      # 调仓周期
                 sector_type: str = 'industry',# 板块类型
                 hold_period: int = 5,         # 持有期
                 min_sector_momentum: float = 0.0,  # 最小板块动量
                 volume_period: int = 20):     # 成交量均线周期
        """
        初始化板块轮动策略
        
        Args:
            lookback: 动量计算周期（日）
            top_k: 选择前 K 个板块
            rebalance_days: 调仓周期（日）
            sector_type: 板块类型 (industry/concept)
            hold_period: 持有期
            min_sector_momentum: 最小板块动量阈值
            volume_period: 成交量均线周期
        """
        super().__init__(params={
            'lookback': lookback,
            'top_k': top_k,
            'rebalance_days': rebalance_days,
            'sector_type': sector_type,
            'hold_period': hold_period,
            'min_sector_momentum': min_sector_momentum,
            'volume_period': volume_period
        })
        
        self.lookback = lookback
        self.top_k = top_k
        self.rebalance_days = rebalance_days
        self.sector_type = sector_type
        self.hold_period = hold_period
        self.min_sector_momentum = min_sector_momentum
        self.volume_period = volume_period
        
        # 板块数据
        self.sector_stocks: Dict[str, List[str]] = {}
        self.stock_sector_map: Dict[str, str] = {}
        
        # 状态跟踪
        self.current_sectors: List[str] = []
        self.current_stock: Optional[str] = None
        self.days_since_rebalance = 0
        self.days_holding = 0
        self.entry_price = 0.0
    
    def set_sector_data(self, sector_stocks: Dict[str, List[str]]):
        """
        设置板块成分股数据
        
        Args:
            sector_stocks: {板块名：[股票代码列表]}
        """
        self.sector_stocks = sector_stocks
        # 构建股票→板块映射
        self.stock_sector_map = {}
        for sector, stocks in sector_stocks.items():
            for stock in stocks:
                self.stock_sector_map[stock] = sector
    
    def calculate_sector_momentum(self, 
                                   sector_data: Dict[str, pd.DataFrame],
                                   idx: int) -> Dict[str, float]:
        """
        计算各板块动量
        
        Args:
            sector_data: {股票代码：DataFrame}
            idx: 当前索引
            
        Returns:
            {板块名：动量值}
        """
        momentum = {}
        
        for sector, stocks in self.sector_stocks.items():
            sector_returns = []
            
            for stock in stocks:
                if stock in sector_data:
                    df = sector_data[stock]
                    if idx >= self.lookback and len(df) > idx:
                        # 计算 N 日收益
                        current_price = df.iloc[idx]['close']
                        past_price = df.iloc[idx - self.lookback]['close']
                        ret = (current_price - past_price) / past_price
                        
                        if not np.isnan(ret):
                            sector_returns.append(ret)
            
            if sector_returns:
                # 板块等权平均收益
                momentum[sector] = np.mean(sector_returns)
            else:
                momentum[sector] = 0.0
        
        return momentum
    
    def select_top_sectors(self, momentum: Dict[str, float]) -> List[str]:
        """选择动量最强的 TopK 板块"""
        # 过滤掉动量低于阈值的板块
        filtered = {k: v for k, v in momentum.items() 
                   if v >= self.min_sector_momentum}
        
        if not filtered:
            return []
        
        # 排序选择 TopK
        sorted_sectors = sorted(filtered.items(), 
                               key=lambda x: x[1], 
                               reverse=True)
        return [s[0] for s in sorted_sectors[:self.top_k]]
    
    def select_stock_in_sector(self, 
                                sector: str,
                                sector_data: Dict[str, pd.DataFrame],
                                idx: int) -> Optional[str]:
        """
        选择板块内股票
        
        选择逻辑：
        1. 成交量最大（流动性最好）
        2. 市值适中（可选）
        3. 动量最强（可选）
        
        Args:
            sector: 板块名
            sector_data: {股票代码：DataFrame}
            idx: 当前索引
            
        Returns:
            选中的股票代码
        """
        stocks = self.sector_stocks.get(sector, [])
        
        best_stock = None
        best_score = 0
        
        for stock in stocks:
            if stock in sector_data:
                df = sector_data[stock]
                if len(df) > idx and idx >= self.volume_period:
                    # 计算成交量评分
                    avg_volume = df.iloc[idx-self.volume_period:idx]['vol'].mean()
                    current_volume = df.iloc[idx]['vol']
                    
                    # 流动性评分（成交量越大越好）
                    volume_score = np.log1p(avg_volume)
                    
                    if volume_score > best_score:
                        best_score = volume_score
                        best_stock = stock
        
        return best_stock
    
    def should_rebalance(self) -> bool:
        """是否应该调仓"""
        return self.days_since_rebalance >= self.rebalance_days
    
    def reset_rebalance_timer(self):
        """重置调仓计时器"""
        self.days_since_rebalance = 0
    
    def update_state(self, bought: bool):
        """更新状态"""
        if bought:
            self.days_holding = 0
        else:
            self.days_holding += 1
        
        if self.days_since_rebalance < self.rebalance_days:
            self.days_since_rebalance += 1
    
    def generate_signal_bar(self, data: pd.DataFrame, idx: int) -> Signal:
        """
        逐 bar 模式信号生成（用于单股票回测）
        
        注意：此策略需要板块数据，单股票模式下功能受限
        """
        current_price = data.iloc[idx]['close']
        
        # 检查是否应该调仓
        if self.should_rebalance():
            self.reset_rebalance_timer()
            
            # 简单实现：如果当前股票所属板块动量强，则持有
            if self.current_stock and self.current_stock in self.stock_sector_map:
                sector = self.stock_sector_map[self.current_stock]
                # 这里需要全市场数据来计算板块动量
                # 在单股票模式下，简化为动量信号
                if idx >= self.lookback:
                    momentum = (current_price - data.iloc[idx-self.lookback]['close']) / data.iloc[idx-self.lookback]['close']
                    
                    if momentum > self.min_sector_momentum and self.position <= 0:
                        self.entry_price = current_price
                        return Signal(
                            signal_type=SignalType.BUY,
                            price=current_price,
                            strength=min(1.0, 0.5 + momentum),
                            reason=f"板块动量={momentum:.2%}"
                        )
        
        # 持有期检查
        if self.position > 0:
            if self.days_holding >= self.hold_period:
                return Signal(
                    signal_type=SignalType.SELL,
                    price=current_price,
                    reason="持有到期"
                )
        
        self.update_state(bought=False)
        
        return Signal(
            signal_type=SignalType.HOLD,
            price=current_price,
            reason="持有"
        )
    
    def generate_signals_vectorized(self, data: pd.DataFrame):
        """
        向量化信号生成
        
        注意：板块轮动策略需要多股票数据，这里提供简化版本
        """
        n = len(data)
        signals = np.full(n, SignalType.HOLD.value, dtype=object)
        strengths = np.full(n, 0.5)
        reasons = [''] * n
        
        # 简化实现：使用个股动量模拟板块动量
        if idx >= self.lookback:
            momentum = data['close'].pct_change(self.lookback)
            
            # 动量高于阈值时买入
            buy_signal = momentum > self.min_sector_momentum
            
            for i in range(self.lookback, n):
                if buy_signal.iloc[i]:
                    signals[i] = SignalType.BUY.value
                    strengths[i] = min(1.0, 0.5 + momentum.iloc[i])
                    reasons[i] = f"动量={momentum.iloc[i]:.2%}"
        
        from .vectorized_strategy import VectorizedSignal
        return VectorizedSignal(
            signal_types=signals,
            strengths=strengths,
            reasons=reasons,
            metadata={'momentum': momentum}
        )
    
    def get_params_description(self) -> Dict[str, dict]:
        """返回参数说明"""
        return {
            'lookback': {
                'type': int,
                'default': 20,
                'range': (10, 60),
                'description': '动量计算周期'
            },
            'top_k': {
                'type': int,
                'default': 3,
                'range': (1, 10),
                'description': '选择板块数量'
            },
            'rebalance_days': {
                'type': int,
                'default': 5,
                'range': (1, 20),
                'description': '调仓周期'
            },
            'min_sector_momentum': {
                'type': float,
                'default': 0.0,
                'range': (-0.2, 0.2),
                'description': '最小板块动量阈值'
            }
        }


class SectorFlowStrategy(BaseStrategy):
    """
    板块资金流向策略
    
    核心逻辑：
    1. 计算各板块资金净流入
    2. 选择资金持续流入的板块
    3. 跟随主力资金布局
    
    注意：需要主力资金流向数据支持
    """
    
    name = "板块资金流向策略"
    
    def __init__(self,
                 flow_lookback: int = 5,     # 资金流计算周期
                 top_k: int = 3,             # 选择板块数量
                 rebalance_days: int = 5):   # 调仓周期
        super().__init__(params={
            'flow_lookback': flow_lookback,
            'top_k': top_k,
            'rebalance_days': rebalance_days
        })
        
        self.flow_lookback = flow_lookback
        self.top_k = top_k
        self.rebalance_days = rebalance_days
        
        self.sector_stocks: Dict[str, List[str]] = {}
        self.days_since_rebalance = 0
    
    def set_sector_data(self, sector_stocks: Dict[str, List[str]]):
        """设置板块数据"""
        self.sector_stocks = sector_stocks
    
    def calculate_net_flow(self, 
                           stock_data: pd.DataFrame, 
                           idx: int) -> float:
        """
        计算资金净流入（估算）
        
        基于价格和成交量变化估算主力资金流向
        """
        if idx < self.flow_lookback:
            return 0.0
        
        net_flow = 0.0
        
        for i in range(idx - self.flow_lookback + 1, idx + 1):
            close = stock_data.iloc[i]['close']
            prev_close = stock_data.iloc[i-1]['close']
            volume = stock_data.iloc[i]['vol']
            
            # 价格上涨视为资金流入
            if close > prev_close:
                net_flow += volume * (close - prev_close) / prev_close
            else:
                net_flow -= volume * abs(close - prev_close) / prev_close
        
        return net_flow
    
    def generate_signal(self, data: pd.DataFrame, idx: int) -> Signal:
        """生成信号"""
        current_price = data.iloc[idx]['close']
        
        # 简化实现：使用资金流估算
        net_flow = self.calculate_net_flow(data, idx)
        
        # 资金流入时买入
        if net_flow > 0 and self.position <= 0:
            return Signal(
                signal_type=SignalType.BUY,
                price=current_price,
                strength=min(1.0, 0.5 + net_flow / 1e8),
                reason=f"资金净流入={net_flow:.0f}"
            )
        
        # 资金流出时卖出
        if net_flow < 0 and self.position > 0:
            return Signal(
                signal_type=SignalType.SELL,
                price=current_price,
                reason=f"资金净流出={net_flow:.0f}"
            )
        
        return Signal(
            signal_type=SignalType.HOLD,
            price=current_price,
            reason="持有"
        )
