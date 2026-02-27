"""
数据缓存模块
支持本地缓存 Tushare 数据，减少 API 调用
优化功能：
- TTL 过期检查
- LRU 淘汰策略
- 缓存大小限制
- 数据完整性标志（新增）
"""
import os
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
import time
from typing import List, Dict, Optional
from collections import OrderedDict


class DataCache:
    """本地数据缓存管理"""

    def __init__(self, cache_dir: str = "./data_cache",
                 max_size_mb: float = 1024,
                 ttl_days: int = 30,
                 compression: str = "gzip"):
        """
        初始化数据缓存

        Args:
            cache_dir: 缓存目录
            max_size_mb: 最大缓存大小 (MB)
            ttl_days: 缓存 TTL (天)
            compression: 压缩方式 (none/snappy/gzip/brotli/zstd)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.cache_dir / "metadata.csv"
        self._metadata = self._load_metadata()

        # 缓存配置
        self.max_size_mb = max_size_mb
        self.ttl_days = ttl_days
        self.compression = compression  # 压缩算法

        # 数据完整性配置
        self.completeness_check = True  # 是否检查数据完整性

        # LRU 访问记录
        self._access_log = OrderedDict()
        self._load_access_log()

        # 内存缓存统计
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0
        }

    def _load_metadata(self) -> pd.DataFrame:
        """加载缓存元数据"""
        if self.metadata_file.exists():
            return pd.read_csv(self.metadata_file)
        return pd.DataFrame(columns=["key", "path", "updated_at", "start_date", "end_date", "data_type", "ts_code", "is_complete", "record_count"])

    def _save_metadata(self):
        """保存缓存元数据"""
        self._metadata.to_csv(self.metadata_file, index=False)
    
    def _load_access_log(self):
        """加载 LRU 访问日志"""
        access_file = self.cache_dir / "access_log.csv"
        if access_file.exists():
            try:
                df = pd.read_csv(access_file)
                for _, row in df.iterrows():
                    self._access_log[row["key"]] = row["timestamp"]
            except:
                pass
    
    def _save_access_log(self):
        """保存 LRU 访问日志"""
        access_file = self.cache_dir / "access_log.csv"
        df = pd.DataFrame([
            {"key": key, "timestamp": ts}
            for key, ts in self._access_log.items()
        ])
        if not df.empty:
            df.to_csv(access_file, index=False)

    def _generate_key(self, data_type: str, params: dict) -> str:
        """
        生成缓存键
        
        P1-1: 使用哈希避免冲突和长度限制
        """
        param_str = "_".join(f"{k}={v}" for k, v in sorted(params.items()))
        
        # P1-1: 限制长度，超过 100 字符使用 MD5 哈希
        if len(param_str) > 100:
            import hashlib
            param_str = hashlib.md5(param_str.encode()).hexdigest()
        
        return f"{data_type}_{param_str}"
    
    def _update_access_log(self, key: str):
        """更新访问日志（LRU）"""
        if key in self._access_log:
            del self._access_log[key]
        self._access_log[key] = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 限制访问日志大小
        if len(self._access_log) > 10000:
            # 保留最近的 5000 条
            keys = list(self._access_log.keys())[5000:]
            for k in list(self._access_log.keys())[:5000]:
                del self._access_log[k]
        
        self._save_access_log()
    
    def _get_cache_age_days(self, updated_at: str) -> float:
        """获取缓存年龄（天）"""
        try:
            cache_time = datetime.strptime(updated_at, "%Y%m%d_%H%M%S")
            age = datetime.now() - cache_time
            return age.total_seconds() / 86400
        except:
            return 999999  # 无法解析时认为非常老
    
    def _check_ttl_expired(self, updated_at: str) -> bool:
        """检查 TTL 是否过期"""
        age_days = self._get_cache_age_days(updated_at)
        return age_days > self.ttl_days
    
    def _enforce_size_limit(self):
        """执行缓存大小限制（LRU 淘汰）"""
        current_size_mb = self._get_total_size_mb()

        if current_size_mb <= self.max_size_mb:
            return

        # 按 LRU 顺序淘汰
        keys_to_remove = list(self._access_log.keys())

        for key in keys_to_remove:
            if current_size_mb <= self.max_size_mb * 0.8:  # 淘汰到 80% 以下
                break

            # 找到对应的元数据
            cache_entry = self._metadata[self._metadata["key"] == key]
            if not cache_entry.empty:
                # P0-1: 跳过 daily_full 类型（永久保存的数据）
                data_type = cache_entry.iloc[0].get("data_type", "")
                if data_type == "daily_full":
                    logger.debug(f"跳过 daily_full 类型缓存：{key}（永久保存）")
                    continue

                path = cache_entry.iloc[0]["path"]
                try:
                    if Path(path).exists():
                        file_size = Path(path).stat().st_size / 1024 / 1024
                        Path(path).unlink()
                        current_size_mb -= file_size
                        self._metadata = self._metadata[self._metadata["key"] != key]
                        self._stats["evictions"] += 1
                        logger.debug(f"LRU 淘汰：{key} ({file_size:.2f} MB)")
                except Exception as e:
                    logger.warning(f"淘汰缓存失败：{e}")

            if key in self._access_log:
                del self._access_log[key]

        self._save_metadata()
    
    def _get_total_size_mb(self) -> float:
        """获取当前缓存总大小 (MB)"""
        total_size = 0
        for _, row in self._metadata.iterrows():
            try:
                total_size += Path(row["path"]).stat().st_size
            except:
                pass
        return total_size / 1024 / 1024

    def get(self, data_type: str, params: dict, start_date: str = None, end_date: str = None,
            expected_days: int = None) -> pd.DataFrame | None:
        """
        从缓存获取数据

        Args:
            data_type: 数据类型 (daily, adj_factor, etc.)
            params: 查询参数
            start_date: 开始日期
            end_date: 结束日期
            expected_days: 预期数据天数（用于完整性检查）

        Returns:
            缓存的数据，如果不存在或过期则返回 None
        """
        key = self._generate_key(data_type, params)
        cache_entry = self._metadata[self._metadata["key"] == key]

        if cache_entry.empty:
            self._stats["misses"] += 1
            return None

        row = cache_entry.iloc[0]
        
        # 检查 TTL
        updated_at = row["updated_at"]
        if self._check_ttl_expired(updated_at):
            logger.debug(f"缓存过期：{key} (已 {self._get_cache_age_days(updated_at):.1f} 天)")
            self._delete_cache_entry(row)
            self._stats["misses"] += 1
            return None

        cache_path = Path(row["path"])
        if not cache_path.exists():
            self._stats["misses"] += 1
            return None

        # 检查数据完整性（如果标记为完整）
        is_complete = row.get("is_complete", False) if "is_complete" in cache_entry.columns else False

        if is_complete:
            # 完整数据，直接返回
            logger.debug(f"缓存命中（完整数据）：{key}")
            self._stats["hits"] += 1
            self._update_access_log(key)
            try:
                df = pd.read_parquet(cache_path)

                # P0-2: 对于 daily_full 类型，需要按日期范围过滤（使用索引过滤）
                if data_type == "daily_full" and start_date and end_date:
                    # 确保索引是 datetime 类型
                    if not pd.api.types.is_datetime64_any_dtype(df.index):
                        # 尝试多种格式转换
                        try:
                            df.index = pd.to_datetime(df.index, format='%Y%m%d')
                        except (ValueError, TypeError):
                            # 如果已经是 datetime 或其他格式，自动推断
                            df.index = pd.to_datetime(df.index)
                    
                    # 使用索引过滤（daily_full 数据已设置索引为 trade_date）
                    start_dt = pd.to_datetime(start_date, format='%Y%m%d')
                    end_dt = pd.to_datetime(end_date, format='%Y%m%d')
                    mask = (df.index >= start_dt) & (df.index <= end_dt)
                    result = df[mask].copy()
                    return result

                return df
            except Exception as e:
                logger.warning(f"读取缓存失败：{e}")
                self._stats["misses"] += 1
                return None

        # 非完整数据，需要验证
        try:
            df = pd.read_parquet(cache_path) if cache_path.suffix == ".parquet" else pd.read_csv(cache_path)

            # 日期范围检查
            if start_date and end_date and "trade_date" in df.columns:
                df["trade_date"] = df["trade_date"].astype(str)
                mask = (df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)
                if mask.sum() == 0:
                    self._stats["misses"] += 1
                    return None

                # 如果有预期天数，检查数据完整性（100% 要求）
                if expected_days and self.completeness_check:
                    actual_days = mask.sum()
                    
                    # 检测重复数据
                    if "trade_date" in df.columns:
                        duplicates = df["trade_date"].duplicated().sum()
                        if duplicates > 0:
                            logger.warning(f"缓存数据存在重复：{key} ({duplicates}条重复)")
                            self._stats["misses"] += 1
                            return None
                    
                    completeness = actual_days / expected_days
                    
                    # 100% 完整度要求
                    if actual_days < expected_days:
                        logger.debug(f"缓存数据不完整：{key} (期望{expected_days}天，实际{actual_days}天，完整度{completeness:.1%})")
                        self._stats["misses"] += 1
                        return None
                    elif actual_days == expected_days:
                        # 标记为完整数据
                        self._mark_as_complete(key, actual_days)
                    elif actual_days > expected_days:
                        # 超过预期，可能存在重复
                        logger.warning(f"缓存数据异常：{key} (期望{expected_days}天，实际{actual_days}天，可能存在重复)")
                        self._stats["misses"] += 1
                        return None

            logger.debug(f"缓存命中：{key}")
            self._stats["hits"] += 1
            self._update_access_log(key)  # 更新 LRU
            return df
        except Exception as e:
            logger.warning(f"读取缓存失败：{e}")
            self._stats["misses"] += 1
            return None
    
    def _mark_as_complete(self, key: str, record_count: int):
        """
        标记缓存数据为完整
        
        Args:
            key: 缓存键
            record_count: 记录数
        """
        mask = self._metadata["key"] == key
        if mask.any():
            self._metadata.loc[mask, "is_complete"] = True
            self._metadata.loc[mask, "record_count"] = record_count
            self._save_metadata()
            logger.debug(f"标记缓存为完整数据：{key} ({record_count}条记录)")

    def set(self, data_type: str, params: dict, df: pd.DataFrame, is_complete: bool = False):
        """
        保存数据到缓存

        Args:
            data_type: 数据类型
            params: 查询参数
            df: 要缓存的 DataFrame
            is_complete: 是否标记为完整数据
        """
        # 先执行 LRU 淘汰，确保有空间
        self._enforce_size_limit()

        key = self._generate_key(data_type, params)
        
        # P0-3: 删除旧的相同 key 的记录，确保每个 key 只有一条记录
        old_entry = self._metadata[self._metadata["key"] == key]
        if not old_entry.empty:
            # 删除旧的缓存文件
            for _, row in old_entry.iterrows():
                try:
                    old_path = Path(row["path"])
                    if old_path.exists():
                        old_path.unlink()
                        logger.debug(f"删除旧缓存文件：{old_path}")
                except Exception as e:
                    logger.warning(f"删除旧缓存文件失败：{e}")
            
            # 删除旧的元数据记录
            self._metadata = self._metadata[self._metadata["key"] != key]
            logger.debug(f"清理旧元数据记录：{key}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{key}_{timestamp}.parquet"
        cache_path = self.cache_dir / filename

        try:
            # 使用指定的压缩算法保存 Parquet
            # compression 选项：None, 'snappy', 'gzip', 'brotli', 'zstd'
            compression_opts = self.compression if self.compression != 'none' else None
            
            df.to_parquet(cache_path, index=False, compression=compression_opts)

            # 计算记录数
            record_count = len(df)

            # 更新元数据（添加新记录）
            new_entry = pd.DataFrame([{
                "key": key,
                "path": str(cache_path),
                "updated_at": timestamp,
                "start_date": df["trade_date"].min() if "trade_date" in df.columns else None,
                "end_date": df["trade_date"].max() if "trade_date" in df.columns else None,
                "data_type": data_type,
                "ts_code": params.get("ts_code", ""),
                "is_complete": is_complete,
                "record_count": record_count
            }])

            self._metadata = pd.concat([self._metadata, new_entry], ignore_index=True)
            self._save_metadata()

            # 更新 LRU 访问
            self._update_access_log(key)

            logger.debug(f"缓存保存：{key} -> {cache_path} ({record_count}条记录，完整={is_complete})")
        except Exception as e:
            logger.error(f"保存缓存失败：{e}")
    
    def _delete_cache_entry(self, entry: pd.Series):
        """删除缓存条目"""
        try:
            cache_path = Path(entry["path"])
            if cache_path.exists():
                cache_path.unlink()
            self._metadata = self._metadata[self._metadata["key"] != entry["key"]]
            if entry["key"] in self._access_log:
                del self._access_log[entry["key"]]
            self._save_metadata()
        except Exception as e:
            logger.warning(f"删除缓存失败：{e}")

    def list_cache(self, data_type: str = None, ts_code: str = None) -> pd.DataFrame:
        """
        列出缓存中的数据

        Args:
            data_type: 数据类型过滤
            ts_code: 股票代码过滤

        Returns:
            缓存元数据 DataFrame
        """
        df = self._metadata.copy()

        if data_type:
            df = df[df["data_type"] == data_type]

        if ts_code:
            df = df[df["ts_code"] == ts_code]

        # 添加文件大小信息
        if not df.empty:
            df["size_mb"] = df["path"].apply(
                lambda x: round(Path(x).stat().st_size / 1024 / 1024, 2) if Path(x).exists() else 0
            )
            # 添加缓存年龄
            df["age_days"] = df["updated_at"].apply(
                lambda x: round(self._get_cache_age_days(x), 1)
            )
            # 添加是否过期标记
            df["expired"] = df["updated_at"].apply(
                lambda x: self._check_ttl_expired(x)
            )
            # 添加完整性标记
            if "is_complete" in df.columns:
                df["complete"] = df["is_complete"].apply(lambda x: "✅" if x else "⚠️")
            if "record_count" in df.columns:
                df["records"] = df["record_count"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "N/A")

        return df

    def get_cached_stocks(self) -> list:
        """
        获取缓存中所有股票代码列表

        Returns:
            股票代码列表
        """
        if self._metadata.empty:
            return []
        return self._metadata["ts_code"].dropna().unique().tolist()

    def get_cache_stats(self) -> dict:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        if self._metadata.empty:
            return {
                "total_files": 0,
                "total_size_mb": 0,
                "stock_count": 0,
                "data_types": {},
                "hit_rate": 0,
                "evictions": 0
            }

        total_size = 0
        for _, row in self._metadata.iterrows():
            try:
                total_size += Path(row["path"]).stat().st_size
            except:
                pass

        # 兼容旧数据（没有 data_type 列）
        if "data_type" in self._metadata.columns:
            data_types = self._metadata["data_type"].value_counts().to_dict()
        else:
            data_types = {}

        if "ts_code" in self._metadata.columns:
            stock_count = self._metadata["ts_code"].dropna().nunique()
        else:
            stock_count = 0
        
        # 计算命中率
        total_access = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_access if total_access > 0 else 0

        return {
            "total_files": len(self._metadata),
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "stock_count": stock_count,
            "data_types": data_types,
            "hit_rate": hit_rate,
            "evictions": self._stats["evictions"],
            "max_size_mb": self.max_size_mb,
            "ttl_days": self.ttl_days
        }

    def clear(self, older_than_days: int = None):
        """
        清理缓存

        Args:
            older_than_days: 如果指定，只清理超过此天数的缓存
        """
        cutoff = time.time() - (older_than_days * 86400) if older_than_days else 0

        for _, row in self._metadata.iterrows():
            try:
                cache_path = Path(row["path"])
                if cache_path.exists():
                    if older_than_days:
                        mtime = cache_path.stat().st_mtime
                        if mtime < cutoff:
                            cache_path.unlink()
                    else:
                        cache_path.unlink()
            except Exception as e:
                logger.warning(f"清理缓存失败：{e}")

        if older_than_days:
            self._metadata = self._metadata[self._metadata["updated_at"].apply(
                lambda x: datetime.strptime(x, "%Y%m%d_%H%M%S").timestamp() >= cutoff
            )]
        else:
            self._metadata = pd.DataFrame(columns=self._metadata.columns)

        self._save_metadata()
        logger.info(f"缓存清理完成")
    
    def get_stats(self) -> dict:
        """获取详细统计信息"""
        stats = self.get_cache_stats()
        stats.update({
            "cache_hits": self._stats["hits"],
            "cache_misses": self._stats["misses"],
            "lru_entries": len(self._access_log)
        })
        return stats

    def get_cache_report(self) -> dict:
        """
        P2-2: 生成缓存统计报告
        
        Returns:
            缓存统计报告字典
        """
        if self._metadata.empty:
            return {
                "total_size_mb": 0,
                "total_files": 0,
                "by_type": {},
                "complete_count": 0,
                "incomplete_count": 0,
                "oldest_cache": None,
                "newest_cache": None,
                "avg_age_days": 0,
                "stock_count": 0
            }
        
        # 按类型统计
        by_type = self._metadata.groupby("data_type").size().to_dict()
        
        # 完整/不完整统计
        if "is_complete" in self._metadata.columns:
            complete_count = len(self._metadata[self._metadata["is_complete"] == True])
            incomplete_count = len(self._metadata[self._metadata["is_complete"] == False])
        else:
            complete_count = len(self._metadata)
            incomplete_count = 0
        
        # 计算缓存年龄
        def parse_age_days(updated_at: str) -> float:
            try:
                return self._get_cache_age_days(updated_at)
            except:
                return 0
        
        ages = self._metadata["updated_at"].apply(parse_age_days)
        avg_age_days = ages.mean() if not ages.empty else 0
        
        # 最早和最晚缓存
        try:
            oldest_cache = pd.to_datetime(self._metadata["updated_at"].min(), format='%Y%m%d_%H%M%S')
            newest_cache = pd.to_datetime(self._metadata["updated_at"].max(), format='%Y%m%d_%H%M%S')
        except:
            oldest_cache = None
            newest_cache = None
        
        # 股票数量
        stock_count = 0
        if "ts_code" in self._metadata.columns:
            stock_count = self._metadata["ts_code"].dropna().nunique()
        
        return {
            "total_size_mb": self._get_total_size_mb(),
            "total_files": len(self._metadata),
            "by_type": by_type,
            "complete_count": complete_count,
            "incomplete_count": incomplete_count,
            "oldest_cache": oldest_cache,
            "newest_cache": newest_cache,
            "avg_age_days": round(avg_age_days, 1),
            "stock_count": stock_count
        }

    def export_cache(self, output_dir: str, ts_codes: List[str] = None, data_types: List[str] = None):
        """
        P2-3: 导出指定股票的缓存数据（用于备份或迁移）
        
        Args:
            output_dir: 输出目录
            ts_codes: 股票代码列表，None 表示导出所有
            data_types: 数据类型列表，None 表示导出所有
        """
        import shutil
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 筛选要导出的数据
        export_df = self._metadata.copy()
        
        if ts_codes:
            export_df = export_df[export_df["ts_code"].isin(ts_codes)]
        
        if data_types:
            export_df = export_df[export_df["data_type"].isin(data_types)]
        
        if export_df.empty:
            logger.warning("没有要导出的缓存数据")
            return
        
        # 复制缓存文件
        exported_count = 0
        for _, row in export_df.iterrows():
            try:
                src_path = Path(row["path"])
                if src_path.exists():
                    # 保持相对路径结构
                    rel_path = src_path.relative_to(self.cache_dir)
                    dst_path = output_path / rel_path
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dst_path)
                    exported_count += 1
            except Exception as e:
                logger.warning(f"导出缓存文件失败 {row['path']}: {e}")
        
        # 导出元数据
        export_df.to_csv(output_path / "metadata.csv", index=False)
        
        logger.info(f"缓存导出完成：{exported_count} 个文件 -> {output_dir}")

    def import_cache(self, input_dir: str, merge: bool = True):
        """
        P2-3: 导入缓存数据（从备份恢复）
        
        Args:
            input_dir: 输入目录（包含 metadata.csv 和缓存文件）
            merge: 是否合并到现有缓存（True=合并，False=替换）
        """
        import shutil
        
        input_path = Path(input_dir)
        metadata_file = input_path / "metadata.csv"
        
        if not metadata_file.exists():
            logger.error(f"导入失败：未找到元数据文件 {metadata_file}")
            return False
        
        try:
            # 加载导入的元数据
            import_df = pd.read_csv(metadata_file)
            
            if import_df.empty:
                logger.warning("导入的元数据为空")
                return False
            
            # 复制缓存文件
            imported_count = 0
            for _, row in import_df.iterrows():
                try:
                    src_path = input_path / row["path"]
                    if src_path.exists():
                        # 复制到本地缓存目录
                        dst_path = self.cache_dir / src_path.name
                        shutil.copy2(src_path, dst_path)
                        
                        # 更新路径为本地路径
                        row["path"] = str(dst_path)
                        
                        imported_count += 1
                except Exception as e:
                    logger.warning(f"导入缓存文件失败 {row['path']}: {e}")
            
            # 合并元数据
            if merge:
                # 删除已存在的相同 key
                for key in import_df["key"].unique():
                    self._metadata = self._metadata[self._metadata["key"] != key]
                
                self._metadata = pd.concat([self._metadata, import_df], ignore_index=True)
            else:
                self._metadata = import_df
            
            self._save_metadata()
            logger.info(f"缓存导入完成：{imported_count} 个文件从 {input_dir}")
            return True
            
        except Exception as e:
            logger.error(f"导入缓存失败：{e}")
            return False
