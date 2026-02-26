"""
参数优化模块
支持网格搜索、随机搜索、贝叶斯优化 (Optuna) 等方法
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Callable, Optional, Tuple
from dataclasses import dataclass
from itertools import product
import random

from loguru import logger
from tqdm import tqdm


@dataclass
class ParamRange:
    """参数范围定义"""
    name: str
    values: List[Any]  # 离散值列表或范围

    @classmethod
    def range(cls, name: str, start: Any, end: Any, step: Any = None):
        """创建范围参数"""
        if step:
            values = []
            current = start
            while current <= end:
                values.append(current)
                current += step
            return cls(name=name, values=values)
        else:
            # 整数范围
            return cls(name=name, values=list(range(start, end + 1)))


@dataclass
class OptimizationResult:
    """优化结果"""
    best_params: Dict[str, Any]
    best_score: float
    all_results: pd.DataFrame
    total_trials: int
    method: str = ""

    def summary(self) -> str:
        """生成结果摘要"""
        lines = [
            "\n" + "=" * 60,
            f"参数优化结果 ({self.method})",
            "=" * 60,
            f"总试验次数：{self.total_trials}",
            f"最佳得分：{self.best_score:.4f}",
            "最佳参数:",
        ]
        for key, value in self.best_params.items():
            lines.append(f"  {key}: {value}")

        lines.append("\nTop 10 结果:")
        top10 = self.all_results.nlargest(10, 'score')
        for i, (_, row) in enumerate(top10.iterrows(), 1):
            params_str = ", ".join([f"{k}={v}" for k, v in row.items()
                                    if k not in ['score', 'rank']])
            lines.append(f"  {i}. score={row['score']:.4f} | {params_str}")

        lines.append("=" * 60)
        return "\n".join(lines)


class ParamOptimizer:
    """
    参数优化器

    支持多种优化策略：
    - 网格搜索 (Grid Search)
    - 随机搜索 (Random Search)
    - 贝叶斯优化 (Optuna TPE)
    - 进化算法
    """

    def __init__(self, strategy_class, data: pd.DataFrame,
                 ts_code: str = "optimization",
                 score_func: Callable = None):
        """
        初始化优化器

        Args:
            strategy_class: 策略类
            data: 股票数据 DataFrame
            ts_code: 股票代码
            score_func: 评分函数，接收 BacktestResult 返回 float
        """
        self.strategy_class = strategy_class
        self.data = data
        self.ts_code = ts_code

        # 默认评分函数：使用夏普比率
        if score_func is None:
            self.score_func = lambda result: result.sharpe_ratio
        else:
            self.score_func = score_func

        self.results = []

    def grid_search(self, param_ranges: List[ParamRange],
                    backtester_class=None, backtest_config=None,
                    show_progress: bool = True) -> OptimizationResult:
        """
        网格搜索

        Args:
            param_ranges: 参数范围列表
            backtester_class: 回测类
            backtest_config: 回测配置
            show_progress: 是否显示进度

        Returns:
            OptimizationResult
        """
        from quant_strategy.backtester import Backtester, BacktestConfig

        if backtest_config is None:
            backtest_config = BacktestConfig()

        # 生成所有参数组合
        param_names = [p.name for p in param_ranges]
        param_values = [p.values for p in param_ranges]
        all_combinations = list(product(*param_values))

        logger.info(f"网格搜索：{len(all_combinations)} 个参数组合")

        results = []
        iterator = tqdm(all_combinations, desc="网格搜索") if show_progress else all_combinations

        for combo in iterator:
            params = dict(zip(param_names, combo))

            try:
                # 创建策略
                strategy = self.strategy_class(**params)

                # 运行回测
                backtester = Backtester(backtest_config)
                result = backtester.run(strategy, self.data, self.ts_code)

                if result:
                    score = self.score_func(result)
                    result_dict = params.copy()
                    result_dict['score'] = score
                    results.append(result_dict)

            except Exception as e:
                logger.debug(f"回测失败 {params}: {e}")

        # 创建结果 DataFrame
        df = pd.DataFrame(results)

        if df.empty:
            return OptimizationResult(
                best_params={},
                best_score=0,
                all_results=df,
                total_trials=len(all_combinations),
                method="grid"
            )

        # 找出最佳结果
        best_idx = df['score'].idxmax()
        best_row = df.loc[best_idx]
        best_params = {name: best_row[name] for name in param_names}

        return OptimizationResult(
            best_params=best_params,
            best_score=best_row['score'],
            all_results=df,
            total_trials=len(all_combinations),
            method="grid"
        )

    def random_search(self, param_ranges: List[ParamRange],
                      n_iterations: int = 100,
                      backtester_class=None, backtest_config=None,
                      show_progress: bool = True) -> OptimizationResult:
        """
        随机搜索

        Args:
            param_ranges: 参数范围列表
            n_iterations: 迭代次数
            backtester_class: 回测类
            backtest_config: 回测配置
            show_progress: 是否显示进度

        Returns:
            OptimizationResult
        """
        from quant_strategy.backtester import Backtester, BacktestConfig

        if backtest_config is None:
            backtest_config = BacktestConfig()

        logger.info(f"随机搜索：{n_iterations} 次迭代")

        results = []

        for i in tqdm(range(n_iterations), desc="随机搜索", disable=not show_progress):
            # 随机选择参数
            params = {}
            for param_range in param_ranges:
                params[param_range.name] = random.choice(param_range.values)

            try:
                # 创建策略
                strategy = self.strategy_class(**params)

                # 运行回测
                backtester = Backtester(backtest_config)
                result = backtester.run(strategy, self.data, self.ts_code)

                if result:
                    score = self.score_func(result)
                    result_dict = params.copy()
                    result_dict['score'] = score
                    results.append(result_dict)

            except Exception as e:
                logger.debug(f"回测失败 {params}: {e}")

        # 创建结果 DataFrame
        df = pd.DataFrame(results)

        if df.empty:
            return OptimizationResult(
                best_params={},
                best_score=0,
                all_results=df,
                total_trials=n_iterations,
                method="random"
            )

        # 找出最佳结果
        best_idx = df['score'].idxmax()
        best_row = df.loc[best_idx]
        best_params = {name: best_row[name] for name in param_ranges}

        return OptimizationResult(
            best_params=best_params,
            best_score=best_row['score'],
            all_results=df,
            total_trials=n_iterations,
            method="random"
        )

    def bayesian_search(self, param_ranges: List[ParamRange],
                        n_trials: int = 100,
                        backtest_config=None,
                        show_progress: bool = True,
                        study_name: str = None) -> OptimizationResult:
        """
        贝叶斯优化 (使用 Optuna)

        Args:
            param_ranges: 参数范围列表
            n_trials: 试验次数
            backtest_config: 回测配置
            show_progress: 是否显示进度
            study_name: 研究名称

        Returns:
            OptimizationResult
        """
        try:
            import optuna
        except ImportError:
            logger.error("Optuna 未安装，请运行：pip install optuna")
            return self.random_search(param_ranges, n_trials, backtest_config, show_progress)

        from quant_strategy.backtester import Backtester, BacktestConfig

        if backtest_config is None:
            backtest_config = BacktestConfig()

        logger.info(f"贝叶斯优化：{n_trials} 次试验")

        # 定义参数分布
        def suggest_params(trial, param_ranges):
            params = {}
            for param_range in param_ranges:
                values = param_range.values
                if len(values) > 0 and isinstance(values[0], int):
                    # 整数参数
                    params[param_range.name] = trial.suggest_int(
                        param_range.name, min(values), max(values)
                    )
                elif len(values) > 0 and isinstance(values[0], float):
                    # 浮点参数
                    params[param_range.name] = trial.suggest_float(
                        param_range.name, min(values), max(values), step=values[1]-values[0] if len(values) > 1 else 0.1
                    )
                else:
                    # 离散选择
                    params[param_range.name] = trial.suggest_categorical(param_range.name, values)
            return params

        # 目标函数
        def objective(trial):
            params = suggest_params(trial, param_ranges)

            try:
                strategy = self.strategy_class(**params)
                backtester = Backtester(backtest_config)
                result = backtester.run(strategy, self.data, self.ts_code)

                if result:
                    score = self.score_func(result)
                    # 记录结果
                    trial.set_user_attr("params", params)
                    trial.set_user_attr("score", score)
                    return score
                else:
                    return -np.inf

            except Exception as e:
                logger.debug(f"回测失败 {params}: {e}")
                return -np.inf

        # 创建研究
        sampler = optuna.samplers.TPESampler(seed=42)
        study = optuna.create_study(
            study_name=study_name or "strategy_optimization",
            sampler=sampler,
            direction="maximize"
        )

        # 运行优化
        study.optimize(
            objective,
            n_trials=n_trials,
            show_progress_bar=show_progress,
            gc_after_trial=True
        )

        # 提取结果
        results = []
        for trial in study.trials:
            if trial.value is not None and trial.value != -np.inf:
                params = trial.user_attrs.get("params", {})
                result_dict = params.copy()
                result_dict['score'] = trial.value
                results.append(result_dict)

        df = pd.DataFrame(results)

        if df.empty:
            return OptimizationResult(
                best_params={},
                best_score=0,
                all_results=df,
                total_trials=n_trials,
                method="bayesian"
            )

        # 最佳结果
        best_params = study.best_params
        best_score = study.best_value

        logger.info(f"贝叶斯优化完成：最佳得分 {best_score:.4f}")

        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            all_results=df,
            total_trials=n_trials,
            method="bayesian"
        )

    def optimize(self, method: str = "grid", **kwargs) -> OptimizationResult:
        """
        执行优化

        Args:
            method: 优化方法 ("grid", "random", "bayesian")
            **kwargs: 传递给具体优化方法的参数

        Returns:
            OptimizationResult
        """
        if method == "grid":
            return self.grid_search(**kwargs)
        elif method == "random":
            return self.random_search(**kwargs)
        elif method == "bayesian":
            return self.bayesian_search(**kwargs)
        else:
            raise ValueError(f"未知的优化方法：{method}")


def create_param_grid(base_params: Dict[str, Any],
                      **param_ranges) -> List[ParamRange]:
    """
    创建参数网格

    Args:
        base_params: 基础参数
        **param_ranges: 参数范围，格式为 name=(start, end, step)

    Returns:
        ParamRange 列表
    """
    ranges = []

    for name, range_def in param_ranges.items():
        if isinstance(range_def, (list, tuple)) and len(range_def) >= 2:
            if len(range_def) == 2:
                # (start, end)
                ranges.append(ParamRange.range(name, range_def[0], range_def[1]))
            else:
                # (start, end, step)
                ranges.append(ParamRange.range(name, range_def[0], range_def[1], range_def[2]))
        else:
            # 离散值列表
            ranges.append(ParamRange(name=name, values=list(range_def)))

    return ranges
