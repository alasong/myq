"""
命令行接口模块
提供丰富的 CLI 命令用于策略管理、数据查询、回测等
"""
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

import pandas as pd
from loguru import logger

# 配置日志输出到控制台
logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>")


def list_strategies():
    """列出所有可用策略"""
    from quant_strategy.strategy import (
        DualMAStrategy, MomentumStrategy,
        KDJStrategy, RSIStrategy, BOLLStrategy,
        DMIStrategy, CCIStrategy, MACDStrategy, VolumePriceStrategy,
        MarketBreadthStrategy, LimitUpStrategy, VolumeSentimentStrategy,
        FearGreedStrategy, OpenInterestStrategy
    )
    from quant_strategy.strategy import (
        SectorMomentumRotationStrategy, SectorFlowStrategy,
        FirstLimitUpStrategy, ContinuousLimitUpStrategy, LimitUpPullbackStrategy
    )

    strategies = {
        # 经典策略
        "dual_ma": {
            "class": DualMAStrategy,
            "name": "双均线策略",
            "description": "基于短期和长期均线交叉产生交易信号",
            "params": {
                "short_window": {"type": int, "default": 5, "desc": "短期均线周期"},
                "long_window": {"type": int, "default": 20, "desc": "长期均线周期"}
            }
        },
        "momentum": {
            "class": MomentumStrategy,
            "name": "动量策略",
            "description": "基于动量因子和 RSI 指标的交易策略",
            "params": {
                "lookback_period": {"type": int, "default": 20, "desc": "动量计算周期"},
                "rsi_period": {"type": int, "default": 14, "desc": "RSI 计算周期"},
                "rsi_oversold": {"type": float, "default": 30, "desc": "RSI 超卖阈值"},
                "rsi_overbought": {"type": float, "default": 70, "desc": "RSI 超买阈值"}
            }
        },
        # 短线策略
        "kdj": {
            "class": KDJStrategy,
            "name": "KDJ 短线策略",
            "description": "基于 KDJ 指标的超买超卖信号",
            "params": {
                "n": {"type": int, "default": 9, "desc": "KDJ 计算周期"},
                "m1": {"type": int, "default": 3, "desc": "K 值平滑周期"},
                "m2": {"type": int, "default": 3, "desc": "D 值平滑周期"},
                "oversold": {"type": float, "default": 20, "desc": "超卖阈值"},
                "overbought": {"type": float, "default": 80, "desc": "超买阈值"}
            }
        },
        "rsi": {
            "class": RSIStrategy,
            "name": "RSI 短线策略",
            "description": "基于 RSI 指标的超买超卖信号",
            "params": {
                "period": {"type": int, "default": 6, "desc": "RSI 计算周期"},
                "oversold": {"type": float, "default": 30, "desc": "超卖阈值"},
                "overbought": {"type": float, "default": 70, "desc": "超买阈值"}
            }
        },
        "boll": {
            "class": BOLLStrategy,
            "name": "布林线策略",
            "description": "基于布林带的均值回归信号",
            "params": {
                "period": {"type": int, "default": 20, "desc": "均线周期"},
                "num_std": {"type": float, "default": 2.0, "desc": "标准差倍数"}
            }
        },
        "dmi": {
            "class": DMIStrategy,
            "name": "DMI 趋势策略",
            "description": "基于 DMI 指标的趋势强度信号",
            "params": {
                "period": {"type": int, "default": 14, "desc": "DMI 计算周期"},
                "adx_period": {"type": int, "default": 14, "desc": "ADX 平滑周期"}
            }
        },
        "cci": {
            "class": CCIStrategy,
            "name": "CCI 顺势策略",
            "description": "基于 CCI 指标的超买超卖信号",
            "params": {
                "period": {"type": int, "default": 14, "desc": "CCI 计算周期"},
                "oversold": {"type": float, "default": -100, "desc": "超卖阈值"},
                "overbought": {"type": float, "default": 100, "desc": "超买阈值"}
            }
        },
        "macd": {
            "class": MACDStrategy,
            "name": "MACD 策略",
            "description": "基于 MACD 金叉死叉信号",
            "params": {
                "fast": {"type": int, "default": 12, "desc": "快线周期"},
                "slow": {"type": int, "default": 26, "desc": "慢线周期"},
                "signal": {"type": int, "default": 9, "desc": "信号线周期"}
            }
        },
        "volume_price": {
            "class": VolumePriceStrategy,
            "name": "量价策略",
            "description": "基于成交量和价格的配合",
            "params": {
                "vol_period": {"type": int, "default": 5, "desc": "成交量均线周期"},
                "price_period": {"type": int, "default": 10, "desc": "价格均线周期"},
                "vol_ratio": {"type": float, "default": 1.5, "desc": "放量倍数"},
                "price_change": {"type": float, "default": 0.03, "desc": "价格变化阈值"}
            }
        },
        # 情绪策略
        "market_breadth": {
            "class": MarketBreadthStrategy,
            "name": "市场广度策略",
            "description": "基于涨跌比（ADR）的情绪指标",
            "params": {
                "lookback": {"type": int, "default": 20, "desc": "历史数据周期"},
                "adr_period": {"type": int, "default": 5, "desc": "涨跌比移动平均周期"},
                "high_threshold": {"type": float, "default": 2.0, "desc": "超买阈值"},
                "low_threshold": {"type": float, "default": 0.5, "desc": "超卖阈值"}
            },
            "note": "需要全市场数据"
        },
        "limit_up": {
            "class": LimitUpStrategy,
            "name": "涨停情绪策略",
            "description": "基于涨停家数占比判断市场情绪",
            "params": {
                "lookback": {"type": int, "default": 20, "desc": "历史数据周期"},
                "high_threshold": {"type": float, "default": 0.05, "desc": "涨停占比高阈值"},
                "low_threshold": {"type": float, "default": 0.01, "desc": "涨停占比低阈值"}
            },
            "note": "需要全市场数据"
        },
        "volume_sentiment": {
            "class": VolumeSentimentStrategy,
            "name": "成交量情绪策略",
            "description": "基于成交量变化判断情绪",
            "params": {
                "vol_period": {"type": int, "default": 20, "desc": "成交量均线周期"},
                "high_vol_ratio": {"type": float, "default": 2.0, "desc": "放量倍数"},
                "low_vol_ratio": {"type": float, "default": 0.5, "desc": "缩量倍数"}
            }
        },
        "fear_greed": {
            "class": FearGreedStrategy,
            "name": "恐惧贪婪策略",
            "description": "综合多个情绪指标计算恐惧贪婪指数",
            "params": {
                "lookback": {"type": int, "default": 20, "desc": "历史数据周期"},
                "rsi_period": {"type": int, "default": 14, "desc": "RSI 计算周期"}
            }
        },
        "open_interest": {
            "class": OpenInterestStrategy,
            "name": "开盘情绪策略",
            "description": "基于开盘价和跳空缺口判断情绪",
            "params": {
                "gap_threshold": {"type": float, "default": 0.02, "desc": "跳空阈值"},
                "vol_period": {"type": int, "default": 20, "desc": "成交量均线周期"}
            }
        },
        # 板块轮动策略
        "sector_momentum": {
            "class": SectorMomentumRotationStrategy,
            "name": "板块动量轮动策略",
            "description": "基于板块动量排名进行轮动交易",
            "params": {
                "lookback": {"type": int, "default": 20, "desc": "动量计算周期"},
                "top_k": {"type": int, "default": 3, "desc": "选择板块数量"},
                "rebalance_days": {"type": int, "default": 5, "desc": "调仓周期"}
            },
            "note": "需要板块数据"
        },
        "sector_flow": {
            "class": SectorFlowStrategy,
            "name": "板块资金流向策略",
            "description": "跟随主力资金流向进行板块配置",
            "params": {
                "flow_lookback": {"type": int, "default": 5, "desc": "资金流计算周期"},
                "top_k": {"type": int, "default": 3, "desc": "选择板块数量"}
            },
            "note": "需要板块数据"
        },
        # 打板策略
        "first_limit_up": {
            "class": FirstLimitUpStrategy,
            "name": "首板打板策略",
            "description": "识别首次涨停股票，次日高开时买入",
            "params": {
                "min_close_ratio": {"type": float, "default": 0.095, "desc": "涨停阈值"},
                "min_volume_ratio": {"type": float, "default": 1.5, "desc": "最小放量倍数"},
                "hold_days": {"type": int, "default": 3, "desc": "最大持有期"},
                "stop_loss": {"type": float, "default": 0.05, "desc": "止损比例"},
                "take_profit": {"type": float, "default": 0.15, "desc": "止盈比例"}
            }
        },
        "continuous_limit_up": {
            "class": ContinuousLimitUpStrategy,
            "name": "连板打板策略",
            "description": "捕捉 N 连板股票，博弈继续涨停",
            "params": {
                "target_continuous": {"type": int, "default": 2, "desc": "目标连板数"},
                "max_hold_days": {"type": int, "default": 5, "desc": "最大持有期"}
            }
        },
        "limit_up_pullback": {
            "class": LimitUpPullbackStrategy,
            "name": "涨停回马枪策略",
            "description": "博弈涨停股回调后的第二波拉升",
            "params": {
                "limit_up_lookback": {"type": int, "default": 10, "desc": "涨停回溯期"},
                "pullback_days": {"type": int, "default": 5, "desc": "回调天数"},
                "hold_days": {"type": int, "default": 5, "desc": "持有期"}
            }
        }
    }
    
    print("\n" + "=" * 70)
    print("可用策略列表")
    print("=" * 70)

    print("\n【经典策略】")
    for name in ["dual_ma", "momentum"]:
        info = strategies[name]
        print(f"  {name:16} - {info['name']}")

    print("\n【短线策略】")
    for name in ["kdj", "rsi", "boll", "dmi", "cci", "macd", "volume_price"]:
        info = strategies[name]
        print(f"  {name:16} - {info['name']}")

    print("\n【情绪策略】")
    for name in ["market_breadth", "limit_up", "volume_sentiment", "fear_greed", "open_interest"]:
        info = strategies[name]
        note = f" ({info['note']})" if "note" in info else ""
        print(f"  {name:16} - {info['name']}{note}")

    print("\n【板块轮动策略】")
    for name in ["sector_momentum", "sector_flow"]:
        info = strategies[name]
        note = f" ({info['note']})" if "note" in info else ""
        print(f"  {name:16} - {info['name']}{note}")

    print("\n【打板策略】")
    for name in ["first_limit_up", "continuous_limit_up", "limit_up_pullback"]:
        info = strategies[name]
        print(f"  {name:16} - {info['name']}")

    print("\n" + "=" * 70)
    print(f"共 {len(strategies)} 个策略")
    print("=" * 70)

    return list(strategies.keys())


def list_stocks(ts_provider, exchange: str = None, limit: int = 20):
    """列出股票列表"""
    df = ts_provider.get_stock_list(exchange=exchange)
    
    print("\n" + "=" * 100)
    if exchange:
        print(f"股票列表 ({exchange})")
    else:
        print("股票列表 (全部)")
    print("=" * 100)
    
    display_df = df.head(limit) if limit else df
    
    # 格式化显示
    for _, row in display_df.iterrows():
        print(f"  {row['ts_code']:12} | {row['name']:15} | {row.get('area', 'N/A'):10} | {row.get('industry', 'N/A'):15}")
    
    print("=" * 100)
    print(f"共 {len(df)} 只股票，显示前 {len(display_df)} 只")
    print("=" * 100)
    
    return df


def list_indices(ts_provider):
    """列出主要指数"""
    indices = {
        "000001.SH": "上证指数",
        "399001.SZ": "深证成指",
        "399006.SZ": "创业板指",
        "000016.SH": "上证 50",
        "000300.SH": "沪深 300",
        "000905.SH": "中证 500",
        "000852.SH": "中证 1000"
    }
    
    print("\n" + "=" * 50)
    print("主要指数")
    print("=" * 50)
    
    for code, name in indices.items():
        print(f"  {code:12} | {name}")
    
    print("=" * 50)
    
    return indices


def list_industries(ts_provider):
    """列出行业板块"""
    df = ts_provider.get_industry_list()
    
    print("\n" + "=" * 70)
    print("行业板块列表")
    print("=" * 70)
    
    if df is not None and not df.empty:
        for _, row in df.head(50).iterrows():
            print(f"  {row.get('ts_code', 'N/A'):12} | {row.get('name', 'N/A'):20}")
        print(f"\n共 {len(df)} 个行业板块，显示前 50 个")
    else:
        print("暂无数据")
    
    print("=" * 70)
    
    return df


def list_concepts(ts_provider):
    """列出概念板块"""
    df = ts_provider.get_concept_list()
    
    print("\n" + "=" * 70)
    print("概念板块列表")
    print("=" * 70)
    
    if df is not None and not df.empty:
        for _, row in df.head(50).iterrows():
            print(f"  {row.get('ts_code', 'N/A'):12} | {row.get('name', 'N/A'):20}")
        print(f"\n共 {len(df)} 个概念板块，显示前 50 个")
    else:
        print("暂无数据")
    
    print("=" * 70)
    
    return df


def show_stock_info(ts_provider, ts_code: str):
    """显示股票详细信息"""
    df = ts_provider.get_stock_info(ts_code)
    
    print("\n" + "=" * 50)
    print(f"股票信息：{ts_code}")
    print("=" * 50)
    
    if df is not None and not df.empty:
        info = df.iloc[0]
        for col in df.columns:
            print(f"  {col:15}: {info.get(col, 'N/A')}")
    else:
        print("暂无数据")
    
    print("=" * 50)
    
    return df


def show_stock_industry(ts_provider, ts_code: str):
    """显示股票所属行业板块"""
    df = ts_provider.get_stock_industry(ts_code)
    
    print("\n" + "=" * 50)
    print(f"股票行业板块：{ts_code}")
    print("=" * 50)
    
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            print(f"  {row.get('ts_code', 'N/A'):12} | {row.get('industry', 'N/A'):20}")
    else:
        print("暂无数据")
    
    print("=" * 50)
    
    return df


def show_industry_stocks(ts_provider, industry: str):
    """显示某行业包含的股票"""
    df = ts_provider.get_industry_stocks(industry)
    
    print("\n" + "=" * 70)
    print(f"行业股票列表：{industry}")
    print("=" * 70)
    
    if df is not None and not df.empty:
        for _, row in df.head(50).iterrows():
            print(f"  {row['ts_code']:12} | {row['name']:15}")
        print(f"\n共 {len(df)} 只股票，显示前 50 只")
    else:
        print("暂无数据")
    
    print("=" * 70)
    
    return df


def show_concept_stocks(ts_provider, concept: str):
    """显示某概念包含的股票"""
    df = ts_provider.get_concept_stocks(concept)
    
    print("\n" + "=" * 70)
    print(f"概念股票列表：{concept}")
    print("=" * 70)
    
    if df is not None and not df.empty:
        for _, row in df.head(50).iterrows():
            print(f"  {row['ts_code']:12} | {row['name']:15}")
        print(f"\n共 {len(df)} 只股票，显示前 50 只")
    else:
        print("暂无数据")
    
    print("=" * 70)
    
    return df


def download_data(ts_provider, ts_codes: List[str], start_date: str, end_date: str, adj: str = "qfq"):
    """批量下载数据到本地缓存"""
    from tqdm import tqdm
    
    print("\n" + "=" * 70)
    print(f"批量下载数据：{len(ts_codes)} 只股票")
    print(f"日期范围：{start_date} - {end_date}")
    print(f"复权类型：{adj}")
    print("=" * 70)
    
    success_count = 0
    failed_codes = []
    
    for ts_code in tqdm(ts_codes, desc="下载进度"):
        try:
            df = ts_provider.get_daily_data(ts_code, start_date, end_date, adj=adj)
            if not df.empty:
                success_count += 1
            else:
                failed_codes.append(ts_code)
        except Exception as e:
            logger.error(f"下载失败 {ts_code}: {e}")
            failed_codes.append(ts_code)
    
    print("\n" + "=" * 70)
    print(f"下载完成：成功 {success_count}/{len(ts_codes)}")
    if failed_codes:
        print(f"失败：{', '.join(failed_codes[:10])}{'...' if len(failed_codes) > 10 else ''}")
    print("=" * 70)
    
    return success_count, failed_codes


def list_cache(data_type: str = None, ts_code: str = None):
    """列出本地缓存数据"""
    from quant_strategy.data import DataCache
    
    cache = DataCache()
    df = cache.list_cache(data_type=data_type, ts_code=ts_code)
    
    print("\n" + "=" * 100)
    print("本地缓存数据列表")
    print("=" * 100)
    
    if df.empty:
        print("缓存为空")
    else:
        # 格式化显示
        for _, row in df.iterrows():
            print(f"  {row['ts_code']:12} | {row['data_type']:15} | {row['start_date'] or 'N/A':10} - {row['end_date'] or 'N/A':10} | {row['size_mb']:>8} MB")
        
        print("=" * 100)
        print(f"共 {len(df)} 条缓存记录")
    
    print("=" * 100)
    
    return df


def show_cache_stats():
    """显示缓存统计信息"""
    from quant_strategy.data import DataCache
    
    cache = DataCache()
    stats = cache.get_cache_stats()
    
    print("\n" + "=" * 50)
    print("缓存统计信息")
    print("=" * 50)
    print(f"  总文件数：   {stats['total_files']}")
    print(f"  总大小：     {stats['total_size_mb']} MB")
    print(f"  股票数量：   {stats['stock_count']}")
    print("  数据类型分布:")
    for data_type, count in stats.get('data_types', {}).items():
        print(f"    - {data_type}: {count}")
    print("=" * 50)
    
    return stats


def scan_stocks(ts_provider, strategy_class, ts_codes: List[str], 
                start_date: str, end_date: str, params: dict = None):
    """多股票策略扫描"""
    from tqdm import tqdm
    from quant_strategy.backtester import Backtester, BacktestConfig
    
    print("\n" + "=" * 70)
    print("策略扫描器")
    print(f"策略：{strategy_class.__name__}")
    print(f"股票数量：{len(ts_codes)}")
    print(f"日期范围：{start_date} - {end_date}")
    print("=" * 70)
    
    results = []
    
    for ts_code in tqdm(ts_codes, desc="扫描进度"):
        try:
            # 获取数据
            data = ts_provider.get_daily_data(ts_code, start_date, end_date, adj="qfq")
            if data.empty:
                continue
            
            # 初始化策略
            strategy = strategy_class(**(params or {}))
            
            # 初始化回测
            config = BacktestConfig()
            backtester = Backtester(config)
            backtester.ts_code = ts_code
            backtester.strategy = strategy
            
            # 运行回测
            result = backtester.run_single_stock(strategy, data)
            
            if result:
                results.append({
                    "ts_code": ts_code,
                    "total_return": result.total_return,
                    "sharpe_ratio": result.sharpe_ratio,
                    "max_drawdown": result.max_drawdown
                })
        except Exception as e:
            logger.debug(f"扫描失败 {ts_code}: {e}")
    
    # 排序并显示结果
    if results:
        results.sort(key=lambda x: x["total_return"], reverse=True)
        
        print("\n" + "=" * 70)
        print("扫描结果 (按收益率排序)")
        print("=" * 70)
        print(f"{'代码':12} | {'收益率':>10} | {'夏普':>8} | {'最大回撤':>10}")
        print("-" * 50)
        
        for r in results[:20]:  # 显示前 20
            print(f"{r['ts_code']:12} | {r['total_return']:>9.2%} | {r['sharpe_ratio']:>8.2f} | {r['max_drawdown']:>9.2%}")
        
        print("=" * 70)
    
    return results


def create_main_parser():
    """创建主解析器"""
    parser = argparse.ArgumentParser(
        description="量化策略回测系统",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # ===== 策略相关命令 =====
    # strategies
    subparsers.add_parser("strategies", help="列出所有可用策略")
    
    # ===== 数据相关命令 =====
    data_parser = subparsers.add_parser("data", help="数据相关操作")
    data_subparsers = data_parser.add_subparsers(dest="data_command")
    
    # data list-stocks
    list_stocks_parser = data_subparsers.add_parser("list-stocks", help="列出股票")
    list_stocks_parser.add_argument("--exchange", choices=["SSE", "SZSE", "BJSE"], help="交易所")
    list_stocks_parser.add_argument("--limit", type=int, default=20, help="显示数量")
    
    # data list-indices
    data_subparsers.add_parser("list-indices", help="列出主要指数")
    
    # data list-industries
    data_subparsers.add_parser("list-industries", help="列出行业板块")
    
    # data list-concepts
    data_subparsers.add_parser("list-concepts", help="列出概念板块")
    
    # data stock-info
    stock_info_parser = data_subparsers.add_parser("stock-info", help="显示股票信息")
    stock_info_parser.add_argument("--ts_code", required=True, help="股票代码")
    
    # data stock-industry
    stock_industry_parser = data_subparsers.add_parser("stock-industry", help="显示股票所属行业")
    stock_industry_parser.add_argument("--ts_code", required=True, help="股票代码")
    
    # data industry-stocks
    industry_stocks_parser = data_subparsers.add_parser("industry-stocks", help="显示行业包含的股票")
    industry_stocks_parser.add_argument("--industry", required=True, help="行业名称")
    
    # data concept-stocks
    concept_stocks_parser = data_subparsers.add_parser("concept-stocks", help="显示概念包含的股票")
    concept_stocks_parser.add_argument("--concept", required=True, help="概念名称")
    
    # data download
    download_parser = data_subparsers.add_parser("download", help="批量下载数据")
    download_parser.add_argument("--ts_codes", nargs="+", required=True, help="股票代码列表")
    download_parser.add_argument("--start_date", required=True, help="开始日期 YYYYMMDD")
    download_parser.add_argument("--end_date", required=True, help="结束日期 YYYYMMDD")
    download_parser.add_argument("--adj", default="qfq", choices=["qfq", "hfq", "none"], help="复权类型")

    # data list-cache
    list_cache_parser = data_subparsers.add_parser("list-cache", help="列出本地缓存数据")
    list_cache_parser.add_argument("--data_type", help="数据类型过滤")
    list_cache_parser.add_argument("--ts_code", help="股票代码过滤")

    # data cache-stats
    data_subparsers.add_parser("cache-stats", help="显示缓存统计信息")

    # data scan
    scan_parser = data_subparsers.add_parser("scan", help="策略扫描器")
    scan_parser.add_argument("--strategy", required=True, choices=[
        "dual_ma", "momentum", "kdj", "rsi", "boll", "dmi", "cci", "macd",
        "volume_price", "volume_sentiment", "fear_greed", "open_interest"
    ], help="策略名称")
    scan_parser.add_argument("--ts_codes", nargs="+", required=True, help="股票代码列表")
    scan_parser.add_argument("--start_date", required=True, help="开始日期 YYYYMMDD")
    scan_parser.add_argument("--end_date", required=True, help="结束日期 YYYYMMDD")

    # ===== 优化命令 =====
    optimize_parser = subparsers.add_parser("optimize", help="参数优化")
    optimize_parser.add_argument("--strategy", required=True, choices=[
        "dual_ma", "momentum", "kdj", "rsi", "boll", "dmi", "cci", "macd",
        "volume_price", "volume_sentiment", "fear_greed", "open_interest"
    ], help="策略名称")
    optimize_parser.add_argument("--ts_code", required=True, help="股票代码")
    optimize_parser.add_argument("--start_date", default="20200101", help="开始日期")
    optimize_parser.add_argument("--end_date", default="20231231", help="结束日期")
    optimize_parser.add_argument("--method", default="grid", choices=["grid", "random", "bayesian"], help="优化方法")
    optimize_parser.add_argument("--n_iterations", type=int, default=50, help="迭代次数 (随机/贝叶斯搜索)")
    optimize_parser.add_argument("--n_trials", type=int, default=50, help="贝叶斯优化试验次数")

    # ===== 回测命令 =====
    backtest_parser = subparsers.add_parser("backtest", help="运行回测")
    backtest_parser.add_argument("--strategy", type=str, default="dual_ma", help="策略名称")
    backtest_parser.add_argument("--ts_code", type=str, required=True, help="股票代码")
    backtest_parser.add_argument("--start_date", type=str, default="20200101", help="开始日期")
    backtest_parser.add_argument("--end_date", type=str, default="20231231", help="结束日期")
    backtest_parser.add_argument("--config", type=str, help="配置文件路径")
    backtest_parser.add_argument("--export", choices=["html", "md", "both"], help="导出报告格式")
    backtest_parser.add_argument("--save_plot", action="store_true", help="是否保存图表")

    # ===== 板块/组合回测命令 =====
    sector_backtest_parser = subparsers.add_parser("sector-backtest", help="板块/组合回测")
    sector_backtest_parser.add_argument("--strategy", required=True, help="策略名称")
    sector_backtest_parser.add_argument("--sector_type", choices=["industry", "concept", "area", "custom"],
                                        help="板块类型")
    sector_backtest_parser.add_argument("--sector_name", help="板块名称")
    sector_backtest_parser.add_argument("--ts_codes", nargs="+", help="自定义股票列表")
    sector_backtest_parser.add_argument("--start_date", default="20200101", help="开始日期")
    sector_backtest_parser.add_argument("--end_date", default="20231231", help="结束日期")
    sector_backtest_parser.add_argument("--workers", type=int, help="并发工作进程数")
    sector_backtest_parser.add_argument("--use_processes", action="store_true", help="使用多进程（否则多线程）")

    # ===== 多策略对比命令 =====
    compare_parser = subparsers.add_parser("compare", help="多策略对比回测")
    compare_parser.add_argument("--strategies", nargs="+", required=True, help="策略名称列表")
    compare_parser.add_argument("--ts_code", required=True, help="股票代码")
    compare_parser.add_argument("--start_date", default="20200101", help="开始日期")
    compare_parser.add_argument("--end_date", default="20231231", help="结束日期")
    compare_parser.add_argument("--workers", type=int, help="并发工作进程数")

    # ===== 策略管理命令 =====
    strategy_parser = subparsers.add_parser("strategy", help="策略管理")
    strategy_subparsers = strategy_parser.add_subparsers(dest="strategy_command")

    # strategy list
    strategy_subparsers.add_parser("list", help="列出策略状态")

    # strategy enable
    enable_parser = strategy_subparsers.add_parser("enable", help="激活策略")
    enable_parser.add_argument("--name", required=True, help="策略名称")

    # strategy disable
    disable_parser = strategy_subparsers.add_parser("disable", help="停用策略")
    disable_parser.add_argument("--name", required=True, help="策略名称")
    disable_parser.add_argument("--reason", default="", help="停用原因")

    # ===== 批量回测命令 =====
    batch_backtest_parser = subparsers.add_parser("batch-backtest", help="激活策略批量回测")
    batch_backtest_parser.add_argument("--ts_code", required=True, help="股票代码")
    batch_backtest_parser.add_argument("--start_date", default="20200101", help="开始日期")
    batch_backtest_parser.add_argument("--end_date", default="20231231", help="结束日期")
    batch_backtest_parser.add_argument("--workers", type=int, default=4, help="并发工作进程数")
    batch_backtest_parser.add_argument("--show-details", action="store_true", help="显示详细结果")

    return parser


def main():
    """CLI 入口函数"""
    parser = create_main_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 导入数据提供者
    from quant_strategy.data import create_data_provider, MultiSourceDataProvider
    from quant_strategy.config import Config

    # 加载配置
    config = Config()
    config.data_source.token = config.data_source.token or os.getenv("TUSHARE_TOKEN", "")

    # 创建数据提供者（支持多数据源自动切换）
    ts_provider = None
    data_source_type = os.getenv("DATA_SOURCE", "auto")  # 可通过环境变量配置
    
    try:
        ts_provider = create_data_provider(
            source=data_source_type,
            tushare_token=config.data_source.token,
            use_cache=config.data_source.use_cache,
            cache_dir=config.data_source.cache_dir
        )
        logger.info(f"数据提供者初始化：{data_source_type}")
    except Exception as e:
        logger.error(f"数据提供者初始化失败：{e}")

    # 处理命令
    if args.command == "strategies":
        list_strategies()

    elif args.command == "data":
        if not ts_provider:
            logger.error("请先设置 TUSHARE_TOKEN 环境变量")
            return

        if args.data_command == "list-stocks":
            list_stocks(ts_provider, getattr(args, 'exchange', None), args.limit)

        elif args.data_command == "list-indices":
            list_indices(ts_provider)

        elif args.data_command == "list-industries":
            list_industries(ts_provider)

        elif args.data_command == "list-concepts":
            list_concepts(ts_provider)

        elif args.data_command == "stock-info":
            show_stock_info(ts_provider, args.ts_code)

        elif args.data_command == "stock-industry":
            show_stock_industry(ts_provider, args.ts_code)

        elif args.data_command == "industry-stocks":
            show_industry_stocks(ts_provider, args.industry)

        elif args.data_command == "concept-stocks":
            show_concept_stocks(ts_provider, args.concept)

        elif args.data_command == "download":
            download_data(ts_provider, args.ts_codes, args.start_date, args.end_date, args.adj)

        elif args.data_command == "list-cache":
            list_cache(args.data_type, args.ts_code)

        elif args.data_command == "cache-stats":
            show_cache_stats()

        elif args.data_command == "scan":
            from quant_strategy.strategy import (
                DualMAStrategy, MomentumStrategy,
                KDJStrategy, RSIStrategy, BOLLStrategy,
                DMIStrategy, CCIStrategy, MACDStrategy, VolumePriceStrategy
            )

            from quant_strategy.strategy import (
                DualMAStrategy, MomentumStrategy,
                KDJStrategy, RSIStrategy, BOLLStrategy,
                DMIStrategy, CCIStrategy, MACDStrategy, VolumePriceStrategy,
                VolumeSentimentStrategy, FearGreedStrategy, OpenInterestStrategy
            )

            strategy_map = {
                "dual_ma": DualMAStrategy,
                "momentum": MomentumStrategy,
                "kdj": KDJStrategy,
                "rsi": RSIStrategy,
                "boll": BOLLStrategy,
                "dmi": DMIStrategy,
                "cci": CCIStrategy,
                "macd": MACDStrategy,
                "volume_price": VolumePriceStrategy,
                "volume_sentiment": VolumeSentimentStrategy,
                "fear_greed": FearGreedStrategy,
                "open_interest": OpenInterestStrategy
            }
            strategy_class = strategy_map.get(args.strategy)

            if strategy_class:
                scan_stocks(ts_provider, strategy_class, args.ts_codes,
                           args.start_date, args.end_date)

        elif args.data_command is None:
            parser.parse_args(["data", "--help"])

    elif args.command == "optimize":
        # 参数优化
        if not ts_provider:
            logger.error("请先设置 TUSHARE_TOKEN 环境变量")
            return

        from quant_strategy.strategy import (
            DualMAStrategy, MomentumStrategy,
            KDJStrategy, RSIStrategy, BOLLStrategy,
            DMIStrategy, CCIStrategy, MACDStrategy, VolumePriceStrategy,
            VolumeSentimentStrategy, FearGreedStrategy, OpenInterestStrategy
        )
        from quant_strategy.optimizer import ParamOptimizer, ParamRange
        from quant_strategy.backtester import BacktestConfig

        strategy_map = {
            "dual_ma": DualMAStrategy,
            "momentum": MomentumStrategy,
            "kdj": KDJStrategy,
            "rsi": RSIStrategy,
            "boll": BOLLStrategy,
            "dmi": DMIStrategy,
            "cci": CCIStrategy,
            "macd": MACDStrategy,
            "volume_price": VolumePriceStrategy,
            "volume_sentiment": VolumeSentimentStrategy,
            "fear_greed": FearGreedStrategy,
            "open_interest": OpenInterestStrategy
        }
        strategy_class = strategy_map.get(args.strategy)

        if not strategy_class:
            logger.error(f"未知策略：{args.strategy}")
            return

        # 获取数据
        data = ts_provider.get_daily_data(args.ts_code, args.start_date, args.end_date, adj="qfq")
        if data.empty:
            logger.error("获取数据失败")
            return

        # 定义参数范围（根据策略）
        param_ranges_map = {
            "dual_ma": [
                ParamRange.range("short_window", 3, 10),
                ParamRange.range("long_window", 15, 30)
            ],
            "momentum": [
                ParamRange.range("lookback_period", 10, 30),
                ParamRange.range("rsi_period", 10, 20)
            ],
            "kdj": [
                ParamRange.range("n", 6, 12),
                ParamRange.range("oversold", 15, 25)
            ],
            "rsi": [
                ParamRange.range("period", 5, 10),
                ParamRange.range("oversold", 25, 35)
            ],
            "boll": [
                ParamRange.range("period", 18, 26),
                ParamRange.range("num_std", 1.5, 2.5)
            ],
            "dmi": [
                ParamRange.range("period", 10, 18),
            ],
            "cci": [
                ParamRange.range("period", 10, 20),
            ],
            "macd": [
                ParamRange.range("fast", 8, 16),
                ParamRange.range("slow", 20, 32)
            ],
            "volume_price": [
                ParamRange.range("vol_period", 3, 8),
                ParamRange.range("vol_ratio", 1.2, 2.0)
            ],
            "volume_sentiment": [
                ParamRange.range("vol_period", 15, 30),
                ParamRange.range("high_vol_ratio", 1.5, 3.0)
            ],
            "fear_greed": [
                ParamRange.range("lookback", 15, 30),
                ParamRange.range("rsi_period", 10, 20)
            ],
            "open_interest": [
                ParamRange.range("gap_threshold", 0.015, 0.03),
                ParamRange.range("vol_period", 15, 25)
            ]
        }
        
        param_ranges = param_ranges_map.get(args.strategy, [])

        # 运行优化
        optimizer = ParamOptimizer(strategy_class, data, args.ts_code)

        if args.method == "grid":
            result = optimizer.grid_search(param_ranges)
        elif args.method == "random":
            result = optimizer.random_search(param_ranges, n_iterations=args.n_iterations)
        elif args.method == "bayesian":
            result = optimizer.bayesian_search(param_ranges, n_trials=args.n_trials)
        else:
            logger.error(f"未知优化方法：{args.method}")
            return

        print(result.summary())

    elif args.command == "backtest":
        # 运行回测
        from quant_strategy.main import run_backtest
        from quant_strategy.analyzer import ReportExporter

        if args.config:
            config = Config.from_yaml(args.config)
        else:
            config.strategy.name = args.strategy
            config.ts_code = args.ts_code
            config.start_date = args.start_date
            config.end_date = args.end_date
            config.backtest.save_plot = args.save_plot

        result = run_backtest(config)

        # 导出报告
        if args.export and result:
            exporter = ReportExporter()
            if args.export in ["html", "both"]:
                exporter.export_html(result)
            if args.export in ["md", "both"]:
                exporter.export_markdown(result)

    elif args.command == "sector-backtest":
        # 板块/组合回测
        if not ts_provider:
            logger.error("请先设置 TUSHARE_TOKEN 环境变量")
            return

        from quant_strategy.strategy import (
            DualMAStrategy, MomentumStrategy,
            KDJStrategy, RSIStrategy, BOLLStrategy,
            DMIStrategy, CCIStrategy, MACDStrategy, VolumePriceStrategy,
            VolumeSentimentStrategy, FearGreedStrategy, OpenInterestStrategy
        )
        from quant_strategy.backtester import ParallelBacktester, BacktestConfig

        strategy_map = {
            "dual_ma": DualMAStrategy,
            "momentum": MomentumStrategy,
            "kdj": KDJStrategy,
            "rsi": RSIStrategy,
            "boll": BOLLStrategy,
            "dmi": DMIStrategy,
            "cci": CCIStrategy,
            "macd": MACDStrategy,
            "volume_price": VolumePriceStrategy,
            "volume_sentiment": VolumeSentimentStrategy,
            "fear_greed": FearGreedStrategy,
            "open_interest": OpenInterestStrategy
        }
        strategy_class = strategy_map.get(args.strategy)

        if not strategy_class:
            logger.error(f"未知策略：{args.strategy}")
            return

        # 获取股票列表
        ts_codes = []
        if args.sector_type == "custom":
            if not args.ts_codes:
                logger.error("自定义模式需要指定 --ts_codes")
                return
            ts_codes = args.ts_codes
        else:
            # 从板块获取股票
            if args.sector_type == "industry":
                df = ts_provider.get_industry_stocks(industry_name=args.sector_name)
            elif args.sector_type == "concept":
                df = ts_provider.get_concept_stocks(concept_name=args.sector_name)
            elif args.sector_type == "area":
                from quant_strategy.data import SectorDataProvider
                sector_provider = SectorDataProvider(ts_provider.token)
                df = sector_provider.get_area_stocks(area=args.sector_name)
            else:
                logger.error(f"未知板块类型：{args.sector_type}")
                return

            if df is not None and not df.empty:
                ts_codes = df["ts_code"].tolist()[:50]  # 限制 50 只
                logger.info(f"板块包含 {len(ts_codes)} 只股票")
            else:
                logger.error("未获取到板块成分股")
                return

        # 执行并行回测
        backtester = ParallelBacktester(
            max_workers=args.workers,
            use_processes=args.use_processes
        )

        results = backtester.backtest_sector(
            strategy_class=strategy_class,
            ts_codes=ts_codes,
            data_provider=ts_provider,
            start_date=args.start_date,
            end_date=args.end_date,
            show_progress=True
        )

        # 汇总结果
        print("\n" + "=" * 80)
        print("板块回测结果汇总")
        print("=" * 80)

        summary_data = []
        for ts_code, task_result in results.items():
            if task_result.result:
                summary_data.append({
                    "代码": ts_code,
                    "收益率": f"{task_result.result.total_return:.2%}",
                    "夏普": f"{task_result.result.sharpe_ratio:.2f}",
                    "最大回撤": f"{task_result.result.max_drawdown:.2%}",
                    "交易次数": task_result.result.total_trades
                })

        if summary_data:
            summary_df = pd.DataFrame(summary_data)
            summary_df = summary_df.sort_values("收益率", ascending=False)
            print(summary_df.to_string(index=False))
        print("=" * 80)

    elif args.command == "compare":
        # 多策略对比回测
        if not ts_provider:
            logger.error("请先设置 TUSHARE_TOKEN 环境变量")
            return

        from quant_strategy.strategy import (
            DualMAStrategy, MomentumStrategy,
            KDJStrategy, RSIStrategy, BOLLStrategy,
            DMIStrategy, CCIStrategy, MACDStrategy, VolumePriceStrategy,
            VolumeSentimentStrategy, FearGreedStrategy, OpenInterestStrategy
        )
        from quant_strategy.backtester import ParallelBacktester, BacktestConfig

        strategy_map = {
            "dual_ma": DualMAStrategy,
            "momentum": MomentumStrategy,
            "kdj": KDJStrategy,
            "rsi": RSIStrategy,
            "boll": BOLLStrategy,
            "dmi": DMIStrategy,
            "cci": CCIStrategy,
            "macd": MACDStrategy,
            "volume_price": VolumePriceStrategy,
            "volume_sentiment": VolumeSentimentStrategy,
            "fear_greed": FearGreedStrategy,
            "open_interest": OpenInterestStrategy
        }

        # 构建策略列表
        strategies = []
        for strat_name in args.strategies:
            strategy_class = strategy_map.get(strat_name)
            if strategy_class:
                strategies.append((strategy_class, {}, strat_name))
            else:
                logger.warning(f"未知策略：{strat_name}")

        if not strategies:
            logger.error("没有有效的策略")
            return

        # 获取数据
        data = ts_provider.get_daily_data(args.ts_code, args.start_date, args.end_date, adj="qfq")
        if data.empty:
            logger.error("获取数据失败")
            return

        # 执行多策略回测
        backtester = ParallelBacktester(max_workers=args.workers, use_processes=True)
        results = backtester.compare_strategies(
            strategies=strategies,
            data_dict={args.ts_code: data},
            show_progress=True
        )

        # 显示对比结果
        print("\n" + "=" * 80)
        print("多策略对比结果")
        print("=" * 80)

        if not results.empty:
            print(results.to_string(index=False))
        print("=" * 80)

    elif args.command == "strategy":
        # 策略管理
        from quant_strategy.strategy import StrategyManager

        manager = StrategyManager()

        if args.strategy_command == "list":
            print(manager.list_strategies(show_all=True))

        elif args.strategy_command == "enable":
            if manager.enable(args.name):
                logger.info(f"策略 {args.name} 已激活")
            else:
                logger.error(f"策略 {args.name} 不存在")

        elif args.strategy_command == "disable":
            if manager.disable(args.name, args.reason):
                logger.info(f"策略 {args.name} 已停用：{args.reason}")
            else:
                logger.error(f"策略 {args.name} 不存在")

        elif args.strategy_command is None:
            print(manager.list_strategies(show_all=True))

    elif args.command == "batch-backtest":
        # 批量回测激活的策略
        if not ts_provider:
            logger.error("请先设置 TUSHARE_TOKEN 环境变量")
            return

        from quant_strategy.strategy import (
            DualMAStrategy, MomentumStrategy,
            KDJStrategy, RSIStrategy, BOLLStrategy,
            DMIStrategy, CCIStrategy, MACDStrategy, VolumePriceStrategy,
            VolumeSentimentStrategy, FearGreedStrategy, OpenInterestStrategy,
            StrategyManager
        )
        from quant_strategy.backtester import ParallelBacktester, BacktestConfig

        # 获取激活的策略列表
        manager = StrategyManager()
        enabled_strategies = manager.get_enabled_strategies()

        if not enabled_strategies:
            logger.error("没有激活的策略，请先使用 strategy enable 命令激活策略")
            return

        logger.info(f"激活的策略：{', '.join(enabled_strategies)}")

        # 策略映射
        strategy_map = {
            "dual_ma": DualMAStrategy,
            "momentum": MomentumStrategy,
            "kdj": KDJStrategy,
            "rsi": RSIStrategy,
            "boll": BOLLStrategy,
            "dmi": DMIStrategy,
            "cci": CCIStrategy,
            "macd": MACDStrategy,
            "volume_price": VolumePriceStrategy,
            "volume_sentiment": VolumeSentimentStrategy,
            "fear_greed": FearGreedStrategy,
            "open_interest": OpenInterestStrategy
        }

        # 构建策略列表
        strategies = []
        for strat_name in enabled_strategies:
            strategy_class = strategy_map.get(strat_name)
            if strategy_class:
                strategies.append((strategy_class, {}, strat_name))
            else:
                logger.warning(f"未知策略：{strat_name}，跳过")

        if not strategies:
            logger.error("没有有效的策略")
            return

        # 获取数据
        logger.info(f"获取股票数据：{args.ts_code}")
        data = ts_provider.get_daily_data(args.ts_code, args.start_date, args.end_date, adj="qfq")
        if data.empty:
            logger.error("获取数据失败")
            return

        logger.info(f"获取数据成功：{len(data)} 条记录")

        # 执行多策略回测
        backtester = ParallelBacktester(max_workers=args.workers, use_processes=False)
        results = backtester.compare_strategies(
            strategies=strategies,
            data_dict={args.ts_code: data},
            show_progress=True
        )

        # 显示结果
        print("\n" + "=" * 80)
        print("批量回测结果汇总")
        print(f"股票代码：{args.ts_code}")
        print(f"日期范围：{args.start_date} - {args.end_date}")
        print("=" * 80)

        if not results.empty:
            # 按收益率排序
            results = results.sort_values("total_return", ascending=False)
            print(results.to_string(index=False))

            # 汇总统计
            print("\n" + "-" * 80)
            print("统计摘要:")
            print(f"  策略数量：{len(strategies)}")
            print(f"  平均收益率：{results['total_return'].mean():.2%}")
            print(f"  平均夏普比率：{results['sharpe_ratio'].mean():.2f}")
            print(f"  平均最大回撤：{results['max_drawdown'].mean():.2%}")
            print(f"  最佳策略：{results.iloc[0]['strategy']} ({results.iloc[0]['total_return']:.2%})")
            print(f"  最差策略：{results.iloc[-1]['strategy']} ({results.iloc[-1]['total_return']:.2%})")
        else:
            print("无有效回测结果")

        print("=" * 80)

        # 导出详细结果
        if args.show_details:
            output_file = Path("./output/reports") / f"batch_backtest_{args.ts_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            results.to_csv(output_file, index=False, encoding='utf-8-sig')
            logger.info(f"详细结果已保存到：{output_file}")


if __name__ == "__main__":
    main()
