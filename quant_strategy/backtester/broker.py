"""
模拟券商模块
处理订单执行、仓位管理、交易成本
"""
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum
import pandas as pd


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"  # 市价单
    LIMIT = "limit"    # 限价单


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """订单"""
    ts_code: str
    order_type: OrderType
    direction: str  # buy/sell
    shares: int
    price: float  # 限价单价格，市价单为 0
    timestamp: str
    status: OrderStatus = OrderStatus.PENDING
    filled_price: float = 0.0
    filled_shares: int = 0
    commission: float = 0.0
    slippage: float = 0.0


class SimulatedBroker:
    """
    模拟券商
    
    模拟真实交易环境，包括：
    - 订单撮合
    - 滑点模拟
    - 手续费计算
    - 仓位管理
    """
    
    # A 股交易规则
    COMMISSION_RATE = 0.0003  # 佣金率 (万分之三)
    MIN_COMMISSION = 5.0      # 最低佣金 5 元
    STAMP_DUTY_RATE = 0.001   # 印花税 (卖出时收取，千分之一)
    TRANSFER_FEE_RATE = 0.00001  # 过户费 (万分之 0.1)
    
    def __init__(self, initial_cash: float, slippage_rate: float = 0.001):
        """
        初始化券商
        
        Args:
            initial_cash: 初始资金
            slippage_rate: 滑点率
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.slippage_rate = slippage_rate
        
        # 持仓
        self.positions: dict[str, int] = {}  # {ts_code: shares}
        self.position_cost: dict[str, float] = {}  # {ts_code: cost_basis}
        
        # 订单历史
        self.orders: List[Order] = []
        self.trades: List[dict] = []
        
        # 每日资产记录
        self.daily_values: List[dict] = []
    
    def get_position(self, ts_code: str) -> int:
        """获取某股票持仓"""
        return self.positions.get(ts_code, 0)
    
    def get_available_shares(self, ts_code: str) -> int:
        """获取可用股数 (A 股 T+1，简化处理：全部可用)"""
        return self.get_position(ts_code)
    
    def submit_order(self, ts_code: str, direction: str, shares: int,
                     order_type: OrderType = OrderType.MARKET,
                     limit_price: float = None,
                     current_price: float = None) -> Order:
        """
        提交订单
        
        Args:
            ts_code: 股票代码
            direction: buy/sell
            shares: 股数
            order_type: 订单类型
            limit_price: 限价单价格
            current_price: 当前市场价格
            
        Returns:
            Order: 订单对象
        """
        if shares <= 0:
            return None
        
        if direction == "buy" and shares % 100 != 0:
            # A 股买入必须是 100 的整数倍
            shares = (shares // 100) * 100
            if shares <= 0:
                return None
        
        order = Order(
            ts_code=ts_code,
            order_type=order_type,
            direction=direction,
            shares=shares,
            price=limit_price or 0,
            timestamp=current_price,
            status=OrderStatus.PENDING
        )
        
        # 立即执行订单 (简化：市价单立即成交)
        if order_type == OrderType.MARKET and current_price:
            self._execute_order(order, current_price)
        
        self.orders.append(order)
        return order
    
    def _execute_order(self, order: Order, market_price: float):
        """执行订单"""
        # 检查资金/持仓是否充足
        if order.direction == "buy":
            required_cash = order.shares * market_price * (1 + self.COMMISSION_RATE + self.TRANSFER_FEE_RATE)
            if required_cash > self.cash:
                order.status = OrderStatus.REJECTED
                return
            
            # 计算滑点
            slippage = market_price * self.slippage_rate
            filled_price = market_price + slippage
        else:
            # 卖出
            if self.get_position(order.ts_code) < order.shares:
                order.status = OrderStatus.REJECTED
                return
            
            slippage = market_price * self.slippage_rate
            filled_price = market_price - slippage
        
        # 计算费用
        commission = max(self.MIN_COMMISSION, order.shares * filled_price * self.COMMISSION_RATE)
        transfer_fee = order.shares * filled_price * self.TRANSFER_FEE_RATE
        
        if order.direction == "buy":
            total_cost = order.shares * filled_price + commission + transfer_fee
            self.cash -= total_cost
            
            # 更新持仓成本
            old_shares = self.get_position(order.ts_code)
            old_cost = self.position_cost.get(order.ts_code, 0)
            new_cost = old_cost + order.shares * filled_price
            self.position_cost[order.ts_code] = new_cost
            self.positions[order.ts_code] = old_shares + order.shares
        else:
            # 卖出
            stamp_duty = order.shares * filled_price * self.STAMP_DUTY_RATE
            total_received = order.shares * filled_price - commission - transfer_fee - stamp_duty
            self.cash += total_received
            
            # 更新持仓
            self.positions[order.ts_code] -= order.shares
            if self.positions[order.ts_code] == 0:
                del self.positions[order.ts_code]
                del self.position_cost[order.ts_code]
        
        # 更新订单状态
        order.status = OrderStatus.FILLED
        order.filled_price = filled_price
        order.filled_shares = order.shares
        order.commission = commission
        order.slippage = slippage * order.shares
        
        # 记录交易
        self.trades.append({
            "ts_code": order.ts_code,
            "direction": order.direction,
            "shares": order.shares,
            "filled_price": filled_price,
            "commission": commission,
            "slippage": order.slippage,
            "timestamp": order.timestamp
        })
    
    def get_portfolio_value(self, prices: dict[str, float]) -> float:
        """计算组合总价值"""
        value = self.cash
        for ts_code, shares in self.positions.items():
            if ts_code in prices:
                value += shares * prices[ts_code]
        return value
    
    def record_daily_value(self, date: str, prices: dict[str, float]):
        """记录每日资产"""
        total_value = self.get_portfolio_value(prices)
        self.daily_values.append({
            "date": date,
            "cash": self.cash,
            "total_value": total_value,
            "positions": dict(self.positions)
        })
    
    def get_return_series(self) -> pd.DataFrame:
        """获取收益率序列"""
        if not self.daily_values:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.daily_values)
        df["daily_return"] = df["total_value"].pct_change()
        df["cum_return"] = (1 + df["daily_return"]).cumprod() - 1
        return df
    
    def get_summary(self) -> dict:
        """获取交易摘要"""
        total_commission = sum(t["commission"] for t in self.trades)
        total_slippage = sum(t["slippage"] for t in self.trades)
        
        return {
            "initial_cash": self.initial_cash,
            "final_cash": self.cash,
            "total_trades": len(self.trades),
            "buy_trades": sum(1 for t in self.trades if t["direction"] == "buy"),
            "sell_trades": sum(1 for t in self.trades if t["direction"] == "sell"),
            "total_commission": total_commission,
            "total_slippage": total_slippage,
            "current_positions": dict(self.positions)
        }
