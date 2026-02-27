"""
统一数据源接口模块

数据源：
- Tushare（付费，稳定可靠）⭐⭐⭐⭐⭐

已移除的数据源：
- AKShare（免费，稳定性太差）
- 聚宽 JoinQuant（需要额外配置）
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


def create_data_provider(
    source: str = "tushare",
    **kwargs
) -> BaseDataProvider:
    """
    工厂函数：创建数据提供者

    Args:
        source: 数据源类型（仅支持 tushare）
        **kwargs: 配置参数

    Returns:
        BaseDataProvider: 数据提供者实例
    """
    if source == "tushare":
        from .tushare_provider import TushareDataProvider
        token = kwargs.get('token') or os.getenv('TUSHARE_TOKEN', '')
        if not token:
            raise ValueError("Tushare Token 未设置，请提供 token 参数或设置 TUSHARE_TOKEN 环境变量")
        return TushareDataProvider(token=token, use_cache=kwargs.get('use_cache', True))
    
    elif source == "auto":
        # auto 也使用 Tushare
        token = kwargs.get('tushare_token') or os.getenv('TUSHARE_TOKEN', '')
        if not token:
            raise ValueError("Tushare Token 未设置，请提供 tushare_token 参数或设置 TUSHARE_TOKEN 环境变量")
        return TushareDataProvider(token=token, use_cache=kwargs.get('use_cache', True))

    else:
        raise ValueError(f"不支持的数据源：{source}。仅支持：tushare")
