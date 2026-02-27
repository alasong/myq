"""
数据存储优化脚本

功能：
1. 按交易所分区存储（SSE/SZSE/BJSE）
2. 使用 ZSTD 压缩
3. 优化数据类型（float64→float32）
4. 自动清理过期缓存
"""
import sys
import pandas as pd
from pathlib import Path
import sqlite3
import shutil
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from quant_strategy.data.data_cache import DataCache


def optimize_parquet_compression():
    """优化 Parquet 文件压缩"""
    print("=" * 60)
    print("优化 Parquet 文件压缩")
    print("=" * 60)
    
    cache = DataCache()
    cache_dir = Path(cache.cache_dir)
    
    # 获取所有 parquet 文件
    parquet_files = list(cache_dir.glob("*.parquet"))
    print(f"\n找到 {len(parquet_files)} 个 Parquet 文件")
    
    total_saved = 0
    optimized_count = 0
    
    for i, parquet_file in enumerate(parquet_files[:100]):  # 先处理前 100 个
        try:
            # 读取原始数据
            df = pd.read_parquet(parquet_file)
            original_size = parquet_file.stat().st_size
            
            # 优化数据类型
            float_cols = ['open', 'high', 'low', 'close', 'vol', 'amount', 'pct_chg', 'change']
            for col in float_cols:
                if col in df.columns:
                    if 'pct_chg' in col or 'change' in col:
                        df[col] = df[col].astype('float32')
                    elif col == 'vol' or col == 'amount':
                        df[col] = df[col].astype('float64')  # 保持精度
                    else:
                        df[col] = df[col].astype('float32')
            
            # 使用 ZSTD 重新保存（移除 compression_opts 参数）
            backup_path = parquet_file.with_suffix('.parquet.bak')
            shutil.copy2(parquet_file, backup_path)
            
            df.to_parquet(parquet_file, compression='zstd')
            new_size = parquet_file.stat().st_size
            
            saved = original_size - new_size
            total_saved += saved
            optimized_count += 1
            
            if i % 20 == 0:
                print(f"  处理进度：{i+1}/{min(100, len(parquet_files))} - 节省：{saved/1024:.1f} KB")
            
            # 删除备份
            backup_path.unlink()
            
        except Exception as e:
            print(f"  处理失败 {parquet_file}: {e}")
            continue
    
    print(f"\n优化完成:")
    print(f"  处理文件：{optimized_count} 个")
    print(f"  节省空间：{total_saved/1024/1024:.2f} MB")
    print(f"  平均压缩：{total_saved/optimized_count/1024:.1f} KB/文件" if optimized_count > 0 else "")


def organize_by_exchange():
    """按交易所组织文件"""
    print("\n" + "=" * 60)
    print("按交易所组织文件")
    print("=" * 60)
    
    cache = DataCache()
    cache_dir = Path(cache.cache_dir)
    
    # 创建交易所目录
    sse_dir = cache_dir / "SSE"
    szse_dir = cache_dir / "SZSE"
    bjse_dir = cache_dir / "BJSE"
    
    for d in [sse_dir, szse_dir, bjse_dir]:
        d.mkdir(parents=True, exist_ok=True)
    
    # 从 SQLite 获取股票信息
    conn = sqlite3.connect(str(cache_dir / "cache.db"))
    
    # 查询所有股票
    df = pd.read_sql_query("""
        SELECT key, ts_code, path
        FROM cache_metadata
        WHERE ts_code IS NOT NULL
    """, conn)
    
    print(f"\n找到 {len(df)} 只股票")
    
    moved_count = 0
    
    for _, row in df.iterrows():
        ts_code = row['ts_code']
        old_path = Path(row['path'])
        
        if not old_path.exists():
            continue
        
        # 判断交易所
        if ts_code.endswith('.SH'):
            new_dir = sse_dir
        elif ts_code.endswith('.SZ'):
            new_dir = szse_dir
        elif ts_code.endswith('.BJ'):
            new_dir = bjse_dir
        else:
            continue
        
        # 移动文件
        new_path = new_dir / old_path.name
        if not new_path.exists():
            try:
                shutil.move(str(old_path), str(new_path))
                
                # 更新数据库
                conn.execute("""
                    UPDATE cache_metadata
                    SET path = ?
                    WHERE key = ?
                """, (str(new_path), row['key']))
                
                moved_count += 1
                
                if moved_count % 500 == 0:
                    print(f"  已移动：{moved_count} 个文件")
                    
            except Exception as e:
                print(f"  移动失败 {ts_code}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\n移动完成:")
    print(f"  移动文件：{moved_count} 个")
    print(f"  SSE 目录：{len(list(sse_dir.glob('*.parquet')))} 个")
    print(f"  SZSE 目录：{len(list(szse_dir.glob('*.parquet')))} 个")
    print(f"  BJSE 目录：{len(list(bjse_dir.glob('*.parquet')))} 个")


def cleanup_old_backups(days=7):
    """清理旧备份"""
    print("\n" + "=" * 60)
    print(f"清理 {days} 天前的备份")
    print("=" * 60)
    
    cache = DataCache()
    backup_dir = Path(cache.cache_dir) / "backup"
    
    if not backup_dir.exists():
        print("  无备份目录")
        return
    
    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=days)
    
    deleted = 0
    for f in backup_dir.iterdir():
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                deleted += 1
        except:
            pass
    
    print(f"  删除备份：{deleted} 个")


def show_storage_stats():
    """显示存储统计"""
    print("\n" + "=" * 60)
    print("存储统计")
    print("=" * 60)
    
    cache = DataCache()
    cache_dir = Path(cache.cache_dir)
    
    # 从 SQLite 获取统计
    conn = sqlite3.connect(str(cache_dir / "cache.db"))
    
    # 总数
    total = pd.read_sql_query("SELECT COUNT(*) as count FROM cache_metadata", conn)['count'].iloc[0]
    
    # 按类型
    by_type = pd.read_sql_query("""
        SELECT data_type, COUNT(*) as count, SUM(record_count) as records
        FROM cache_metadata
        GROUP BY data_type
    """, conn)
    
    # 按交易所
    by_exchange = pd.read_sql_query("""
        SELECT 
            CASE 
                WHEN ts_code LIKE '%.SH' THEN 'SSE'
                WHEN ts_code LIKE '%.SZ' THEN 'SZSE'
                WHEN ts_code LIKE '%.BJ' THEN 'BJSE'
                ELSE 'UNKNOWN'
            END as exchange,
            COUNT(*) as count
        FROM cache_metadata
        GROUP BY exchange
    """, conn)
    
    # 计算实际文件大小
    total_size = 0
    for pattern in ['*.parquet', 'SSE/*.parquet', 'SZSE/*.parquet', 'BJSE/*.parquet']:
        for f in cache_dir.glob(pattern):
            total_size += f.stat().st_size
    
    conn.close()
    
    print(f"\n总文件数：{total}")
    print(f"总大小：{total_size/1024/1024:.2f} MB")
    print(f"平均每只股票：{total_size/total/1024:.1f} KB" if total > 0 else "N/A")
    
    print("\n按类型:")
    for _, row in by_type.iterrows():
        print(f"  {row['data_type']}: {row['count']} 个，{row['records']:.0f} 条记录")
    
    print("\n按交易所:")
    for _, row in by_exchange.iterrows():
        print(f"  {row['exchange']}: {row['count']} 个")


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print(" 数据存储优化")
    print("=" * 70)
    
    # 1. 优化压缩
    optimize_parquet_compression()
    
    # 2. 按交易所组织
    organize_by_exchange()
    
    # 3. 清理旧备份
    cleanup_old_backups(days=7)
    
    # 4. 显示统计
    show_storage_stats()
    
    print("\n" + "=" * 70)
    print(" [OK] 优化完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()
