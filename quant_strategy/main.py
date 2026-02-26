"""
量化策略回测系统 - 主程序

用法:
    python main.py --config config.yaml
    python main.py --strategy dual_ma --ts_code 000001.SZ
"""
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from quant_strategy.data import TushareDataProvider
from quant_strategy.strategy import (
    DualMAStrategy, MomentumStrategy,
    KDJStrategy, RSIStrategy, BOLLStrategy,
    DMIStrategy, CCIStrategy, MACDStrategy, VolumePriceStrategy,
    MarketBreadthStrategy, LimitUpStrategy, VolumeSentimentStrategy,
    FearGreedStrategy, OpenInterestStrategy
)
from quant_strategy.backtester import Backtester, BacktestConfig
from quant_strategy.analyzer import PerformanceAnalyzer, Visualizer
from quant_strategy.config import Config


def setup_logger(log_file: str = None, level: str = "INFO"):
    """配置日志"""
    logger.remove()
    logger.add(sys.stdout, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>")
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        logger.add(log_file, level=level, rotation="10 MB")


def run_backtest(config: Config):
    """运行回测"""
    # 验证配置
    config.validate()
    
    # 设置日志
    setup_logger(config.log_file, config.log_level)
    
    logger.info("=" * 50)
    logger.info("量化策略回测系统")
    logger.info("=" * 50)
    
    # 初始化数据提供者
    logger.info("初始化数据源...")
    data_provider = TushareDataProvider(
        token=config.data_source.token,
        use_cache=config.data_source.use_cache
    )
    
    # 获取股票数据
    logger.info(f"获取股票数据：{config.ts_code}")
    stock_data = data_provider.get_daily_data(
        ts_code=config.ts_code,
        start_date=config.start_date,
        end_date=config.end_date,
        adj="qfq"
    )
    
    if stock_data.empty:
        logger.error("获取股票数据失败")
        return
    
    logger.info(f"数据获取成功，共 {len(stock_data)} 条记录")
    
    # 获取基准数据
    logger.info(f"获取基准数据：{config.benchmark_code}")
    benchmark_data = data_provider.get_index_daily(
        ts_code=config.benchmark_code,
        start_date=config.start_date,
        end_date=config.end_date
    )
    
    # 初始化策略
    strategy_name = config.strategy.name
    strategy_params = config.strategy.params

    logger.info(f"初始化策略：{strategy_name}, 参数：{strategy_params}")

    # 策略工厂
    strategy_classes = {
        "dual_ma": DualMAStrategy,
        "momentum": MomentumStrategy,
        "kdj": KDJStrategy,
        "rsi": RSIStrategy,
        "boll": BOLLStrategy,
        "dmi": DMIStrategy,
        "cci": CCIStrategy,
        "macd": MACDStrategy,
        "volume_price": VolumePriceStrategy,
        "market_breadth": MarketBreadthStrategy,
        "limit_up": LimitUpStrategy,
        "volume_sentiment": VolumeSentimentStrategy,
        "fear_greed": FearGreedStrategy,
        "open_interest": OpenInterestStrategy
    }

    strategy_class = strategy_classes.get(strategy_name.lower())
    if not strategy_class:
        logger.error(f"未知策略：{strategy_name}")
        return

    strategy = strategy_class(**strategy_params)
    
    # 初始化回测引擎
    backtest_config = BacktestConfig(
        initial_cash=config.backtest.initial_cash,
        commission_rate=config.backtest.commission_rate,
        slippage_rate=config.backtest.slippage_rate,
        max_position_pct=config.backtest.max_position_pct,
        allow_short=config.backtest.allow_short
    )
    
    backtester = Backtester(backtest_config)
    
    # 运行回测
    logger.info("开始回测...")
    result = backtester.run(
        strategy=strategy,
        data=stock_data,
        ts_code=config.ts_code,
        benchmark_data=benchmark_data
    )
    
    # 输出结果
    logger.info("=" * 50)
    logger.info("回测结果")
    logger.info("=" * 50)
    
    for key, value in result.to_dict().items():
        logger.info(f"{key}: {value}")
    
    # 绩效分析
    analyzer = PerformanceAnalyzer()
    metrics = analyzer.analyze(result.daily_values, benchmark_data["close"])
    
    if metrics:
        report = analyzer.generate_report(metrics)
        logger.info(report)

    # 可视化（可选）
    if config.backtest.save_plot:
        logger.info("生成图表...")
        output_dir = Path("./output/charts")
        output_dir.mkdir(parents=True, exist_ok=True)

        visualizer = Visualizer()

        # 综合图表
        fig = visualizer.plot_comprehensive(
            daily_values=result.daily_values,
            benchmark_values=benchmark_data["close"],
            title=f"{strategy_name} 回测结果 - {config.ts_code}",
            save_path=str(output_dir / f"backtest_{config.ts_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        )

        logger.info(f"图表已保存到 {output_dir}")
    else:
        logger.info("跳过图表生成（设置 save_plot=True 启用）")

    return result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="量化策略回测系统")
    parser.add_argument("--config", type=str, default=None, help="配置文件路径")
    parser.add_argument("--strategy", type=str, default="dual_ma", 
                        choices=["dual_ma", "momentum"], help="策略名称")
    parser.add_argument("--ts_code", type=str, default="000001.SZ", help="股票代码")
    parser.add_argument("--start_date", type=str, default="20200101", help="开始日期")
    parser.add_argument("--end_date", type=str, default="20231231", help="结束日期")
    parser.add_argument("--initial_cash", type=float, default=100000, help="初始资金")
    parser.add_argument("--short_window", type=int, default=5, help="短期均线周期 (双均线策略)")
    parser.add_argument("--long_window", type=int, default=20, help="长期均线周期 (双均线策略)")
    
    args = parser.parse_args()
    
    # 加载配置
    if args.config and Path(args.config).exists():
        config = Config.from_yaml(args.config)
    else:
        config = Config()
        
        # 从命令行参数覆盖配置
        config.data_source.token = os.getenv("TUSHARE_TOKEN", "")
        config.strategy.name = args.strategy
        config.ts_code = args.ts_code
        config.start_date = args.start_date
        config.end_date = args.end_date
        config.backtest.initial_cash = args.initial_cash
        
        if args.strategy == "dual_ma":
            config.strategy.params = {
                "short_window": args.short_window,
                "long_window": args.long_window
            }
    
    # 运行回测
    run_backtest(config)


if __name__ == "__main__":
    main()
