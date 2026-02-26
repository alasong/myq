"""
增强的板块回测引擎
支持多种回测模式：individual/portfolio/leaders
"""
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from loguru import logger
from tqdm import tqdm

from .engine import BacktestConfig, BacktestResult
from .parallel_engine import ParallelBacktester, BacktestTask, BacktestTaskResult, _run_single_backtest


class EnhancedSectorBacktester(ParallelBacktester):
    """
    增强的板块回测引擎
    
    支持模式：
    - individual: 逐个股票回测（默认）
    - portfolio: 等权组合回测
    - leaders: 龙头股回测
    """
    
    def backtest_sector(
        self,
        strategy_class: type,
        ts_codes: List[str],
        data_provider: Any,
        start_date: str,
        end_date: str,
        strategy_params: dict = None,
        config: Any = None,
        show_progress: bool = True,
        mode: str = "individual",
        top_n: int = 5
    ) -> Dict[str, BacktestTaskResult]:
        """
        回测整个板块/股票组

        Args:
            strategy_class: 策略类
            ts_codes: 股票代码列表
            data_provider: 数据提供者
            start_date: 开始日期
            end_date: 结束日期
            strategy_params: 策略参数
            config: 回测配置
            show_progress: 是否显示进度
            mode: 回测模式
                  - individual: 逐个回测（默认）
                  - portfolio: 等权组合回测
                  - leaders: 龙头股回测
            top_n: 龙头股数量（leaders 模式使用）

        Returns:
            {ts_code: BacktestTaskResult} 结果字典
        """
        if config is None:
            config = BacktestConfig()

        if strategy_params is None:
            strategy_params = {}

        logger.info(f"开始板块回测：{len(ts_codes)} 只股票，模式={mode}")

        # 获取数据
        data_dict = {}
        for ts_code in tqdm(ts_codes, desc="获取数据", disable=not show_progress):
            try:
                data = data_provider.get_daily_data(
                    ts_code, start_date, end_date, adj="qfq"
                )
                if not data.empty:
                    data_dict[ts_code] = data
            except Exception as e:
                logger.debug(f"获取数据失败 {ts_code}: {e}")

        if not data_dict:
            logger.error("没有获取到任何股票数据")
            return {}

        logger.info(f"成功获取 {len(data_dict)} 只股票数据")

        # leaders 模式：选择龙头股
        if mode == "leaders":
            data_dict = self._select_leaders(data_dict, top_n)
            logger.info(f"龙头股模式：选择前 {top_n} 只股票")

        # 执行回测
        results = self.backtest_stocks(
            strategy_class=strategy_class,
            data_dict=data_dict,
            strategy_params=strategy_params,
            config=config,
            show_progress=show_progress
        )

        # portfolio 模式：计算组合收益
        if mode == "portfolio":
            portfolio_result = self._calculate_portfolio_return(results)
            if portfolio_result:
                results["PORTFOLIO"] = portfolio_result
                logger.info(f"等权组合收益率：{portfolio_result.result.total_return:.2%}")

        return results
    
    def _select_leaders(self, data_dict: dict, top_n: int = 5) -> dict:
        """
        选择龙头股
        
        标准：
        1. 成交额（代表市值和流动性）
        2. 收益率
        3. 波动率（反向指标）
        
        Args:
            data_dict: {ts_code: DataFrame}
            top_n: 选择数量
            
        Returns:
            筛选后的数据字典
        """
        scores = {}
        
        for ts_code, data in data_dict.items():
            if len(data) < 20:
                continue
            
            # 评分标准
            # 1. 成交额（代表市值和流动性）
            avg_amount = data['amount'].mean() if 'amount' in data.columns else 0
            
            # 2. 收益率
            total_return = (data['close'].iloc[-1] - data['close'].iloc[0]) / data['close'].iloc[0]
            
            # 3. 波动率（反向指标）
            volatility = data['close'].pct_change().std()
            
            # 综合评分
            score = avg_amount * 0.4 + total_return * 0.4 - volatility * 0.2
            scores[ts_code] = score
        
        # 选择前 N 名
        sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
        
        return {ts_code: data_dict[ts_code] for ts_code, _ in sorted_stocks}
    
    def _calculate_portfolio_return(self, results: dict) -> Optional[BacktestTaskResult]:
        """
        计算等权组合收益
        
        Args:
            results: {ts_code: BacktestTaskResult}
            
        Returns:
            组合回测结果
        """
        # 收集所有股票的每日收益
        daily_returns = {}
        for ts_code, task_result in results.items():
            if task_result.result and task_result.result.daily_values is not None:
                dv = task_result.result.daily_values
                if 'daily_return' in dv.columns:
                    daily_returns[ts_code] = dv.set_index('date')['daily_return']
        
        if not daily_returns:
            return None
        
        # 对齐日期
        returns_df = pd.DataFrame(daily_returns)
        returns_df = returns_df.dropna()
        
        # 等权组合收益
        portfolio_returns = returns_df.mean(axis=1)
        
        # 计算组合指标
        cumulative = (1 + portfolio_returns).cumprod()
        total_return = cumulative.iloc[-1] - 1
        
        # 年化收益
        n_days = len(portfolio_returns)
        annual_return = (1 + total_return) ** (365 / n_days) - 1
        
        # 夏普比率
        sharpe = (portfolio_returns.mean() / portfolio_returns.std()) * np.sqrt(252) if portfolio_returns.std() > 0 else 0
        
        # 最大回撤
        cum_max = cumulative.cummax()
        drawdown = (cumulative - cum_max) / cum_max
        max_drawdown = drawdown.min()
        
        # 胜率
        win_rate = (portfolio_returns > 0).mean()
        
        # 交易次数
        total_trades = sum((portfolio_returns != 0).astype(int))
        
        # 创建模拟结果
        class MockResult:
            def __init__(self, tr, ar, sr, md, wr, tt):
                self.total_return = tr
                self.annual_return = ar
                self.sharpe_ratio = sr
                self.max_drawdown = md
                self.win_rate = wr
                self.total_trades = tt
        
        return BacktestTaskResult(
            ts_code="PORTFOLIO",
            result=MockResult(total_return, annual_return, sharpe, max_drawdown, win_rate, total_trades),
            error=None
        )
