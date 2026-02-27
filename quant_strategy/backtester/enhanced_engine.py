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
        1. 成交额（代表市值和流动性）- 标准化评分
        2. 成交量稳定性 - 标准化评分
        3. 历史波动率（反向指标，越低越好）- 标准化评分
        4. 市值代理（使用股票代码特征）

        改进：
        - 使用 Z-Score 标准化，避免数据量级差异
        - 增加数据有效性检查

        注意：
        - 避免使用未来函数（如回测期内的收益率）
        - 真实场景应该从外部获取市值数据

        Args:
            data_dict: {ts_code: DataFrame}
            top_n: 选择数量

        Returns:
            筛选后的数据字典
        """
        # 第一步：收集所有股票的原始指标
        stock_metrics = {}

        for ts_code, data in data_dict.items():
            if len(data) < 20:
                logger.debug(f"{ts_code}: 数据不足 20 条，跳过")
                continue

            # 1. 成交额（代表市值和流动性）- 使用期初数据
            if 'amount' in data.columns and data['amount'].notna().any():
                initial_amount = data['amount'].iloc[:5].mean()
                # 检查成交额是否有效
                if initial_amount <= 0:
                    logger.debug(f"{ts_code}: 成交额为零或负，跳过")
                    continue
            else:
                logger.debug(f"{ts_code}: 无成交额数据，跳过")
                continue

            # 2. 流动性 - 成交量稳定性
            if 'vol' in data.columns and data['vol'].notna().any():
                avg_volume = data['vol'].iloc[:5].mean()
                vol_std = data['vol'].std()
                volume_stability = 1 / (vol_std + 1) if vol_std > 0 else 1
                if avg_volume <= 0:
                    logger.debug(f"{ts_code}: 成交量为零或负，跳过")
                    continue
            else:
                logger.debug(f"{ts_code}: 无成交量数据，跳过")
                continue

            # 3. 波动率（反向指标）- 使用历史波动率
            if len(data) > 20:
                volatility = data['close'].iloc[:20].pct_change().std()
            else:
                volatility = data['close'].pct_change().std()
            
            if pd.isna(volatility) or volatility < 0:
                volatility = 0.05  # 默认波动率

            # 4. 市值代理（使用股票代码特征）
            market_cap_score = 0
            if ts_code.startswith(('600', '601', '603')):
                market_cap_score = 3
            elif ts_code.startswith(('000', '001', '002')):
                market_cap_score = 2
            elif ts_code.startswith('300'):
                market_cap_score = 1

            stock_metrics[ts_code] = {
                'amount': initial_amount,
                'avg_volume': avg_volume,
                'volume_stability': volume_stability,
                'volatility': volatility,
                'market_cap_score': market_cap_score
            }

        if not stock_metrics:
            logger.warning("没有符合条件的股票，返回全部股票")
            return data_dict

        logger.info(f"有效指标数据：{len(stock_metrics)} 只股票")

        # 第二步：标准化处理（Z-Score）
        metrics_df = pd.DataFrame(stock_metrics).T

        # 成交额标准化（越大越好）
        amount_mean = metrics_df['amount'].mean()
        amount_std = metrics_df['amount'].std()
        if amount_std > 0:
            metrics_df['amount_score'] = (metrics_df['amount'] - amount_mean) / amount_std
        else:
            metrics_df['amount_score'] = 0

        # 成交量稳定性标准化（越大越好）
        vol_stab_mean = metrics_df['volume_stability'].mean()
        vol_stab_std = metrics_df['volume_stability'].std()
        if vol_stab_std > 0:
            metrics_df['vol_stab_score'] = (metrics_df['volume_stability'] - vol_stab_mean) / vol_stab_std
        else:
            metrics_df['vol_stab_score'] = 0

        # 波动率标准化（越小越好，取负）
        vol_mean = metrics_df['volatility'].mean()
        vol_std = metrics_df['volatility'].std()
        if vol_std > 0:
            metrics_df['vol_score'] = -(metrics_df['volatility'] - vol_mean) / vol_std  # 负向指标
        else:
            metrics_df['vol_score'] = 0

        # 市值评分已经是离散的 1-3 分，需要归一化到 0-1
        metrics_df['market_score'] = metrics_df['market_cap_score'] / 3.0

        # 第三步：综合评分
        # 成交额 40% + 流动性稳定性 20% + 低波动 20% + 市值特征 20%
        metrics_df['total_score'] = (
            metrics_df['amount_score'] * 0.4 +
            metrics_df['vol_stab_score'] * 0.2 +
            metrics_df['vol_score'] * 0.2 +
            metrics_df['market_score'] * 0.2
        )

        # 选择前 N 名
        sorted_stocks = metrics_df.nlargest(top_n, 'total_score')

        logger.info(f"龙头股评分（Top {top_n}）:")
        for ts_code, row in sorted_stocks.iterrows():
            logger.info(f"  {ts_code}: {row['total_score']:.2f} "
                       f"(成交额={row['amount']/1e8:.2f}亿，波动率={row['volatility']:.2%})")

        return {ts_code: data_dict[ts_code] for ts_code in sorted_stocks.index}
    
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
