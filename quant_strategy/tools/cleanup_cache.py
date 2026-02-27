"""
清理重复缓存数据

问题：
1. 同时存在 daily_full 和 daily 两种缓存
2. 旧格式的 daily 缓存可以删除

解决方案：
- 保留 daily_full 缓存（新格式，按股票 + 复权类型）
- 删除 daily 缓存（旧格式，按日期范围）
- 删除 index_daily 缓存（指数数据）
"""
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from quant_strategy.data.data_cache import DataCache
import pandas as pd

def cleanup_duplicate_cache():
    """清理重复缓存"""
    cache = DataCache()
    metadata = cache._metadata.copy()
    
    print("=" * 60)
    print("清理重复缓存数据")
    print("=" * 60)
    
    # 统计当前状态
    print(f"\n清理前:")
    print(f"  总文件数：{len(metadata)}")
    if 'data_type' in metadata.columns:
        print(f"  按类型:")
        for t, c in metadata['data_type'].value_counts().items():
            print(f"    {t}: {c} 个")
    
    # 找出要删除的缓存
    # 保留 daily_full，删除其他类型
    if 'data_type' in metadata.columns:
        to_delete = metadata[metadata['data_type'].isin(['daily', 'index_daily'])]
    else:
        to_delete = metadata
    
    if to_delete.empty:
        print("\n[OK] 没有需要清理的缓存")
        return
    
    print(f"\n需要删除 {len(to_delete)} 个缓存文件...")
    
    # 删除文件
    deleted = 0
    failed = 0
    for _, row in to_delete.iterrows():
        try:
            path = Path(row['path'])
            if path.exists():
                path.unlink()
                deleted += 1
        except Exception as e:
            failed += 1
            print(f"删除失败：{row['path']} - {e}")
    
    # 更新元数据
    if 'data_type' in metadata.columns:
        cache._metadata = metadata[metadata['data_type'] == 'daily_full']
    else:
        cache._metadata = pd.DataFrame(columns=metadata.columns)
    
    cache._save_metadata()
    
    print(f"\n清理完成:")
    print(f"  删除成功：{deleted} 个")
    print(f"  删除失败：{failed} 个")
    print(f"  剩余缓存：{len(cache._metadata)} 个")
    
    # 显示清理后的状态
    print(f"\n清理后:")
    stats = cache.get_cache_stats()
    print(f"  总文件数：{stats['total_files']}")
    print(f"  缓存大小：{stats['total_size_mb']:.2f} MB")
    print(f"  股票数：{stats['stock_count']}")


if __name__ == "__main__":
    cleanup_duplicate_cache()
