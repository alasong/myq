"""
缓存压缩测试脚本

测试不同压缩算法的效果：
- none: 无压缩
- snappy: 快速压缩（默认）
- gzip: 平衡压缩
- brotli: 高压缩比
- zstd: 最佳平衡
"""
import pandas as pd
import numpy as np
from pathlib import Path
import time
import os

# 创建测试数据
print("生成测试数据...")
np.random.seed(42)
dates = pd.date_range('20240101', '20241231', freq='B')
n = len(dates)

test_data = pd.DataFrame({
    'trade_date': dates.strftime('%Y%m%d').astype(int),
    'ts_code': '000001.SZ',
    'open': np.random.uniform(10, 20, n),
    'high': np.random.uniform(20, 25, n),
    'low': np.random.uniform(9, 19, n),
    'close': np.random.uniform(15, 22, n),
    'vol': np.random.uniform(1000000, 50000000, n),
    'amount': np.random.uniform(10000000, 500000000, n),
    'amplitude': np.random.uniform(1, 10, n),
    'pct_chg': np.random.uniform(-10, 10, n),
    'change': np.random.uniform(-2, 2, n),
})

test_data.set_index('trade_date', inplace=True)
print(f"测试数据：{len(test_data)} 行\n")

# 测试不同压缩算法
compressions = ['none', 'snappy', 'gzip', 'brotli', 'zstd']
results = []

test_file = Path('data_cache/test_compression.parquet')

for comp in compressions:
    try:
        # 测试写入时间和文件大小
        start = time.time()
        if comp == 'none':
            test_data.to_parquet(test_file, index=True, compression=None)
        else:
            test_data.to_parquet(test_file, index=True, compression=comp)
        write_time = time.time() - start
        
        file_size = test_file.stat().st_size
        size_mb = file_size / 1024 / 1024
        
        # 测试读取时间
        start = time.time()
        df_loaded = pd.read_parquet(test_file)
        read_time = time.time() - start
        
        # 验证数据一致性
        assert len(df_loaded) == len(test_data)
        
        results.append({
            'compression': comp,
            'size_mb': size_mb,
            'ratio': f"{100 * size_mb / (test_data.memory_usage(deep=True).sum() / 1024 / 1024):.1f}%",
            'write_ms': f"{write_time * 1000:.1f}",
            'read_ms': f"{read_time * 100:.1f}",
        })
        
        print(f"{comp:8s}: {size_mb:6.2f} MB  (写：{write_time*1000:5.1f}ms, 读：{read_time*100:5.1f}ms)")
        
    except Exception as e:
        print(f"{comp:8s}: 不支持 - {e}")

# 清理测试文件
if test_file.exists():
    test_file.unlink()

# 打印总结
print("\n" + "=" * 60)
print("压缩比总结（越小越好）:")
print("=" * 60)
for r in results:
    bar = "█" * int(20 * float(r['ratio'].strip('%')) / 100)
    print(f"  {r['compression']:8s} [{bar:20s}] {r['ratio']}")

print("\n推荐:")
print("  - 追求速度：snappy（默认）")
print("  - 平衡性能：gzip 或 zstd")
print("  - 最高压缩：brotli（但读写较慢）")
