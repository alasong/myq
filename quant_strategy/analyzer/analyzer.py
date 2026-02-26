"""
绩效分析模块
计算各类投资绩效指标
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    """绩效指标集合"""
    total_return: float
    annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    avg_holding_period: float
    turnover_rate: float
    alpha: float
    beta: float
    information_ratio: float
    tracking_error: float


class PerformanceAnalyzer:
    """
    绩效分析器
    
    计算各类投资绩效指标
    """
    
    TRADING_DAYS_PER_YEAR = 252
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        初始化分析器
        
        Args:
            risk_free_rate: 无风险利率 (年化)
        """
        self.risk_free_rate = risk_free_rate
    
    def analyze(self, daily_values: pd.DataFrame, 
                benchmark_values: pd.Series = None) -> PerformanceMetrics:
        """
        全面分析绩效
        
        Args:
            daily_values: 每日资产数据 (包含 total_value 列)
            benchmark_values: 基准价格序列
            
        Returns:
            PerformanceMetrics: 绩效指标
        """
        if daily_values.empty:
            return None
        
        values = daily_values["total_value"]
        returns = values.pct_change().dropna()
        
        # 基础收益指标
        total_return = (values.iloc[-1] - values.iloc[0]) / values.iloc[0]
        n_days = len(values)
        annual_return = (1 + total_return) ** (self.TRADING_DAYS_PER_YEAR / n_days) - 1
        
        # 波动率
        annual_volatility = returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)
        
        # 夏普比率
        excess_returns = returns - self.risk_free_rate / self.TRADING_DAYS_PER_YEAR
        if returns.std() > 0:
            sharpe_ratio = (excess_returns.mean() / returns.std()) * np.sqrt(self.TRADING_DAYS_PER_YEAR)
        else:
            sharpe_ratio = 0.0
        
        # 索提诺比率 (只考虑下行波动)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() > 0:
            sortino_ratio = (excess_returns.mean() / downside_returns.std()) * np.sqrt(self.TRADING_DAYS_PER_YEAR)
        else:
            sortino_ratio = 0.0
        
        # 最大回撤
        cum_returns = (1 + returns).cumprod()
        running_max = cum_returns.cummax()
        drawdown = (cum_returns - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # 最大回撤持续期
        max_dd_duration = self._calculate_drawdown_duration(drawdown)
        
        # 卡尔玛比率
        if abs(max_drawdown) > 0:
            calmar_ratio = annual_return / abs(max_drawdown)
        else:
            calmar_ratio = 0.0
        
        # 基准相关指标
        alpha, beta, information_ratio, tracking_error = 0.0, 0.0, 0.0, 0.0
        
        if benchmark_values is not None and not benchmark_values.empty:
            benchmark_returns = benchmark_values.pct_change().dropna()
            
            # 对齐数据
            aligned_returns = returns.reindex(benchmark_returns.index).fillna(0)
            benchmark_returns = benchmark_returns.reindex(aligned_returns.index).fillna(0)
            
            if len(aligned_returns) > 20:
                # Beta
                covariance = aligned_returns.cov(benchmark_returns)
                benchmark_var = benchmark_returns.var()
                beta = covariance / benchmark_var if benchmark_var > 0 else 0.0
                
                # Alpha (年化)
                rf_daily = self.risk_free_rate / self.TRADING_DAYS_PER_YEAR
                alpha = (aligned_returns.mean() - rf_daily) - beta * (benchmark_returns.mean() - rf_daily)
                alpha = alpha * self.TRADING_DAYS_PER_YEAR
                
                # 跟踪误差和信息比率
                active_returns = aligned_returns - benchmark_returns
                tracking_error = active_returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)
                if tracking_error > 0:
                    information_ratio = active_returns.mean() * self.TRADING_DAYS_PER_YEAR / tracking_error
        
        # 交易统计 (需要从 trades 数据计算)
        win_rate, profit_factor, avg_win, avg_loss, largest_win, largest_loss = \
            self._calculate_trade_stats(daily_values)
        
        # 平均持仓期
        avg_holding_period = self._calculate_avg_holding_period(daily_values)
        
        # 换手率
        turnover_rate = self._calculate_turnover(daily_values)
        
        return PerformanceMetrics(
            total_return=total_return,
            annual_return=annual_return,
            annual_volatility=annual_volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_dd_duration,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            avg_holding_period=avg_holding_period,
            turnover_rate=turnover_rate,
            alpha=alpha,
            beta=beta,
            information_ratio=information_ratio,
            tracking_error=tracking_error
        )
    
    def _calculate_drawdown_duration(self, drawdown: pd.Series) -> int:
        """计算最大回撤持续期"""
        in_drawdown = drawdown < 0
        if not in_drawdown.any():
            return 0
        
        # 找出连续回撤期
        dd_groups = (in_drawdown != in_drawdown.shift()).cumsum()
        max_duration = 0
        
        for group in dd_groups.unique():
            if in_drawdown[dd_groups == group].iloc[0]:
                duration = (dd_groups == group).sum()
                max_duration = max(max_duration, duration)
        
        return max_duration
    
    def _calculate_trade_stats(self, daily_values: pd.DataFrame) -> tuple:
        """计算交易统计指标 (简化版)"""
        # 实际应用中需要从 trades 数据精确计算
        # 这里使用简化方法
        returns = daily_values["total_value"].pct_change().dropna()
        
        positive_returns = returns[returns > 0]
        negative_returns = returns[returns < 0]
        
        win_rate = len(positive_returns) / len(returns) if len(returns) > 0 else 0
        avg_win = positive_returns.mean() if len(positive_returns) > 0 else 0
        avg_loss = abs(negative_returns.mean()) if len(negative_returns) > 0 else 0
        largest_win = positive_returns.max() if len(positive_returns) > 0 else 0
        largest_loss = abs(negative_returns.min()) if len(negative_returns) > 0 else 0
        
        total_profit = positive_returns.sum() if len(positive_returns) > 0 else 0
        total_loss = abs(negative_returns.sum()) if len(negative_returns) > 0 else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        return win_rate, profit_factor, avg_win, avg_loss, largest_win, largest_loss
    
    def _calculate_avg_holding_period(self, daily_values: pd.DataFrame) -> float:
        """计算平均持仓期"""
        # 简化实现
        return 0.0
    
    def _calculate_turnover(self, daily_values: pd.DataFrame) -> float:
        """计算换手率"""
        # 简化实现
        return 0.0
    
    def generate_report(self, metrics: PerformanceMetrics) -> str:
        """生成文本报告"""
        report = f"""
=====================================
           绩效分析报告
=====================================

【收益指标】
  总收益率：     {metrics.total_return:>10.2%}
  年化收益率：   {metrics.annual_return:>10.2%}
  年化波动率：   {metrics.annual_volatility:>10.2%}

【风险调整收益】
  夏普比率：     {metrics.sharpe_ratio:>10.2f}
  索提诺比率：   {metrics.sortino_ratio:>10.2f}
  卡尔玛比率：   {metrics.calmar_ratio:>10.2f}

【风险指标】
  最大回撤：     {metrics.max_drawdown:>10.2%}
  回撤持续期：   {metrics.max_drawdown_duration:>10d} 天

【市场相关】
  Alpha:         {metrics.alpha:>10.2%}
  Beta:          {metrics.beta:>10.2f}
  信息比率：     {metrics.information_ratio:>10.2f}
  跟踪误差：     {metrics.tracking_error:>10.2%}

【交易统计】
  胜率：         {metrics.win_rate:>10.2%}
  盈亏比：       {metrics.profit_factor:>10.2f}
  平均盈利：     {metrics.avg_win:>10.2%}
  平均亏损：     {metrics.avg_loss:>10.2%}
  最大盈利：     {metrics.largest_win:>10.2%}
  最大亏损：     {metrics.largest_loss:>10.2%}

=====================================
"""
        return report
