"""
数据缓存架构升级：SQLite + Parquet

新架构：
data_cache/
├── cache.db              # SQLite 数据库（元数据 + 索引）
├── data/                 # Parquet 数据文件（按交易所分区）
│   ├── SSE/
│   ├── SZSE/
│   └── BJSE/
└── backup/               # 自动备份

优势：
1. 元数据查询快（SQL vs CSV）
2. 支持并发访问（事务安全）
3. 按交易所分区（易管理）
4. 支持增量备份
"""
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import shutil


class SQLiteCacheManager:
    """SQLite 缓存管理器"""
    
    def __init__(self, cache_dir: str = "./data_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # SQLite 数据库路径
        self.db_path = self.cache_dir / "cache.db"
        
        # 数据文件目录
        self.data_dir = self.cache_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 创建缓存元数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                data_type TEXT NOT NULL,
                ts_code TEXT,
                start_date TEXT,
                end_date TEXT,
                adj TEXT,
                exchange TEXT,
                path TEXT NOT NULL,
                file_size INTEGER,
                record_count INTEGER,
                is_complete INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                checksum TEXT
            )
        ''')
        
        # 创建索引（加速查询）
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_type ON cache_metadata(data_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ts_code ON cache_metadata(ts_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_key ON cache_metadata(key)')
        
        # 创建访问日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_accessed_at ON access_log(accessed_at)')
        
        conn.commit()
        conn.close()
        
        print(f"[OK] 数据库初始化完成：{self.db_path}")
    
    def migrate_from_csv(self):
        """从 CSV 元数据迁移到 SQLite"""
        csv_metadata = self.cache_dir / "metadata.csv"
        
        if not csv_metadata.exists():
            print("[INFO] 未找到 CSV 元数据，跳过迁移")
            return
        
        print(f"[INFO] 开始从 CSV 迁移...")
        
        # 读取 CSV
        df = pd.read_csv(csv_metadata)
        print(f"[INFO] 读取到 {len(df)} 条记录")
        
        # 迁移到 SQLite
        conn = sqlite3.connect(str(self.db_path))
        
        # 直接插入
        df.to_sql('cache_metadata', conn, if_exists='append', index=False)
        
        conn.commit()
        conn.close()
        
        print(f"[OK] 迁移完成：{len(df)} 条记录")
        
        # 备份旧 CSV
        backup_path = self.cache_dir / "backup" / f"metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(csv_metadata, backup_path)
        print(f"[OK] 已备份旧 CSV: {backup_path}")
    
    def get_stats(self):
        """获取统计信息"""
        conn = sqlite3.connect(str(self.db_path))
        
        # 总记录数
        total = pd.read_sql_query("SELECT COUNT(*) as count FROM cache_metadata", conn)['count'].iloc[0]
        
        # 按类型统计
        by_type = pd.read_sql_query(
            "SELECT data_type, COUNT(*) as count FROM cache_metadata GROUP BY data_type",
            conn
        )
        
        # 按交易所统计
        by_exchange = pd.read_sql_query(
            "SELECT exchange, COUNT(*) as count FROM cache_metadata WHERE exchange IS NOT NULL GROUP BY exchange",
            conn
        )
        
        # 总大小
        total_size = pd.read_sql_query(
            "SELECT SUM(file_size) as size FROM cache_metadata",
            conn
        )['size'].iloc[0] or 0
        
        conn.close()
        
        return {
            'total_files': total,
            'total_size_mb': total_size / 1024 / 1024,
            'by_type': by_type.to_dict('records'),
            'by_exchange': by_exchange.to_dict('records')
        }


def main():
    """主函数：执行迁移"""
    print("=" * 60)
    print("SQLite + Parquet 架构升级")
    print("=" * 60)
    
    # 创建管理器
    manager = SQLiteCacheManager()
    
    # 执行迁移
    manager.migrate_from_csv()
    
    # 显示统计
    print("\n迁移后统计:")
    stats = manager.get_stats()
    print(f"  总文件数：{stats['total_files']}")
    print(f"  总大小：{stats['total_size_mb']:.2f} MB")
    
    if stats['by_type']:
        print("  按类型:")
        for row in stats['by_type']:
            print(f"    {row['data_type']}: {row['count']} 个")
    
    if stats['by_exchange']:
        print("  按交易所:")
        for row in stats['by_exchange']:
            print(f"    {row['exchange']}: {row['count']} 个")
    
    print("\n" + "=" * 60)
    print("[OK] 架构升级完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
