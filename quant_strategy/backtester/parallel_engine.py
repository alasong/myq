"""
高并发回测引擎模块
支持多进程、多线程并行回测
"""
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
import pandas as pd
from loguru import logger
from tqdm import tqdm
import os
import sys


@dataclass
class BacktestTask:
    """回测任务"""
    ts_code: str
    data: pd.DataFrame
    strategy_class: type
    strategy_params: dict
    config: Any


@dataclass
class BacktestTaskResult:
    """回测任务结果"""
    ts_code: str
    result: Any
    error: Optional[str] = None


def _run_single_backtest(task: BacktestTask) -> BacktestTaskResult:
    """
    运行单个回测任务（进程目标函数）
    
    Args:
        task: 回测任务
        
    Returns:
        回测结果
    """
    try:
        # 导入需要的模块（在进程内导入）
        from quant_strategy.backtester import Backtester, BacktestConfig
        
        # 创建策略
        strategy = task.strategy_class(**task.strategy_params)
        
        # 创建回测器
        backtester = Backtester(task.config)
        
        # 运行回测
        result = backtester.run(strategy, task.data, task.ts_code)
        
        return BacktestTaskResult(
            ts_code=task.ts_code,
            result=result
        )
    except Exception as e:
        return BacktestTaskResult(
            ts_code=task.ts_code,
            result=None,
            error=str(e)
        )


class ParallelBacktester:
    """
    并行回测引擎
    
    支持：
    - 多进程并行回测（适合 CPU 密集型）
    - 多线程并行回测（适合 I/O 密集型）
    - 板块/股票组回测
    - 多策略同步回测
    """
    
    def __init__(self, max_workers: int = None, use_processes: bool = True):
        """
        初始化并行回测引擎
        
        Args:
            max_workers: 最大工作进程/线程数，默认 CPU 核心数
            use_processes: 是否使用多进程（否则使用多线程）
        """
        if max_workers is None:
            max_workers = mp.cpu_count()
        
        self.max_workers = max_workers
        self.use_processes = use_processes
        
        logger.info(f"并行回测引擎初始化：workers={max_workers}, "
                   f"mode={'process' if use_processes else 'thread'}")
    
    def backtest_stocks(
        self,
        strategy_class: type,
        data_dict: Dict[str, pd.DataFrame],
        strategy_params: dict = None,
        config: Any = None,
        show_progress: bool = True
    ) -> Dict[str, BacktestTaskResult]:
        """
        批量回测多只股票
        
        Args:
            strategy_class: 策略类
            data_dict: {ts_code: DataFrame} 数据字典
            strategy_params: 策略参数
            config: 回测配置
            show_progress: 是否显示进度
            
        Returns:
            {ts_code: BacktestTaskResult} 结果字典
        """
        from quant_strategy.backtester import BacktestConfig
        
        if config is None:
            config = BacktestConfig()
        
        if strategy_params is None:
            strategy_params = {}
        
        # 创建任务列表
        tasks = []
        for ts_code, data in data_dict.items():
            tasks.append(BacktestTask(
                ts_code=ts_code,
                data=data,
                strategy_class=strategy_class,
                strategy_params=strategy_params,
                config=config
            ))
        
        logger.info(f"开始批量回测：{len(tasks)} 只股票")
        
        results = {}
        
        if self.use_processes:
            # 多进程模式
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(_run_single_backtest, task): task 
                          for task in tasks}
                
                iterator = as_completed(futures)
                if show_progress:
                    iterator = tqdm(iterator, total=len(tasks), desc="回测进度")
                
                for future in iterator:
                    task = futures[future]
                    try:
                        result = future.result()
                        results[result.ts_code] = result
                    except Exception as e:
                        logger.error(f"回测失败 {task.ts_code}: {e}")
                        results[task.ts_code] = BacktestTaskResult(
                            ts_code=task.ts_code,
                            result=None,
                            error=str(e)
                        )
        else:
            # 多线程模式
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(_run_single_backtest, task): task 
                          for task in tasks}
                
                iterator = as_completed(futures)
                if show_progress:
                    iterator = tqdm(iterator, total=len(tasks), desc="回测进度")
                
                for future in iterator:
                    task = futures[future]
                    try:
                        result = future.result()
                        results[result.ts_code] = result
                    except Exception as e:
                        logger.error(f"回测失败 {task.ts_code}: {e}")
                        results[task.ts_code] = BacktestTaskResult(
                            ts_code=task.ts_code,
                            result=None,
                            error=str(e)
                        )
        
        # 统计结果
        success_count = sum(1 for r in results.values() if r.error is None)
        logger.info(f"回测完成：成功 {success_count}/{len(tasks)}")
        
        return results
    
    def backtest_sector(
        self,
        strategy_class: type,
        ts_codes: List[str],
        data_provider: Any,
        start_date: str,
        end_date: str,
        strategy_params: dict = None,
        config: Any = None,
        show_progress: bool = True
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
            
        Returns:
            {ts_code: BacktestTaskResult} 结果字典
        """
        from quant_strategy.backtester import BacktestConfig
        
        if config is None:
            config = BacktestConfig()
        
        if strategy_params is None:
            strategy_params = {}
        
        logger.info(f"开始板块回测：{len(ts_codes)} 只股票")
        
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
        
        # 执行回测
        return self.backtest_stocks(
            strategy_class=strategy_class,
            data_dict=data_dict,
            strategy_params=strategy_params,
            config=config,
            show_progress=show_progress
        )
    
    def backtest_multi_strategy(
        self,
        strategies: List[tuple],  # [(strategy_class, strategy_params, strategy_name), ...]
        data: pd.DataFrame,
        ts_code: str,
        config: Any = None,
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        多策略同步回测（同一股票）
        
        Args:
            strategies: 策略列表 [(strategy_class, strategy_params, strategy_name), ...]
            data: 股票数据
            ts_code: 股票代码
            config: 回测配置
            show_progress: 是否显示进度
            
        Returns:
            {strategy_name: BacktestResult} 结果字典
        """
        from quant_strategy.backtester import BacktestConfig
        
        if config is None:
            config = BacktestConfig()
        
        logger.info(f"开始多策略回测：{len(strategies)} 个策略")
        
        results = {}
        
        # 创建任务
        tasks = []
        for strategy_class, strategy_params, strategy_name in strategies:
            tasks.append(BacktestTask(
                ts_code=f"{ts_code}_{strategy_name}",
                data=data,
                strategy_class=strategy_class,
                strategy_params=strategy_params,
                config=config
            ))
        
        # 执行回测
        if self.use_processes:
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(_run_single_backtest, task): task 
                          for task in tasks}
                
                iterator = as_completed(futures)
                if show_progress:
                    iterator = tqdm(iterator, total=len(tasks), desc="策略回测")
                
                for future in iterator:
                    task = futures[future]
                    try:
                        result = future.result()
                        # 提取策略名
                        strategy_name = task.ts_code.split("_")[-1]
                        results[strategy_name] = result.result
                    except Exception as e:
                        logger.error(f"策略回测失败：{e}")
        else:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(_run_single_backtest, task): task 
                          for task in tasks}
                
                iterator = as_completed(futures)
                if show_progress:
                    iterator = tqdm(iterator, total=len(tasks), desc="策略回测")
                
                for future in iterator:
                    task = futures[future]
                    try:
                        result = future.result()
                        strategy_name = task.ts_code.split("_")[-1]
                        results[strategy_name] = result.result
                    except Exception as e:
                        logger.error(f"策略回测失败：{e}")
        
        return results
    
    def compare_strategies(
        self,
        strategies: List[tuple],
        data_dict: Dict[str, pd.DataFrame],
        config: Any = None,
        show_progress: bool = True
    ) -> pd.DataFrame:
        """
        多策略对比回测
        
        Args:
            strategies: 策略列表 [(strategy_class, strategy_params, strategy_name), ...]
            data_dict: {ts_code: DataFrame} 数据字典
            config: 回测配置
            show_progress: 是否显示进度
            
        Returns:
            策略对比结果 DataFrame
        """
        all_results = []
        
        for strategy_class, strategy_params, strategy_name in strategies:
            logger.info(f"回测策略：{strategy_name}")
            
            results = self.backtest_stocks(
                strategy_class=strategy_class,
                data_dict=data_dict,
                strategy_params=strategy_params,
                config=config,
                show_progress=False
            )
            
            # 汇总结果
            for ts_code, task_result in results.items():
                if task_result.result:
                    all_results.append({
                        "ts_code": ts_code,
                        "strategy": strategy_name,
                        "total_return": task_result.result.total_return,
                        "annual_return": task_result.result.annual_return,
                        "sharpe_ratio": task_result.result.sharpe_ratio,
                        "max_drawdown": task_result.result.max_drawdown,
                        "win_rate": task_result.result.win_rate,
                        "total_trades": task_result.result.total_trades
                    })
        
        df = pd.DataFrame(all_results)
        
        if not df.empty:
            # 按策略分组统计
            summary = df.groupby("strategy").agg({
                "total_return": "mean",
                "annual_return": "mean",
                "sharpe_ratio": "mean",
                "max_drawdown": "mean",
                "win_rate": "mean",
                "total_trades": "sum"
            }).round(4)
            
            logger.info("\n策略对比摘要:")
            logger.info(summary.to_string())
        
        return df


def run_parallel_backtest(
    strategy_class: type,
    data_dict: Dict[str, pd.DataFrame],
    strategy_params: dict = None,
    max_workers: int = None,
    use_processes: bool = True
) -> Dict[str, BacktestTaskResult]:
    """
    便捷函数：并行回测
    
    Args:
        strategy_class: 策略类
        data_dict: {ts_code: DataFrame} 数据字典
        strategy_params: 策略参数
        max_workers: 最大工作进程数
        use_processes: 是否使用多进程
        
    Returns:
        {ts_code: BacktestTaskResult} 结果字典
    """
    backtester = ParallelBacktester(
        max_workers=max_workers,
        use_processes=use_processes
    )
    
    return backtester.backtest_stocks(
        strategy_class=strategy_class,
        data_dict=data_dict,
        strategy_params=strategy_params
    )
