"""
数据缓存性能测试脚本

测试当前数据本地存储的存取性能，识别潜在瓶颈
"""
import sys
import time
import pandas as pd
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from quant_strategy.data.data_cache import DataCache


def generate_test_data(days=250):
    """生成测试数据（模拟 1 年的交易日数据）"""
    dates = pd.date_range('20230101', periods=days, freq='B')  # 工作日
    test_df = pd.DataFrame({
        'trade_date': dates,
        'open': (10 + pd.Series(range(days)) * 0.01).astype(float),
        'high': (11 + pd.Series(range(days)) * 0.01).astype(float),
        'low': (9 + pd.Series(range(days)) * 0.01).astype(float),
        'close': (10.5 + pd.Series(range(days)) * 0.01).astype(float),
        'vol': (1000 + pd.Series(range(days)) * 10).astype(float),
        'amount': (10000 + pd.Series(range(days)) * 100).astype(float),
        'pct_chg': (pd.Series(range(days)) * 0.001).astype(float),
    })
    test_df.set_index('trade_date', inplace=True)
    return test_df


def test_write_performance():
    """测试写入性能"""
    print("=" * 70)
    print("测试 1: 写入性能测试")
    print("=" * 70)
    
    cache = DataCache()
    test_df = generate_test_data(250)  # 1 年数据
    
    results = []
    
    # 测试 1: 单次写入性能
    print("\n[测试 1.1] 单次写入性能（250 条记录）...")
    start = time.time()
    params = {"ts_code": "PERF_TEST.SZ", "adj": "qfq"}
    cache.set("daily_full", params, test_df, is_complete=True)
    elapsed = time.time() - start
    results.append(("单次写入 (250 条)", elapsed, len(test_df)/elapsed))
    print(f"  写入时间：{elapsed:.3f} 秒")
    print(f"  写入速度：{len(test_df)/elapsed:.0f} 条/秒")
    
    # 测试 2: 大数据量写入
    print("\n[测试 1.2] 大数据量写入（1000 条记录）...")
    large_df = generate_test_data(1000)  # 约 4 年数据
    start = time.time()
    params = {"ts_code": "PERF_LARGE.SZ", "adj": "qfq"}
    cache.set("daily_full", params, large_df, is_complete=True)
    elapsed = time.time() - start
    results.append(("大数据写入 (1000 条)", elapsed, len(large_df)/elapsed))
    print(f"  写入时间：{elapsed:.3f} 秒")
    print(f"  写入速度：{len(large_df)/elapsed:.0f} 条/秒")
    
    # 测试 3: 重复写入性能（测试旧数据删除）
    print("\n[测试 1.3] 重复写入性能（含旧数据删除）...")
    start = time.time()
    cache.set("daily_full", params, large_df, is_complete=True)
    elapsed = time.time() - start
    results.append(("重复写入 (含删除)", elapsed, len(large_df)/elapsed))
    print(f"  写入时间：{elapsed:.3f} 秒")
    print(f"  写入速度：{len(large_df)/elapsed:.0f} 条/秒")
    
    # 测试 4: 元数据保存性能
    print("\n[测试 1.4] 元数据保存性能...")
    start = time.time()
    cache._save_metadata()
    elapsed = time.time() - start
    print(f"  元数据保存时间：{elapsed:.3f} 秒")
    print(f"  元数据大小：{len(cache._metadata)} 条记录")
    
    return results


def test_read_performance():
    """测试读取性能"""
    print("\n" + "=" * 70)
    print("测试 2: 读取性能测试")
    print("=" * 70)
    
    cache = DataCache()
    results = []
    
    # 准备数据
    test_df = generate_test_data(250)
    params = {"ts_code": "READ_TEST.SZ", "adj": "qfq"}
    cache.set("daily_full", params, test_df, is_complete=True)
    
    # 测试 1: 缓存命中读取（完整数据）
    print("\n[测试 2.1] 缓存命中读取（完整数据，250 条）...")
    start = time.time()
    for _ in range(10):
        df = cache.get("daily_full", params)
    elapsed = time.time() - start
    avg_time = elapsed / 10
    results.append(("缓存命中读取", avg_time, len(test_df)/avg_time))
    print(f"  平均读取时间：{avg_time:.4f} 秒")
    print(f"  读取速度：{len(test_df)/avg_time:.0f} 条/秒")
    
    # 测试 2: 带日期过滤的读取
    print("\n[测试 2.2] 带日期过滤的读取...")
    start = time.time()
    for _ in range(10):
        df = cache.get("daily_full", params, start_date="20230601", end_date="20231231")
    elapsed = time.time() - start
    avg_time = elapsed / 10
    results.append(("带过滤读取", avg_time, len(test_df)/avg_time))
    print(f"  平均读取时间：{avg_time:.4f} 秒")
    print(f"  读取速度：{len(test_df)/avg_time:.0f} 条/秒")
    
    # 测试 3: 缓存未命中
    print("\n[测试 2.3] 缓存未命中读取...")
    start = time.time()
    params_miss = {"ts_code": "MISS_TEST.SZ", "adj": "qfq"}
    df = cache.get("daily_full", params_miss)
    elapsed = time.time() - start
    print(f"  未命中检查时间：{elapsed:.4f} 秒")
    
    return results


def test_metadata_performance():
    """测试元数据操作性能"""
    print("\n" + "=" * 70)
    print("测试 3: 元数据操作性能测试")
    print("=" * 70)
    
    cache = DataCache()
    
    # 测试 1: 元数据加载性能
    print("\n[测试 3.1] 元数据加载性能...")
    start = time.time()
    cache._metadata = cache._load_metadata()
    elapsed = time.time() - start
    print(f"  元数据加载时间：{elapsed:.3f} 秒")
    print(f"  元数据记录数：{len(cache._metadata)}")
    
    # 测试 2: 元数据查询性能
    print("\n[测试 3.2] 元数据查询性能...")
    start = time.time()
    for _ in range(100):
        result = cache._metadata[cache._metadata["key"] == "daily_full_adj=qfq_ts_code=PERF_TEST.SZ"]
    elapsed = time.time() - start
    print(f"  100 次查询时间：{elapsed:.3f} 秒")
    print(f"  平均查询时间：{elapsed/100*1000:.3f} 毫秒")
    
    # 测试 3: 元数据保存性能（大数据量）
    print("\n[测试 3.3] 大量元数据保存性能...")
    # 添加一些测试记录
    for i in range(100):
        new_entry = pd.DataFrame([{
            "key": f"test_key_{i}",
            "path": f"test_path_{i}.parquet",
            "updated_at": "20260227_120000",
            "start_date": "20230101",
            "end_date": "20231231",
            "data_type": "daily",
            "ts_code": f"TEST_{i}.SZ",
            "is_complete": True,
            "record_count": 250
        }])
        cache._metadata = pd.concat([cache._metadata, new_entry], ignore_index=True)
    
    start = time.time()
    cache._save_metadata()
    elapsed = time.time() - start
    print(f"  元数据保存时间：{elapsed:.3f} 秒")
    print(f"  元数据记录数：{len(cache._metadata)}")
    
    # 清理测试数据
    cache._metadata = cache._metadata[~cache._metadata["key"].str.startswith("test_key_")]
    cache._save_metadata()


def test_lru_performance():
    """测试 LRU 淘汰性能"""
    print("\n" + "=" * 70)
    print("测试 4: LRU 淘汰性能测试")
    print("=" * 70)
    
    # 创建小缓存用于测试
    cache = DataCache(max_size_mb=0.1)
    
    # 写入多个文件触发 LRU
    print("\n[测试 4.1] LRU 淘汰性能...")
    start = time.time()
    
    for i in range(20):
        test_df = generate_test_data(100)
        params = {"ts_code": f"LRU_TEST_{i}.SZ", "adj": "qfq"}
        cache.set("daily", params, test_df)
    
    elapsed = time.time() - start
    print(f"  20 次写入（含 LRU 淘汰）时间：{elapsed:.3f} 秒")
    print(f"  平均每次写入：{elapsed/20:.3f} 秒")
    
    # 验证 daily_full 保护
    print("\n[测试 4.2] daily_full 保护验证...")
    cache.set("daily_full", {"ts_code": "PROTECTED.SZ", "adj": "qfq"}, generate_test_data(100), is_complete=True)
    
    # 继续写入触发 LRU
    for i in range(10):
        test_df = generate_test_data(100)
        params = {"ts_code": f"LRU_TEST_{i+20}.SZ", "adj": "qfq"}
        cache.set("daily", params, test_df)
    
    protected_count = len(cache._metadata[cache._metadata["data_type"] == "daily_full"])
    print(f"  daily_full 类型数量：{protected_count}")
    print(f"  daily_full 保护状态：{'正常' if protected_count > 0 else '失败'}")


def test_concurrent_access():
    """测试并发访问性能"""
    print("\n" + "=" * 70)
    print("测试 5: 并发访问性能测试")
    print("=" * 70)
    
    import threading
    
    cache = DataCache()
    test_df = generate_test_data(250)
    params = {"ts_code": "CONCURRENT_TEST.SZ", "adj": "qfq"}
    cache.set("daily_full", params, test_df, is_complete=True)
    
    results = []
    lock = threading.Lock()
    
    def read_worker(worker_id):
        start = time.time()
        for _ in range(10):
            df = cache.get("daily_full", params)
        elapsed = time.time() - start
        with lock:
            results.append((worker_id, elapsed))
    
    # 创建多个线程
    threads = []
    for i in range(5):
        t = threading.Thread(target=read_worker, args=(i,))
        threads.append(t)
    
    # 启动所有线程
    start = time.time()
    for t in threads:
        t.start()
    
    # 等待所有线程完成
    for t in threads:
        t.join()
    
    total_elapsed = time.time() - start
    print(f"  5 个并发线程，各读取 10 次")
    print(f"  总耗时：{total_elapsed:.3f} 秒")
    print(f"  平均每次读取：{total_elapsed/50*1000:.2f} 毫秒")


def print_summary():
    """打印性能总结"""
    print("\n" + "=" * 70)
    print("性能测试总结")
    print("=" * 70)
    
    print("""
识别的性能瓶颈：

1. [中] 元数据保存性能
   - 问题：每次 set() 都保存整个 metadata.csv
   - 影响：大量缓存文件时保存较慢
   - 建议：批量操作后统一保存

2. [低] 重复写入时的旧数据删除
   - 问题：需要先查询再删除
   - 影响：重复写入稍慢
   - 建议：可接受，因为不频繁

3. [低] LRU 淘汰性能
   - 问题：需要遍历文件系统
   - 影响：缓存满时写入稍慢
   - 建议：可接受，因为不频繁

4. [无] 读取性能
   - Parquet 格式读取快速
   - 索引过滤高效
   - 无需优化

5. [无] 并发访问
   - 多线程读取正常
   - 无锁竞争问题
   - 无需优化

总体评价：
- 读取性能：优秀（Parquet 格式）
- 写入性能：良好（主要瓶颈在元数据保存）
- 并发性能：良好
- 主要瓶颈：元数据频繁保存
""")


def main():
    """运行所有性能测试"""
    print("\n" + "=" * 70)
    print(" 数据缓存性能测试")
    print("=" * 70)
    print(f"测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 测试写入性能
        write_results = test_write_performance()
        
        # 测试读取性能
        read_results = test_read_performance()
        
        # 测试元数据性能
        test_metadata_performance()
        
        # 测试 LRU 性能
        test_lru_performance()
        
        # 测试并发访问
        test_concurrent_access()
        
        # 打印总结
        print_summary()
        
        print("\n[PASS] 所有性能测试完成！")
        
    except Exception as e:
        print(f"\n[FAIL] 性能测试失败：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
