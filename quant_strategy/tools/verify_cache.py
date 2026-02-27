"""
验证缓存数据质量工具

用途：
1. 检查缓存中股票的 amount 和 vol 数据
2. 显示数据完整性标记
3. 找出需要更新的股票

使用方法：
    python -m quant_strategy.tools.verify_cache
"""
import sys
from pathlib import Path
import pandas as pd
from loguru import logger

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.data_cache import DataCache


def setup_logger():
    """配置日志"""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )


def verify_cache_data(cache):
    """
    验证缓存数据质量

    Returns:
        数据统计 DataFrame
    """
    logger.info("开始验证缓存数据...")

    # 获取缓存元数据
    metadata = cache.list_cache()

    if metadata.empty:
        logger.warning("缓存为空")
        return pd.DataFrame()

    # 只检查 daily 类型数据
    if "data_type" in metadata.columns:
        daily_cache = metadata[metadata["data_type"].isin(["daily", "daily_ak"])]
    else:
        daily_cache = metadata

    if daily_cache.empty:
        logger.warning("没有缓存日线数据")
        return pd.DataFrame()

    logger.info(f"缓存中有 {len(daily_cache)} 只股票数据")

    # 统计完整性
    if "is_complete" in daily_cache.columns:
        complete_count = len(daily_cache[daily_cache["is_complete"] == True])
        partial_count = len(daily_cache[daily_cache["is_complete"] == False])
        unknown_count = len(daily_cache[daily_cache["is_complete"].isna()])
    else:
        complete_count = 0
        partial_count = len(daily_cache)
        unknown_count = 0

    # 检查重复数据（抽样）
    sample_size = min(50, len(daily_cache))
    sample = daily_cache.sample(n=sample_size, random_state=42)
    duplicate_count = 0

    for _, row in sample.iterrows():
        try:
            cache_path = Path(row["path"])
            if not cache_path.exists():
                continue

            df = pd.read_parquet(cache_path)
            if "trade_date" in df.columns and df["trade_date"].duplicated().any():
                duplicate_count += 1
        except:
            continue

    logger.info("=" * 70)
    logger.info("数据完整性统计 (100% 要求):")
    logger.info("=" * 70)
    logger.info(f"[OK] 完整数据：{complete_count} 只 ({complete_count/len(daily_cache)*100:.1f}%)")
    logger.info(f"[WARN] 部分数据：{partial_count} 只 ({partial_count/len(daily_cache)*100:.1f}%)")
    logger.info(f"[UNK] 未知标记：{unknown_count} 只 ({unknown_count/len(daily_cache)*100:.1f}%)")
    if duplicate_count > 0:
        logger.info(f"[DUP] 抽样发现重复：{duplicate_count} 只 ({duplicate_count/sample_size*100:.1f}%)")

    # 显示需要更新的股票示例
    if partial_count > 0 or unknown_count > 0:
        logger.info("")
        logger.info("需要更新的股票示例（前 20 只）:")
        partial_stocks = daily_cache[(daily_cache["is_complete"] == False) | (daily_cache["is_complete"].isna())].head(20)
        for _, row in partial_stocks.iterrows():
            ts_code = row.get("ts_code", "unknown")
            records = row.get("record_count", "N/A")
            age_days = row.get("age_days", "N/A") if "age_days" in row else "N/A"
            logger.info(f"  {ts_code}: {records}条记录，缓存{age_days}天")

    logger.info("=" * 70)

    # 返回统计信息
    return pd.DataFrame({
        "status": ["complete", "partial", "unknown"],
        "count": [complete_count, partial_count, unknown_count]
    })


def check_specific_stocks(cache, ts_codes, start_date, end_date):
    """
    检查特定股票的数据质量
    
    Args:
        cache: 缓存对象
        ts_codes: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
    """
    logger.info(f"检查 {len(ts_codes)} 只股票的数据质量...")
    
    # 计算预期交易日天数
    start_dt = pd.to_datetime(start_date, format='%Y%m%d')
    end_dt = pd.to_datetime(end_date, format='%Y%m%d')
    expected_days = int(((end_dt - start_dt).days * 250 / 365) * 0.95)
    
    for ts_code in ts_codes:
        params = {"ts_code": ts_code, "start": start_date, "end": end_date, "adj": "qfq"}
        df = cache.get("daily", params, start_date, end_date, expected_days=expected_days)
        
        if df is None or df.empty:
            logger.warning(f"{ts_code}: 缓存中无数据")
            continue
        
        # 检查关键字段
        has_amount = 'amount' in df.columns
        has_vol = 'vol' in df.columns
        
        if has_amount:
            amount_mean = df['amount'].mean()
            amount_valid = (df['amount'] > 0).any()
        else:
            amount_mean = 0
            amount_valid = False
        
        if has_vol:
            vol_mean = df['vol'].mean()
            vol_valid = (df['vol'] > 0).any()
        else:
            vol_mean = 0
            vol_valid = False
        
        status = "[OK]" if (amount_valid and vol_valid) else "[WARN]"
        logger.info(f"{status} {ts_code}: amount={amount_mean/1e8:.2f}亿 (有效={amount_valid}), vol={vol_mean/1e6:.2f}百万股 (有效={vol_valid})")


def main():
    """主函数"""
    setup_logger()
    
    # 初始化缓存
    cache = DataCache(cache_dir="./data_cache")
    
    # 显示缓存统计
    stats = cache.get_cache_stats()
    logger.info("缓存统计:")
    logger.info(f"  文件数：{stats['total_files']}")
    logger.info(f"  大小：{stats['total_size_mb']:.2f} MB")
    logger.info(f"  股票数：{stats['stock_count']}")
    logger.info(f"  命中率：{stats['hit_rate']*100:.1f}%")
    logger.info("")
    
    # 验证数据质量
    result_df = verify_cache_data(cache)
    
    # 检查一些典型股票
    logger.info("")
    sample_stocks = [
        "600519.SH",  # 贵州茅台
        "000001.SZ",  # 平安银行
        "300750.SZ",  # 宁德时代
        "600036.SH",  # 招商银行
        "000002.SZ",  # 万科 A
    ]
    
    # 检查最近一年的数据
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
    
    check_specific_stocks(cache, sample_stocks, start_date, end_date)


if __name__ == "__main__":
    main()
