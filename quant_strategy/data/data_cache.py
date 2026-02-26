"""
数据缓存模块
支持本地缓存 Tushare 数据，减少 API 调用
"""
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from loguru import logger


class DataCache:
    """本地数据缓存管理"""

    def __init__(self, cache_dir: str = "./data_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.cache_dir / "metadata.csv"
        self._metadata = self._load_metadata()

    def _load_metadata(self) -> pd.DataFrame:
        """加载缓存元数据"""
        if self.metadata_file.exists():
            return pd.read_csv(self.metadata_file)
        return pd.DataFrame(columns=["key", "path", "updated_at", "start_date", "end_date", "data_type", "ts_code"])

    def _save_metadata(self):
        """保存缓存元数据"""
        self._metadata.to_csv(self.metadata_file, index=False)

    def _generate_key(self, data_type: str, params: dict) -> str:
        """生成缓存键"""
        param_str = "_".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{data_type}_{param_str}"

    def get(self, data_type: str, params: dict, start_date: str = None, end_date: str = None) -> pd.DataFrame | None:
        """
        从缓存获取数据

        Args:
            data_type: 数据类型 (daily, adj_factor, etc.)
            params: 查询参数
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            缓存的数据，如果不存在或过期则返回 None
        """
        key = self._generate_key(data_type, params)
        cache_entry = self._metadata[self._metadata["key"] == key]

        if cache_entry.empty:
            return None

        cache_path = Path(cache_entry.iloc[0]["path"])
        if not cache_path.exists():
            return None

        try:
            df = pd.read_parquet(cache_path) if cache_path.suffix == ".parquet" else pd.read_csv(cache_path)

            # 日期范围检查
            if start_date and end_date and "trade_date" in df.columns:
                df["trade_date"] = df["trade_date"].astype(str)
                mask = (df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)
                if mask.sum() == 0:
                    return None

            logger.debug(f"缓存命中：{key}")
            return df
        except Exception as e:
            logger.warning(f"读取缓存失败：{e}")
            return None

    def set(self, data_type: str, params: dict, df: pd.DataFrame):
        """
        保存数据到缓存

        Args:
            data_type: 数据类型
            params: 查询参数
            df: 要缓存的 DataFrame
        """
        key = self._generate_key(data_type, params)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{key}_{timestamp}.parquet"
        cache_path = self.cache_dir / filename

        try:
            df.to_parquet(cache_path, index=False)

            # 更新元数据
            new_entry = pd.DataFrame([{
                "key": key,
                "path": str(cache_path),
                "updated_at": timestamp,
                "start_date": df["trade_date"].min() if "trade_date" in df.columns else None,
                "end_date": df["trade_date"].max() if "trade_date" in df.columns else None,
                "data_type": data_type,
                "ts_code": params.get("ts_code", "")
            }])

            self._metadata = pd.concat([self._metadata, new_entry], ignore_index=True)
            self._save_metadata()
            logger.debug(f"缓存保存：{key} -> {cache_path}")
        except Exception as e:
            logger.error(f"保存缓存失败：{e}")

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
                "data_types": {}
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
        
        return {
            "total_files": len(self._metadata),
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "stock_count": stock_count,
            "data_types": data_types
        }

    def clear(self, older_than_days: int = None):
        """
        清理缓存

        Args:
            older_than_days: 如果指定，只清理超过此天数的缓存
        """
        import time
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
