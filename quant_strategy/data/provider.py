"""
统一数据源接口模块
支持多数据源自动切换和故障转移
"""
import os
from typing import List, Optional, Dict
from abc import ABC, abstractmethod
import pandas as pd
from loguru import logger


class BaseDataProvider(ABC):
    """数据提供者基类"""
    
    @abstractmethod
    def get_daily_data(self, ts_code: str, start_date: str, end_date: str,
                       adj: str = "qfq") -> pd.DataFrame:
        """获取日线数据"""
        pass
    
    @abstractmethod
    def get_stock_list(self, exchange: str = None) -> pd.DataFrame:
        """获取股票列表"""
        pass
    
    @abstractmethod
    def get_index_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取指数数据"""
        pass
    
    @abstractmethod
    def get_concept_list(self) -> pd.DataFrame:
        """获取概念列表"""
        pass
    
    @abstractmethod
    def get_concept_stocks(self, concept_name: str = None) -> pd.DataFrame:
        """获取概念成分股"""
        pass
    
    @abstractmethod
    def get_industry_list(self) -> pd.DataFrame:
        """获取行业列表"""
        pass
    
    @abstractmethod
    def get_industry_stocks(self, industry_name: str = None) -> pd.DataFrame:
        """获取行业成分股"""
        pass


class MultiSourceDataProvider(BaseDataProvider):
    """
    多数据源提供者
    
    支持：
    - 自动故障转移
    - 优先级调度
    - 缓存共享
    """
    
    def __init__(self, sources: List[str] = None, **kwargs):
        """
        初始化多数据源提供者
        
        Args:
            sources: 数据源列表，按优先级排序
                     可选值：'akshare', 'tushare', 'jqdata'
            **kwargs: 各数据源的配置参数
        """
        self.sources = sources or ['akshare', 'tushare']
        self.providers: Dict[str, BaseDataProvider] = {}
        self._init_providers(**kwargs)
        
        logger.info(f"多数据源提供者初始化：{self.sources}")
    
    def _init_providers(self, **kwargs):
        """初始化各数据源"""
        for source in self.sources:
            try:
                if source == 'tushare':
                    from .tushare_provider import TushareDataProvider
                    token = kwargs.get('tushare_token') or os.getenv('TUSHARE_TOKEN', '')
                    if token:
                        self.providers['tushare'] = TushareDataProvider(
                            token=token,
                            use_cache=kwargs.get('use_cache', True)
                        )
                        logger.info(f"数据源初始化：{source}")
                    else:
                        logger.warning(f"Tushare token 未设置，跳过 {source}")
                
                elif source == 'akshare':
                    from .akshare_provider import AKShareDataProvider
                    self.providers['akshare'] = AKShareDataProvider(
                        use_cache=kwargs.get('use_cache', True),
                        cache_dir=kwargs.get('cache_dir', './data_cache')
                    )
                    logger.info(f"数据源初始化：{source}")
                
                elif source == 'jqdata':
                    # 聚宽数据源（可选）
                    try:
                        from jqdatasdk import auth
                        user = kwargs.get('jq_user') or os.getenv('JQ_USER', '')
                        password = kwargs.get('jq_password') or os.getenv('JQ_PASSWORD', '')
                        if user and password:
                            auth(user, password)
                            from .jqdata_provider import JoinQuantDataProvider
                            self.providers['jqdata'] = JoinQuantDataProvider()
                            logger.info(f"数据源初始化：{source}")
                    except ImportError:
                        logger.warning(f"jqdatasdk 未安装，跳过 {source}")
                
                else:
                    logger.warning(f"未知数据源：{source}")
                    
            except Exception as e:
                logger.error(f"数据源初始化失败 {source}: {e}")
    
    def get_daily_data(self, ts_code: str, start_date: str, end_date: str,
                       adj: str = "qfq") -> pd.DataFrame:
        """
        获取日线数据（自动故障转移）
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            adj: 复权类型
            
        Returns:
            DataFrame: 日线数据
        """
        last_error = None
        
        for source in self.sources:
            if source not in self.providers:
                continue
            
            try:
                logger.debug(f"尝试从 {source} 获取数据：{ts_code}")
                data = self.providers[source].get_daily_data(
                    ts_code, start_date, end_date, adj
                )
                
                if data is not None and not data.empty:
                    logger.info(f"成功从 {source} 获取数据：{ts_code} ({len(data)}条)")
                    return data
                    
            except Exception as e:
                last_error = e
                logger.warning(f"{source} 获取数据失败：{e}")
                continue
        
        # 所有源都失败
        logger.error(f"所有数据源获取失败：{ts_code}")
        if last_error:
            raise last_error
        return pd.DataFrame()
    
    def get_stock_list(self, exchange: str = None) -> pd.DataFrame:
        """获取股票列表"""
        for source in self.sources:
            if source not in self.providers:
                continue
            try:
                data = self.providers[source].get_stock_list(exchange)
                if data is not None and not data.empty:
                    return data
            except Exception as e:
                logger.warning(f"{source} 获取股票列表失败：{e}")
        return pd.DataFrame()
    
    def get_index_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取指数数据"""
        for source in self.sources:
            if source not in self.providers:
                continue
            try:
                data = self.providers[source].get_index_daily(ts_code, start_date, end_date)
                if data is not None and not data.empty:
                    return data
            except Exception as e:
                logger.warning(f"{source} 获取指数数据失败：{e}")
        return pd.DataFrame()
    
    def get_concept_list(self) -> pd.DataFrame:
        """获取概念列表"""
        for source in self.sources:
            if source not in self.providers:
                continue
            try:
                data = self.providers[source].get_concept_list()
                if data is not None and not data.empty:
                    return data
            except Exception as e:
                logger.warning(f"{source} 获取概念列表失败：{e}")
        return pd.DataFrame()
    
    def get_concept_stocks(self, concept_name: str = None) -> pd.DataFrame:
        """获取概念成分股"""
        for source in self.sources:
            if source not in self.providers:
                continue
            try:
                data = self.providers[source].get_concept_stocks(concept_name)
                if data is not None and not data.empty:
                    return data
            except Exception as e:
                logger.warning(f"{source} 获取概念成分股失败：{e}")
        return pd.DataFrame()
    
    def get_industry_list(self) -> pd.DataFrame:
        """获取行业列表"""
        for source in self.sources:
            if source not in self.providers:
                continue
            try:
                data = self.providers[source].get_industry_list()
                if data is not None and not data.empty:
                    return data
            except Exception as e:
                logger.warning(f"{source} 获取行业列表失败：{e}")
        return pd.DataFrame()
    
    def get_industry_stocks(self, industry_name: str = None) -> pd.DataFrame:
        """获取行业成分股"""
        for source in self.sources:
            if source not in self.providers:
                continue
            try:
                data = self.providers[source].get_industry_stocks(industry_name)
                if data is not None and not data.empty:
                    return data
            except Exception as e:
                logger.warning(f"{source} 获取行业成分股失败：{e}")
        return pd.DataFrame()
    
    def get_area_list(self) -> pd.DataFrame:
        """获取地区列表"""
        for source in self.sources:
            if source not in self.providers:
                continue
            try:
                data = self.providers[source].get_area_list()
                if data is not None and not data.empty:
                    return data
            except Exception as e:
                logger.warning(f"{source} 获取地区列表失败：{e}")
        return pd.DataFrame()
    
    def get_area_stocks(self, area: str) -> pd.DataFrame:
        """获取地区股票"""
        for source in self.sources:
            if source not in self.providers:
                continue
            try:
                data = self.providers[source].get_area_stocks(area)
                if data is not None and not data.empty:
                    return data
            except Exception as e:
                logger.warning(f"{source} 获取地区股票失败：{e}")
        return pd.DataFrame()
    
    def get_stats(self) -> Dict:
        """获取数据源统计信息"""
        stats = {
            "sources": self.sources,
            "active_sources": list(self.providers.keys()),
            "source_status": {}
        }
        
        for name, provider in self.providers.items():
            if hasattr(provider, 'cache') and provider.cache:
                cache_stats = provider.cache.get_stats()
                stats["source_status"][name] = {
                    "cache_hits": cache_stats.get("cache_hits", 0),
                    "cache_misses": cache_stats.get("cache_misses", 0),
                    "hit_rate": cache_stats.get("hit_rate", 0)
                }
            else:
                stats["source_status"][name] = {"status": "active"}
        
        return stats


def create_data_provider(
    source: str = "auto",
    **kwargs
) -> BaseDataProvider:
    """
    工厂函数：创建数据提供者
    
    Args:
        source: 数据源类型
                - 'auto': 自动选择（多数据源）
                - 'tushare': 仅 Tushare
                - 'akshare': 仅 AKShare
                - 'multi': 多数据源
        **kwargs: 配置参数
    
    Returns:
        BaseDataProvider: 数据提供者实例
    """
    if source == "auto" or source == "multi":
        return MultiSourceDataProvider(**kwargs)
    
    elif source == "tushare":
        from .tushare_provider import TushareDataProvider
        token = kwargs.get('token') or os.getenv('TUSHARE_TOKEN', '')
        return TushareDataProvider(token=token, use_cache=kwargs.get('use_cache', True))
    
    elif source == "akshare":
        from .akshare_provider import AKShareDataProvider
        return AKShareDataProvider(
            use_cache=kwargs.get('use_cache', True),
            cache_dir=kwargs.get('cache_dir', './data_cache')
        )
    
    else:
        raise ValueError(f"未知数据源：{source}")
