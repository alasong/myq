"""
清理旧数据结构

删除已迁移到 SQLite 的旧文件：
- metadata.csv (已迁移到 cache.db)
- access_log.csv (已迁移到 cache.db)
- 根目录的 parquet 文件（已移动到 SSE/SZSE/BJSE）
"""
from pathlib import Path
import sqlite3
import shutil

cache_dir = Path("data_cache")

print("=" * 60)
print("清理旧数据结构")
print("=" * 60)

# 1. 备份旧文件（以防万一）
backup_dir = cache_dir / "backup" / "old_structure"
backup_dir.mkdir(parents=True, exist_ok=True)

files_to_remove = []

# 检查 metadata.csv
old_metadata = cache_dir / "metadata.csv"
if old_metadata.exists():
    backup_path = backup_dir / "metadata.csv.bak"
    shutil.copy2(old_metadata, backup_path)
    files_to_remove.append(("metadata.csv", old_metadata.stat().st_size / 1024))
    print(f"\n[准备删除] metadata.csv ({old_metadata.stat().st_size / 1024:.1f} KB)")
    print(f"  已备份到：{backup_path}")

# 检查 access_log.csv
old_access_log = cache_dir / "access_log.csv"
if old_access_log.exists():
    backup_path = backup_dir / "access_log.csv.bak"
    shutil.copy2(old_access_log, backup_path)
    files_to_remove.append(("access_log.csv", old_access_log.stat().st_size / 1024))
    print(f"\n[准备删除] access_log.csv ({old_access_log.stat().st_size / 1024:.1f} KB)")
    print(f"  已备份到：{backup_path}")

# 检查根目录的 parquet 文件（应该都已在 SSE/SZSE/BJSE 目录中）
root_parquet = list(cache_dir.glob("*.parquet"))
if root_parquet:
    print(f"\n[注意] 根目录发现 {len(root_parquet)} 个 parquet 文件")
    print("  这些文件应该移动到 SSE/SZSE/BJSE 目录")
    
    # 从 SQLite 检查这些文件是否已在新目录中
    conn = sqlite3.connect(str(cache_dir / "cache.db"))
    for f in root_parquet[:10]:  # 只显示前 10 个
        # 检查是否有相同文件名的文件在子目录中
        filename = f.name
        in_subdir = any((cache_dir / d / filename).exists() for d in ["SSE", "SZSE", "BJSE"])
        if in_subdir:
            print(f"  重复：{filename} (在子目录中已存在)")
    
    conn.close()

# 确认删除
if files_to_remove:
    print(f"\n共准备删除 {len(files_to_remove)} 个旧文件:")
    for name, size in files_to_remove:
        print(f"  - {name} ({size:.1f} KB)")
    
    confirm = input("\n是否确认删除？(y/n): ")
    if confirm.lower() == 'y':
        for name, path in [("metadata.csv", old_metadata), ("access_log.csv", old_access_log)]:
            if path.exists():
                path.unlink()
                print(f"[已删除] {name}")
    else:
        print("\n[已取消] 保留旧文件")
else:
    print("\n[OK] 没有需要清理的旧文件")

# 显示清理后状态
print("\n" + "=" * 60)
print("清理后状态")
print("=" * 60)

import subprocess
result = subprocess.run(
    ["powershell", "-Command", 
     "Get-ChildItem data_cache -File | Select-Object Name, Length | Format-Table"],
    capture_output=True, text=True
)
print("\n根目录文件:")
print(result.stdout if result.stdout else "  (无)")

print("\n子目录:")
for d in ["SSE", "SZSE", "BJSE"]:
    count = len(list((cache_dir / d).glob("*.parquet")))
    print(f"  {d}/: {count} 个 parquet 文件")

print("\n[OK] 清理完成！")
