"""
批量获取并缓存全量 A 股数据工具

用途：
1. 预先获取并缓存所有股票数据
2. 支持增量更新（跳过已完整的数据）
3. 显示进度和统计信息
4. 支持多线程并发获取

数据源：
- 仅使用 Tushare（稳定可靠）

使用方法：
    # 自动跳过已完整的数据
    python -m quant_strategy.tools.fetch_all_stocks --start 20230101 --end 20231231

    # 强制重新获取（忽略缓存）
    python -m quant_strategy.tools.fetch_all_stocks --start 20230101 --end 20231231 --force
    
    # 使用多线程加速（推荐：4 个线程）
    python -m quant_strategy.tools.fetch_all_stocks --start 20230101 --end 20231231 --workers 4
"""
import argparse
import sys
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.tushare_provider import TushareDataProvider
from data.data_cache import DataCache


def setup_logger():
    """配置日志"""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )
    logger.add(
        "./logs/fetch_stocks_{time:YYYYMMDD}.log",
        rotation="1 day",
        retention="7 days",
        format="{time:HH:mm:ss} | {level} | {message}",
        level="DEBUG"
    )


def get_all_stocks(provider):
    """获取全部 A 股股票列表"""
    logger.info("获取 A 股股票列表...")
    stock_list = provider.get_stock_list()
    
    if stock_list.empty:
        logger.error("获取股票列表失败")
        return []
    
    # 过滤有效股票
    stock_list = stock_list[stock_list['ts_code'].notna()]
    
    # 按交易所分类统计
    sse_count = len(stock_list[stock_list['ts_code'].str.endswith('.SH', na=False)])
    szse_count = len(stock_list[stock_list['ts_code'].str.endswith('.SZ', na=False)])
    bjse_count = len(stock_list[stock_list['ts_code'].str.endswith('.BJ', na=False)])
    
    logger.info(f"获取到 {len(stock_list)} 只股票：沪市{sse_count}只，深市{szse_count}只，北交所{bjse_count}只")
    return stock_list['ts_code'].tolist()


def check_cache_completeness(cache, ts_code, start_date, end_date, expected_days=None):
    """
    检查某只股票的缓存完整性

    Args:
        cache: 缓存对象
        ts_code: 股票代码
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        expected_days: 预期交易日天数（可选，如不提供则自动计算）

    Returns:
        str: 'complete' - 完整数据
             'partial' - 部分数据
             'missing' - 无缓存
    """
    params = {"ts_code": ts_code, "start": start_date, "end": end_date, "adj": "qfq"}

    # 计算预期交易日天数
    if expected_days is None:
        # 使用实际交易日计算（约 250 天/年）
        start_dt = pd.to_datetime(start_date, format='%Y%m%d')
        end_dt = pd.to_datetime(end_date, format='%Y%m%d')
        expected_days = int(((end_dt - start_dt).days * 250 / 365) * 0.95)

    # 从缓存获取
    cached = cache.get("daily", params, start_date, end_date, expected_days=expected_days)

    if cached is None:
        return 'missing'

    # 检查元数据中的完整性标记
    key = cache._generate_key("daily", params)
    cache_entry = cache._metadata[cache._metadata["key"] == key]

    if not cache_entry.empty:
        row = cache_entry.iloc[0]
        is_complete = row.get("is_complete", False) if "is_complete" in cache_entry.columns else False

        if is_complete:
            return 'complete'

        # 检查记录数
        record_count = row.get("record_count", 0) if "record_count" in cache_entry.columns else 0
        if record_count >= expected_days:
            return 'complete'

    return 'partial'


def fetch_single_stock(provider, ts_code, start_date, end_date, adj="qfq"):
    """
    获取单只股票数据（用于多线程）
    
    Returns:
        tuple: (ts_code, success, message)
    """
    try:
        df = provider.get_daily_data(ts_code, start_date, end_date, adj=adj)
        if df is not None and not df.empty:
            has_amount = 'amount' in df.columns and df['amount'].notna().any()
            has_vol = 'vol' in df.columns and df['vol'].notna().any()
            
            if has_amount and has_vol:
                return (ts_code, True, "✅")
            elif has_amount or has_vol:
                return (ts_code, True, "⚠️ ")
            else:
                return (ts_code, True, "❓")
        else:
            return (ts_code, False, "空数据")
    except Exception as e:
        return (ts_code, False, str(e))


def fetch_and_cache_stocks(provider, ts_codes, start_date, end_date, batch_size=100, force=False, workers=1):
    """
    批量获取并缓存股票数据

    Args:
        provider: 数据提供者
        ts_codes: 股票代码列表
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        batch_size: 批次大小
        force: 是否强制重新获取（忽略缓存）
        workers: 并发线程数
    """
    cache = provider.cache
    total = len(ts_codes)
    success = 0
    failed = 0
    skipped_complete = 0
    skipped_partial = 0

    # 先检查缓存状态
    if not force and cache:
        logger.info("检查缓存完整性...")
        stocks_to_fetch = []
        
        for i, ts_code in enumerate(ts_codes):
            status = check_cache_completeness(cache, ts_code, start_date, end_date)
            
            if status == 'complete':
                skipped_complete += 1
            elif status == 'partial':
                stocks_to_fetch.append(ts_code)
                skipped_partial += 1
            else:  # missing
                stocks_to_fetch.append(ts_code)
        
        logger.info(f"缓存检查完成:")
        logger.info(f"  ✅ 完整数据：{skipped_complete} 只（跳过）")
        logger.info(f"  ⚠️  部分数据：{skipped_partial} 只（需更新）")
        logger.info(f"  ❌ 无缓存：{len(ts_codes) - skipped_complete - skipped_partial} 只（需获取）")
        
        if skipped_complete == total:
            logger.info("所有股票数据已完整，无需获取！")
            return
        
        ts_codes = stocks_to_fetch
        total = len(ts_codes)
        logger.info(f"需要获取/更新：{total} 只股票")
        logger.info("")
    
    logger.info(f"开始获取 {total} 只股票数据，时间范围：{start_date} - {end_date}")
    logger.info(f"并发线程数：{workers}")
    
    # 使用多线程获取
    if workers > 1:
        # 多线程模式
        progress_lock = threading.Lock()
        progress_counter = {'count': 0}
        
        def fetch_with_progress(ts_code):
            result = fetch_single_stock(provider, ts_code, start_date, end_date)
            ts_code, ok, status = result
            
            with progress_lock:
                progress_counter['count'] += 1
                count = progress_counter['count']
                
                # 每 10 只显示一次进度
                if count % 10 == 0 or count == total:
                    pct = count / total * 100
                    logger.info(f"进度：{count}/{total} ({pct:.1f}%) - {status} {ts_code}")
                
                if ok:
                    return True
                else:
                    return False
            
            return ok
        
        # 使用线程池
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(fetch_with_progress, ts_code): ts_code for ts_code in ts_codes}
            
            for future in as_completed(futures):
                try:
                    ok = future.result()
                    if ok:
                        success += 1
                    else:
                        failed += 1
                except Exception as e:
                    failed += 1
                    logger.debug(f"线程异常：{e}")
    
    else:
        # 单线程模式（原逻辑）
        for i in range(0, total, batch_size):
            batch = ts_codes[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            logger.info(f"处理批次 {batch_num}/{total_batches} (股票 {i+1}-{min(i+batch_size, total)})")

            for j, ts_code in enumerate(batch):
                try:
                    # 获取数据（会自动缓存）
                    df = provider.get_daily_data(ts_code, start_date, end_date, adj="qfq")

                    if df is not None and not df.empty:
                        # 检查是否有 amount 和 vol 数据
                        has_amount = 'amount' in df.columns and df['amount'].notna().any()
                        has_vol = 'vol' in df.columns and df['vol'].notna().any()

                        if has_amount and has_vol:
                            success += 1
                            status = "✅"
                        elif has_amount or has_vol:
                            success += 1
                            status = "⚠️ "  # 部分数据缺失
                        else:
                            success += 1
                            status = "❓"  # 数据字段缺失

                        # 每 10 只股票显示一次进度
                        if (i + j + 1) % 10 == 0:
                            logger.info(f"进度：{i+j+1}/{total} ({(i+j+1)/total*100:.1f}%) - {status} {ts_code}")
                    else:
                        failed += 1
                        logger.warning(f"获取数据为空：{ts_code}")

                except Exception as e:
                    failed += 1
                    logger.error(f"获取数据失败 {ts_code}: {e}")
                    continue

            # 每批次结束后保存统计
            logger.debug(f"批次完成：成功{success}，失败{failed}")
    
    # 最终统计
    logger.info("=" * 60)
    logger.info(f"数据获取完成！")
    logger.info(f"总计：{len(ts_codes)} 只股票")
    logger.info(f"成功：{success} 只 ({success/len(ts_codes)*100:.1f}% if ts_codes else 0)")
    logger.info(f"失败：{failed} 只 ({failed/len(ts_codes)*100:.1f}% if ts_codes else 0)")
    if not force:
        logger.info(f"跳过（已完整）：{skipped_complete} 只")
    logger.info("=" * 60)
    
    # 缓存统计
    if cache:
        stats = cache.get_cache_stats()
        logger.info(f"缓存统计：{stats['total_files']} 文件，{stats['total_size_mb']:.2f} MB")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="批量获取并缓存 A 股数据（仅 Tushare）")
    parser.add_argument("--start", type=str, required=True, help="开始日期 YYYYMMDD")
    parser.add_argument("--end", type=str, required=True, help="结束日期 YYYYMMDD")
    parser.add_argument("--batch", type=int, default=100, help="批次大小")
    parser.add_argument("--force", action="store_true", help="强制重新获取（忽略缓存）")
    parser.add_argument("--token", type=str, help="Tushare Token（不设置则从环境变量读取）")
    parser.add_argument("--workers", type=int, default=1, help="并发线程数（默认 1，推荐 4）")

    args = parser.parse_args()
    
    # 设置日志
    setup_logger()
    
    # 检查 Tushare Token
    tushare_token = args.token or os.getenv('TUSHARE_TOKEN', '')
    if not tushare_token:
        logger.error("❌ Tushare Token 未设置！")
        logger.error("请设置环境变量：export TUSHARE_TOKEN=your_token_here")
        logger.error("或使用命令行参数：--token your_token_here")
        return
    
    logger.info(f"✅ 检测到 TUSHARE_TOKEN，使用 Tushare 数据源")
    
    # 初始化数据提供者
    try:
        provider = TushareDataProvider(token=tushare_token, use_cache=True)
    except Exception as e:
        logger.error(f"❌ 初始化 Tushare 失败：{e}")
        return
    
    # 获取股票列表
    ts_codes = get_all_stocks(provider)
    
    if not ts_codes:
        logger.error("股票列表为空，退出")
        return
    
    # 获取并缓存数据
    fetch_and_cache_stocks(provider, ts_codes, args.start, args.end, args.batch, args.force, args.workers)
    
    # 验证缓存
    cache = provider.cache
    if cache:
        logger.info("验证缓存...")
        cached_stocks = cache.get_cached_stocks()
        logger.info(f"缓存中股票数量：{len(cached_stocks)}")


if __name__ == "__main__":
    main()
