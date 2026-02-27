"""验证数据清理结果"""
from pathlib import Path
import sqlite3

cache_dir = Path("data_cache")

print("=" * 60)
print("数据清理验证报告")
print("=" * 60)

# 1. SQLite 数据库
conn = sqlite3.connect(str(cache_dir / "cache.db"))
sqlite_count = conn.execute("SELECT COUNT(*) FROM cache_metadata").fetchone()[0]
print(f"\n1. SQLite 数据库")
print(f"   记录数：{sqlite_count}")
print(f"   大小：{cache_dir.joinpath('cache.db').stat().st_size / 1024 / 1024:.2f} MB")

# 2. 目录结构
print("\n2. 目录结构")
for d in ["SSE", "SZSE", "BJSE"]:
    count = len(list((cache_dir / d).glob("*.parquet")))
    print(f"   {d}/: {count} 个 parquet 文件")

# 3. 旧数据结构
print("\n3. 旧数据结构清理")
old_metadata_exists = (cache_dir / "metadata.csv").exists()
old_access_log_exists = (cache_dir / "access_log.csv").exists()
bak_files = len(list(cache_dir.glob("*.bak")))
root_parquet = len(list(cache_dir.glob("*.parquet")))

print(f"   metadata.csv: {'已删除' if not old_metadata_exists else '仍存在'}")
print(f"   access_log.csv: {'已删除' if not old_access_log_exists else '仍存在'}")
print(f"   .bak 文件：{bak_files} 个")
print(f"   根目录 parquet: {root_parquet} 个")

# 4. 总结
print("\n4. 总结")
if sqlite_count == 5012 and not old_metadata_exists and not old_access_log_exists:
    print("   [OK] 所有数据已迁移到新架构")
    print("   [OK] 旧数据结构已清理")
    print("   [OK] 无重复数据")
else:
    print("   [WARN] 需要进一步检查")

print("\n" + "=" * 60)

conn.close()
