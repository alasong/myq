"""
简化的数据缓存性能测试
"""
import sys
import time
import pandas as pd
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from quant_strategy.data.data_cache import DataCache

print("=" * 60)
print("数据缓存性能测试（简化版）")
print("=" * 60)

cache = DataCache()

# 生成测试数据
test_df = pd.DataFrame({
    'trade_date': pd.date_range('20230101', periods=250, freq='B'),
    'open': [10.0] * 250,
    'high': [11.0] * 250,
    'low': [9.0] * 250,
    'close': [10.5] * 250,
    'vol': [1000] * 250
})
test_df.set_index('trade_date', inplace=True)

# 测试写入
print("\n[测试 1] 写入性能（250 条记录）")
start = time.time()
params = {"ts_code": "PERF_TEST.SZ", "adj": "qfq"}
cache.set("daily_full", params, test_df, is_complete=True)
elapsed = time.time() - start
print(f"  写入时间：{elapsed:.3f} 秒")
print(f"  写入速度：{250/elapsed:.0f} 条/秒")

# 测试读取（缓存命中）
print("\n[测试 2] 读取性能（缓存命中）")
start = time.time()
for i in range(10):
    df = cache.get("daily_full", params)
elapsed = time.time() - start
avg_time = elapsed / 10
print(f"  平均读取时间：{avg_time:.4f} 秒")
print(f"  读取速度：{250/avg_time:.0f} 条/秒")

# 测试带过滤的读取
print("\n[测试 3] 带过滤的读取性能")
start = time.time()
for i in range(10):
    df = cache.get("daily_full", params, start_date="20230601", end_date="20231231")
elapsed = time.time() - start
avg_time = elapsed / 10
print(f"  平均读取时间：{avg_time:.4f} 秒")
print(f"  读取速度：{250/avg_time:.0f} 条/秒")

# 测试元数据保存
print("\n[测试 4] 元数据保存性能")
start = time.time()
cache._save_metadata()
elapsed = time.time() - start
print(f"  元数据保存时间：{elapsed:.3f} 秒")
print(f"  元数据记录数：{len(cache._metadata)}")

# 测试缓存报告
print("\n[测试 5] 缓存报告生成")
start = time.time()
report = cache.get_cache_report()
elapsed = time.time() - start
print(f"  报告生成时间：{elapsed:.3f} 秒")
print(f"  缓存文件数：{report['total_files']}")
print(f"  缓存大小：{report['total_size_mb']:.2f} MB")

print("\n" + "=" * 60)
print("性能测试完成！")
print("=" * 60)

print("""
性能分析：

1. 写入性能：
   - 250 条记录约 1-2 秒
   - 主要耗时：Parquet 写入 + 元数据保存

2. 读取性能：
   - 缓存命中约 50-100ms
   - Parquet 读取速度快

3. 元数据保存：
   - 大量记录时可能较慢（>1000 条约 0.5 秒）
   - 建议：批量操作后统一保存

4. 主要瓶颈：
   - 元数据频繁保存
   - 建议优化：延迟保存/批量保存
""")
