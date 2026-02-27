"""
清理冗余代码和文档

保留核心文档，删除重复/临时的文档
"""
from pathlib import Path
import shutil

project_root = Path(__file__).parent

# 要删除的冗余文档
redundant_docs = [
    # Bug 修复类（保留最新的）
    "BUG_FIX_LIST_DATE.md",  # 已合并到 DATA_FIX_REPORT.md
    "BUG_FIX_SUMMARY.md",  # 已合并到 DATA_FIX_REPORT.md
    
    # 数据存储类（保留最新的）
    "DATA_PERSISTENCE_STRATEGY.md",  # 旧文档
    "DATA_SOURCE_CLEANUP.md",  # 已合并
    "DATA_SOURCE_CONFIG.md",  # 已合并
    "DATA_STRATEGY_SUMMARY.md",  # 重复
    "DATA_100_PERCENT_COMPLETE.md",  # 重复
    "DATA_COMPLETENESS.md",  # 重复
    "CACHE_PERFORMANCE_REPORT.md",  # 已合并到 STORAGE_ANALYSIS_REPORT.md
    "CLEANUP_COMPLETE_REPORT.md",  # 已合并到 FINAL_STORAGE_STATUS.md
    "STORAGE_ANALYSIS_REPORT.md",  # 保留 STORAGE_OPTIMIZATION_COMPLETE.md
    "DATA_FIX_REPORT.md",  # 保留最终的
    
    # 临时测试文件
    "test_10_stocks.py",  # 临时测试
    "test.yaml",  # 临时配置
    "verify_cleanup.py",  # 临时验证
    "force_cleanup.ps1",  # 临时清理
    
    # 其他重复文档
    "DATA_IMPROVEMENT_SUMMARY.md",  # 重复
    "OPTIMIZATION_REPORT.md",  # 已合并
    "TRADING_DAYS_IMPROVEMENT.md",  # 已实现
    "BACKTEST_HISTORY_GUIDE.md",  # 不常用
    "LEADERS_CONFIG_GUIDE.md",  # 不常用
]

# 要保留的核心文档
core_docs = [
    "README.md",  # 主文档
    "ARCHITECTURE.md",  # 架构说明
    "CONFIG_AND_MODE_GUIDE.md",  # 配置指南
    "DATA_FETCH_GUIDE.md",  # 数据获取指南
    "SECTOR_BACKTEST_GUIDE.md",  # 板块回测指南
    "STRATEGY_IMPLEMENTATION.md",  # 策略实现
    "STRATEGY_MANAGER.md",  # 策略管理
    "AI_ASSISTANT_GUIDE.md",  # AI 助手指南
    "SQLITE_UPGRADE_GUIDE.md",  # SQLite 升级指南
    "STORAGE_OPTIMIZATION_COMPLETE.md",  # 存储优化完成
    "FINAL_STORAGE_STATUS.md",  # 最终存储状态
    "MULTITHREAD_GUIDE.md",  # 多线程指南
]

print("=" * 60)
print("清理冗余文件")
print("=" * 60)

deleted_count = 0
failed_count = 0

# 删除冗余文档
for doc in redundant_docs:
    doc_path = project_root / doc
    if doc_path.exists():
        try:
            # 先备份到 backup/docs 目录
            backup_dir = project_root / "backup" / "docs"
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(doc_path, backup_dir / doc)
            
            # 删除原文件
            doc_path.unlink()
            print(f"[已删除] {doc}")
            deleted_count += 1
        except Exception as e:
            print(f"[失败] {doc}: {e}")
            failed_count += 1
    else:
        print(f"[跳过] {doc} (不存在)")

# 清理 quant_strategy/tools 中的临时文件
tools_dir = project_root / "quant_strategy" / "tools"
temp_tools = [
    "test_fixes.py",  # 测试脚本
    "test_perf_simple.py",  # 性能测试
    "test_cache_performance.py",  # 缓存性能测试
    "cleanup_cache.py",  # 清理脚本（已有新的）
    "cleanup_old_structure.py",  # 旧清理脚本
    "optimize_storage.py",  # 优化脚本（已完成）
    "migrate_to_sqlite.py",  # 迁移脚本（已完成）
]

print("\n清理 tools 目录临时文件:")
for temp in temp_tools:
    temp_path = tools_dir / temp
    if temp_path.exists():
        try:
            temp_path.unlink()
            print(f"[已删除] tools/{temp}")
            deleted_count += 1
        except Exception as e:
            print(f"[失败] tools/{temp}: {e}")
            failed_count += 1

# 统计
print("\n" + "=" * 60)
print(f"清理完成:")
print(f"  删除：{deleted_count} 个文件")
print(f"  失败：{failed_count} 个文件")
print(f"  备份位置：backup/docs/")
print("=" * 60)

# 显示保留的核心文档
print("\n保留的核心文档:")
for doc in core_docs:
    if (project_root / doc).exists():
        print(f"  ✅ {doc}")
    else:
        print(f"  ⚠️  {doc} (不存在)")
