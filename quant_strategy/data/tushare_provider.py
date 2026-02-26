"""
Tushare 数据提供者模块
支持获取股票行情、财务数据、指数数据等
"""
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List
from loguru import logger
from tqdm import tqdm

import tushare as ts

from .data_cache import DataCache


class TushareDataProvider:
    """Tushare 数据提供者"""
    
    def __init__(self, token: str = None, use_cache: bool = True):
        """
        初始化数据提供者
        
        Args:
            token: Tushare API token，如为 None 则从环境变量读取
            use_cache: 是否启用本地缓存
        """
        self.token = token or os.getenv("TUSHARE_TOKEN")
        if not self.token:
            raise ValueError("请提供 Tushare token 或设置 TUSHARE_TOKEN 环境变量")
        
        ts.set_token(self.token)
        self.pro = ts.pro_api()
        self.use_cache = use_cache
        self.cache = DataCache() if use_cache else None
        
        logger.info("Tushare 数据提供者初始化成功")
    
    def get_trade_cal(self, exchange: str = "SSE", start_date: str = None, 
                      end_date: str = None) -> pd.DataFrame:
        """
        获取交易日历
        
        Args:
            exchange: 交易所 SSE(上交所)/SZSE(深交所)
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
        """
        params = {"exchange": exchange}
        cache_key_params = {"exchange": exchange, "start": start_date, "end": end_date}
        
        if self.use_cache:
            cached = self.cache.get("trade_cal", cache_key_params, start_date, end_date)
            if cached is not None:
                return cached
        
        cal_df = self.pro.trade_cal(
            exchange=exchange,
            start_date=start_date,
            end_date=end_date,
            fields="cal_date,is_open"
        )
        cal_df = cal_df[cal_df["is_open"] == 1]["cal_date"]
        
        if self.use_cache:
            self.cache.set("trade_cal", cache_key_params, cal_df.to_frame(name="cal_date"))
        
        return cal_df
    
    def get_daily_data(self, ts_code: str, start_date: str, end_date: str,
                       adj: str = "qfq") -> pd.DataFrame:
        """
        获取股票日线数据
        
        Args:
            ts_code: 股票代码，如 "000001.SZ"
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            adj: 复权类型 qfq(前复权)/hfq(后复权)/None(不复权)
            
        Returns:
            包含 open, high, low, close, vol, amount 等字段的 DataFrame
        """
        params = {"ts_code": ts_code, "start": start_date, "end": end_date, "adj": adj}
        cache_key_params = params.copy()
        
        if self.use_cache:
            cached = self.cache.get("daily", cache_key_params, start_date, end_date)
            if cached is not None:
                return cached
        
        try:
            if adj:
                # 获取复权因子
                adj_factor = self.get_adj_factor(ts_code, start_date, end_date)
                df = self.pro.daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    fields="ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount"
                )
                # 应用复权
                df = self._apply_adj_factor(df, adj_factor, adj)
            else:
                df = self.pro.daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    fields="ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount"
                )
            
            df = self._process_daily(df)
            
            if self.use_cache:
                self.cache.set("daily", cache_key_params, df)
            
            return df
        except Exception as e:
            logger.error(f"获取日线数据失败 {ts_code}: {e}")
            return pd.DataFrame()
    
    def _apply_adj_factor(self, df: pd.DataFrame, adj_factor: pd.DataFrame, adj_type: str) -> pd.DataFrame:
        """应用复权因子"""
        if adj_factor.empty:
            return df

        # 确保 trade_date 类型一致
        if not pd.api.types.is_datetime64_any_dtype(df["trade_date"]):
            df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")

        df = df.merge(adj_factor[["trade_date", "adj_factor"]], on="trade_date", how="left")
        df["adj_factor"] = df["adj_factor"].fillna(1.0)
        
        if adj_type == "qfq":
            # 前复权
            base_factor = df["adj_factor"].iloc[-1] if len(df) > 0 else 1.0
            for col in ["open", "high", "low", "close", "pre_close"]:
                df[col] = df[col] * df["adj_factor"] / base_factor
        elif adj_type == "hfq":
            # 后复权
            for col in ["open", "high", "low", "close", "pre_close"]:
                df[col] = df[col] * df["adj_factor"]
        
        df = df.drop(columns=["adj_factor"])
        return df
    
    def _process_daily(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理日线数据格式"""
        if df.empty:
            return df
        
        df = df.sort_values("trade_date").reset_index(drop=True)
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
        df.set_index("trade_date", inplace=True)
        
        # 确保数值列类型正确
        numeric_cols = ["open", "high", "low", "close", "vol", "amount", "pre_close", "change", "pct_chg"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        return df
    
    def get_adj_factor(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取复权因子"""
        df = self.pro.adj_factor(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            fields="ts_code,trade_date,adj_factor"
        )
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
        return df
    
    def get_stock_list(self, exchange: str = None) -> pd.DataFrame:
        """
        获取股票列表
        
        Args:
            exchange: 交易所 SSE/SZSE/BJSE，None 表示全部
        """
        fields = "ts_code,symbol,name,area,industry,market,list_date"
        df = self.pro.stock_basic(exchange=exchange, fields=fields)
        return df
    
    def get_index_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取指数日线数据
        
        Args:
            ts_code: 指数代码，如 "000001.SH" (上证指数)
            start_date: 开始日期
            end_date: 结束日期
        """
        params = {"ts_code": ts_code, "start": start_date, "end": end_date}
        cache_key_params = params.copy()
        
        if self.use_cache:
            cached = self.cache.get("index_daily", cache_key_params, start_date, end_date)
            if cached is not None:
                return cached
        
        df = self.pro.index_daily(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            fields="ts_code,trade_date,close,open,high,low,vol,amount"
        )
        
        df = df.sort_values("trade_date").reset_index(drop=True)
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
        df.set_index("trade_date", inplace=True)
        
        if self.use_cache:
            self.cache.set("index_daily", cache_key_params, df)
        
        return df
    
    def get_multiple_stocks(self, ts_codes: List[str], start_date: str, 
                           end_date: str, adj: str = "qfq") -> dict:
        """
        批量获取多只股票数据
        
        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            adj: 复权类型
            
        Returns:
            {ts_code: DataFrame} 字典
        """
        result = {}
        for ts_code in tqdm(ts_codes, desc="获取股票数据"):
            df = self.get_daily_data(ts_code, start_date, end_date, adj)
            if not df.empty:
                result[ts_code] = df
        return result
    
    def get_suspended(self, ts_code: str = None, start_date: str = None,
                      end_date: str = None) -> pd.DataFrame:
        """获取股票停牌数据"""
        df = self.pro.suspend_cal(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            fields="ts_code,trade_date,suspend_type"
        )
        return df
    
    def get_fina_indicator(self, ts_code: str, start_date: str = None,
                           end_date: str = None) -> pd.DataFrame:
        """
        获取财务指标数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期 (财报日期)
            end_date: 结束日期
        """
        fields = ("ts_code,ann_date,end_date,basic_eps,diluted_eps,"
                  "total_revenue,net_profit,roe,roa,gross_margin,"
                  "current_ratio,quick_ratio,asset_liability_ratio")
        
        df = self.pro.fina_indicator(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            fields=fields
        )

        if not df.empty:
            df["ann_date"] = pd.to_datetime(df["ann_date"], format="%Y%m%d")

        return df

    # ===== 板块数据相关方法（代理到 SectorDataProvider）=====
    
    def get_industry_list(self) -> pd.DataFrame:
        """获取行业板块列表"""
        from .sector_provider import SectorDataProvider
        sector_provider = SectorDataProvider(self.token)
        return sector_provider.get_industry_list()

    def get_concept_list(self) -> pd.DataFrame:
        """获取概念板块列表"""
        from .sector_provider import SectorDataProvider
        sector_provider = SectorDataProvider(self.token)
        return sector_provider.get_concept_list()

    def get_industry_stocks(self, industry_code: str = None,
                           industry_name: str = None) -> pd.DataFrame:
        """获取某行业包含的股票"""
        from .sector_provider import SectorDataProvider
        sector_provider = SectorDataProvider(self.token)
        return sector_provider.get_industry_stocks(industry_code, industry_name)

    def get_concept_stocks(self, concept_code: str = None,
                          concept_name: str = None) -> pd.DataFrame:
        """获取某概念包含的股票"""
        from .sector_provider import SectorDataProvider
        sector_provider = SectorDataProvider(self.token)
        return sector_provider.get_concept_stocks(concept_code, concept_name)

    def get_stock_industry(self, ts_code: str) -> pd.DataFrame:
        """获取股票所属行业"""
        from .sector_provider import SectorDataProvider
        sector_provider = SectorDataProvider(self.token)
        return sector_provider.get_stock_industry(ts_code)

    def get_stock_concepts(self, ts_code: str) -> pd.DataFrame:
        """获取股票所属概念"""
        from .sector_provider import SectorDataProvider
        sector_provider = SectorDataProvider(self.token)
        return sector_provider.get_stock_concepts(ts_code)

    def get_stock_info(self, ts_code: str) -> pd.DataFrame:
        """获取股票基本信息"""
        return self.pro.stock_basic(
            ts_code=ts_code,
            fields="ts_code,name,area,industry,market,list_date,delist_date"
        )
