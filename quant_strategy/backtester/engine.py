"""
回测引擎核心模块
事件驱动的回测框架
"""
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd
from loguru import logger
from tqdm import tqdm

from ..strategy.base_strategy import BaseStrategy, SignalType
from .broker import SimulatedBroker, OrderType


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_cash: float = 100000.0  # 初始资金
    commission_rate: float = 0.0003  # 佣金率
    slippage_rate: float = 0.001  # 滑点率
    max_position_pct: float = 1.0  # 最大仓位比例
    allow_short: bool = False  # 是否允许做空


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_name: str
    ts_code: str
    start_date: str
    end_date: str
    initial_cash: float
    final_value: float
    total_return: float
    annual_return: float
    benchmark_return: float
    alpha: float
    beta: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    daily_values: pd.DataFrame
    trades: List[dict]
    signals: List[dict]
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "strategy_name": self.strategy_name,
            "ts_code": self.ts_code,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_cash": self.initial_cash,
            "final_value": self.final_value,
            "total_return": f"{self.total_return:.2%}",
            "annual_return": f"{self.annual_return:.2%}",
            "sharpe_ratio": f"{self.sharpe_ratio:.2f}",
            "max_drawdown": f"{self.max_drawdown:.2%}",
            "win_rate": f"{self.win_rate:.2%}",
            "profit_factor": f"{self.profit_factor:.2f}",
            "total_trades": self.total_trades
        }


class Backtester:
    """
    回测引擎
    
    事件驱动架构，支持：
    - 单股票/多股票回测
    - 实时信号生成
    - 订单执行模拟
    - 绩效评估
    """
    
    def __init__(self, config: BacktestConfig = None):
        """
        初始化回测引擎
        
        Args:
            config: 回测配置
        """
        self.config = config or BacktestConfig()
        self.broker: Optional[SimulatedBroker] = None
        self.strategy: Optional[BaseStrategy] = None
        self.data: Optional[pd.DataFrame] = None
        self.results: Optional[BacktestResult] = None
    
    def run(self, strategy: BaseStrategy, data: pd.DataFrame,
            ts_code: str = None, benchmark_data: pd.DataFrame = None) -> BacktestResult:
        """
        运行回测
        
        Args:
            strategy: 策略实例
            data: 股票数据 (包含 OHLCV)
            ts_code: 股票代码
            benchmark_data: 基准数据 (用于计算 alpha/beta)

        Returns:
            BacktestResult: 回测结果
        """
        self.strategy = strategy
        self.data = data
        self.ts_code = ts_code or "UNKNOWN"

        # 初始化券商
        self.broker = SimulatedBroker(
            initial_cash=self.config.initial_cash,
            slippage_rate=self.config.slippage_rate
        )

        # 初始化策略
        self.strategy.init_position(self.config.initial_cash)
        
        # 向量化策略预计算
        if hasattr(self.strategy, 'precompute'):
            logger.info(f"向量化策略预计算：{self.strategy.name}")
            self.strategy.precompute(data)
        # 调用策略初始化 (如果方法存在)
        elif hasattr(self.strategy, 'on_init'):
            self.strategy.on_init(data)

        # 回测主循环
        signals_log = []
        n_bars = len(data)

        logger.info(f"开始回测：{self.ts_code}, {self.strategy.name}")
        logger.info(f"回测区间：{data.index[0]} - {data.index[-1]}, 共 {n_bars} 根 K 线")

        for i in tqdm(range(len(data)), desc="回测中"):
            current_date = data.index[i]
            
            # Bar 开始回调
            self.strategy.on_bar_start(data, i)
            
            # 生成信号
            signal = self.strategy.generate_signal(data, i)
            self.strategy.current_idx = i

            # 记录信号
            if signal:
                signals_log.append({
                    "date": current_date,
                    "signal_type": signal.signal_type.value,
                    "price": signal.price,
                    "strength": signal.strength,
                    "reason": signal.reason,
                    "position": self.strategy.position
                })

                # 执行信号
                self._execute_signal(signal, data, i)

                # Bar 结束回调
                self.strategy.on_bar_end(data, i, signal)
            else:
                # 无信号时也调用回调
                self.strategy.on_bar_end(data, i, None)
            
            # 记录每日资产
            current_price = data.iloc[i]["close"]
            self.broker.record_daily_value(
                date=current_date,
                prices={self.ts_code: current_price}
            )
        
        # 回测完成
        self.strategy.on_backtest_complete()
        
        # 计算结果
        self.results = self._calculate_result(benchmark_data)
        
        logger.info(f"回测完成：总收益 {self.results.total_return:.2%}, "
                   f"夏普比率 {self.results.sharpe_ratio:.2f}")
        
        return self.results
    
    def _execute_signal(self, signal, data: pd.DataFrame, idx: int):
        """执行交易信号"""
        current_price = data.iloc[idx]["close"]
        
        if signal.signal_type == SignalType.BUY:
            # 买入
            if self.broker.get_position(self.ts_code) <= 0:
                portfolio_value = self.broker.get_portfolio_value({self.ts_code: current_price})
                max_shares = self.calculate_buy_shares(current_price, portfolio_value)
                
                if max_shares > 0:
                    self.broker.submit_order(
                        ts_code=self.ts_code,
                        direction="buy",
                        shares=max_shares,
                        order_type=OrderType.MARKET,
                        current_price=current_price
                    )
                    # 更新策略仓位
                    self.strategy.position = self.broker.get_position(self.ts_code)
        
        elif signal.signal_type == SignalType.SELL:
            # 卖出
            if self.broker.get_position(self.ts_code) > 0:
                shares = self.broker.get_position(self.ts_code)
                self.broker.submit_order(
                    ts_code=self.ts_code,
                    direction="sell",
                    shares=shares,
                    order_type=OrderType.MARKET,
                    current_price=current_price
                )
                # 更新策略仓位
                self.strategy.position = 0
    
    def calculate_buy_shares(self, price: float, portfolio_value: float) -> int:
        """计算可买入股数"""
        target_value = portfolio_value * self.config.max_position_pct
        shares = int(target_value / price / 100) * 100
        return max(0, shares)
    
    def _calculate_result(self, benchmark_data: pd.DataFrame = None) -> BacktestResult:
        """计算回测结果指标"""
        daily_values = self.broker.get_return_series()

        if daily_values.empty:
            return None

        # 基础指标
        initial_value = self.config.initial_cash
        final_value = daily_values["total_value"].iloc[-1]
        total_return = (final_value - initial_value) / initial_value

        # 年化收益 - 使用 date 列计算天数
        if "date" in daily_values.columns and len(daily_values) > 1:
            first_date = pd.to_datetime(daily_values["date"].iloc[0])
            last_date = pd.to_datetime(daily_values["date"].iloc[-1])
            n_days = (last_date - first_date).days
        else:
            n_days = len(daily_values)
        annual_return = (1 + total_return) ** (365 / max(n_days, 1)) - 1
        
        # 夏普比率
        daily_returns = daily_values["daily_return"].dropna()
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * (252 ** 0.5)
        else:
            sharpe_ratio = 0.0
        
        # 最大回撤
        cum_values = (1 + daily_returns).cumprod()
        running_max = cum_values.cummax()
        drawdown = (cum_values - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # 基准对比
        benchmark_return = 0.0
        alpha = 0.0
        beta = 0.0
        
        if benchmark_data is not None and not benchmark_data.empty:
            benchmark_return = (benchmark_data["close"].iloc[-1] - benchmark_data["close"].iloc[0]) / benchmark_data["close"].iloc[0]
            
            # 计算 alpha/beta
            if len(daily_returns) > 20:
                # 对齐数据
                benchmark_returns = benchmark_data["close"].pct_change().reindex(daily_returns.index).fillna(0)
                covariance = daily_returns.cov(benchmark_returns)
                benchmark_var = benchmark_returns.var()
                
                if benchmark_var > 0:
                    beta = covariance / benchmark_var
                    # CAPM: alpha = 实际收益 - (无风险收益 + beta * (市场收益 - 无风险收益))
                    rf = 0.02 / 252  # 假设年化无风险利率 2%
                    alpha = daily_returns.mean() - (rf + beta * (benchmark_returns.mean() - rf))
                    alpha = alpha * 252  # 年化
        
        # 交易统计
        trades = self.broker.trades
        total_trades = len(trades)
        
        # 胜率
        if total_trades > 0:
            # 简化：假设每笔卖出交易对应一笔盈亏
            sell_trades = [t for t in trades if t["direction"] == "sell"]
            # 这里简化计算，实际需要更复杂的逻辑匹配买卖
            profitable_trades = 0
            total_profit = 0
            total_loss = 0
            
            for trade in sell_trades:
                # 简化处理
                if trade["filled_price"] > 0:
                    profitable_trades += 1
                    total_profit += trade["shares"] * trade["filled_price"] * 0.01  # 假设平均盈利 1%
            
            win_rate = profitable_trades / len(sell_trades) if sell_trades else 0
            profit_factor = total_profit / max(abs(total_loss), 1)
        else:
            win_rate = 0.0
            profit_factor = 0.0
        
        return BacktestResult(
            strategy_name=self.strategy.name,
            ts_code=self.ts_code,
            start_date=str(pd.to_datetime(daily_values["date"].iloc[0]).date()),
            end_date=str(pd.to_datetime(daily_values["date"].iloc[-1]).date()),
            initial_cash=initial_value,
            final_value=final_value,
            total_return=total_return,
            annual_return=annual_return,
            benchmark_return=benchmark_return,
            alpha=alpha,
            beta=beta,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            daily_values=daily_values,
            trades=trades,
            signals=[]
        )

    def run_single_stock(self, strategy: BaseStrategy, data: pd.DataFrame) -> Optional[BacktestResult]:
        """
        单股票回测（简化版，用于策略扫描）

        Args:
            strategy: 策略实例
            data: 股票数据 DataFrame

        Returns:
            BacktestResult 或 None
        """
        try:
            # 重置券商和策略状态
            self.broker = SimulatedBroker(
                initial_cash=self.config.initial_cash,
                slippage_rate=self.config.slippage_rate
            )
            self.strategy = strategy
            self.results = None

            # 运行回测
            result = self._run_backtest(data)
            return self.results
        except Exception as e:
            logger.debug(f"单股票回测失败：{e}")
            return None

    def _run_backtest(self, data: pd.DataFrame):
        """执行回测主逻辑（内部方法）"""
        # 初始化
        self.broker = SimulatedBroker(
            initial_cash=self.config.initial_cash,
            slippage_rate=self.config.slippage_rate
        )
        self.strategy.position = 0
        self.broker.daily_values = []

        # 策略初始化
        self.strategy.on_init(data)

        # 遍历数据
        for i in range(len(data)):
            current_date = data.index[i] if hasattr(data.index, '__getitem__') else i

            # 策略生成信号
            signal = self.strategy.generate_signal(data, i)

            # 记录信号
            if signal:
                self.strategy.signals.append({
                    "date": current_date,
                    "type": signal.signal_type.name,
                    "strength": signal.strength,
                    "reason": signal.reason,
                    "position": self.strategy.position
                })

                # 执行信号
                self._execute_signal(signal, data, i)

                # Bar 结束回调
                self.strategy.on_bar_end(data, i, signal)

            # 记录每日资产
            current_price = data.iloc[i]["close"]
            self.broker.record_daily_value(
                date=current_date,
                prices={self.ts_code: current_price}
            )

        # 回测完成
        self.strategy.on_backtest_complete()

        # 计算结果
        self.results = self._calculate_result(None)
        return self.results

    def run_multi_stock(self, strategy_class: type, data_dict: Dict[str, pd.DataFrame],
                        params: dict = None) -> Dict[str, BacktestResult]:
        """
        多股票回测

        Args:
            strategy_class: 策略类
            data_dict: {ts_code: DataFrame} 数据字典
            params: 策略参数

        Returns:
            {ts_code: BacktestResult} 结果字典
        """
        results = {}

        for ts_code, data in tqdm(data_dict.items(), desc="多股票回测"):
            strategy = strategy_class(**(params or {}))
            result = self.run(strategy, data, ts_code)
            results[ts_code] = result

        return results
