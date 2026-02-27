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
        获取交易日历（本地存储，按年份缓存）

        Args:
            exchange: 交易所 SSE(上交所)/SZSE(深交所)
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
        """
        # 解析年份范围
        start_year = start_date[:4] if start_date else str(pd.Timestamp.now().year)
        end_year = end_date[:4] if end_date else str(pd.Timestamp.now().year)
        
        # 按年份获取和缓存交易日历
        all_dates = []
        for year in range(int(start_year), int(end_year) + 1):
            year_start = f"{year}0101"
            year_end = f"{year}1231"
            cache_key_params = {"exchange": exchange, "year": str(year)}
            
            if self.use_cache:
                cached = self.cache.get("trade_cal_year", cache_key_params, year_start, year_end)
                if cached is not None:
                    all_dates.append(cached)
                    continue
            
            # 获取全年交易日历
            cal_df = self.pro.trade_cal(
                exchange=exchange,
                start_date=year_start,
                end_date=year_end,
                fields="cal_date,is_open"
            )
            cal_df = cal_df[cal_df["is_open"] == 1]["cal_date"]
            
            if self.use_cache:
                self.cache.set("trade_cal_year", cache_key_params, 
                              cal_df.to_frame(name="cal_date"), is_complete=True)
            
            all_dates.append(cal_df)
        
        # 合并所有年份数据
        if all_dates:
            result = pd.concat(all_dates, ignore_index=True)
            # 按日期范围过滤
            if start_date and end_date:
                result = result[(result["cal_date"] >= start_date) & (result["cal_date"] <= end_date)]
            return result
        return pd.DataFrame()

    def _get_exchange(self, ts_code: str) -> str:
        """
        根据股票代码获取交易所

        Args:
            ts_code: 股票代码，如 "000001.SZ"

        Returns:
            交易所代码：SSE/SZSE/BJSE
        """
        if ts_code.endswith('.SH'):
            return 'SSE'
        elif ts_code.endswith('.SZ'):
            return 'SZSE'
        elif ts_code.endswith('.BJ'):
            return 'BJSE'
        else:
            # 默认根据代码前缀判断
            if ts_code.startswith('6'):
                return 'SSE'
            elif ts_code.startswith(('0', '3')):
                return 'SZSE'
            else:
                return 'BJSE'

    def _get_suspend_days(self, ts_code: str, start_date: str, end_date: str) -> int:
        """
        获取股票停牌天数（按年份本地存储）

        Args:
            ts_code: 股票代码
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            停牌天数
        """
        # 解析年份范围
        start_year = start_date[:4]
        end_year = end_date[:4]
        
        # 按年份获取和缓存停牌数据
        all_suspend_dates = []
        
        for year in range(int(start_year), int(end_year) + 1):
            year_start = f"{year}0101"
            year_end = f"{year}1231"
            cache_key_params = {"ts_code": ts_code, "year": str(year)}
            
            if self.use_cache:
                cached = self.cache.get("suspend_cal_year", cache_key_params, year_start, year_end)
                if cached is not None and not cached.empty:
                    all_suspend_dates.append(cached)
                    continue
            
            try:
                # 获取全年停牌数据
                suspend_df = self.pro.suspend_cal(
                    ts_code=ts_code,
                    start_date=year_start,
                    end_date=year_end
                )
                
                if suspend_df is not None and not suspend_df.empty:
                    # 转换为日期格式
                    date_col = 'trade_date' if 'trade_date' in suspend_df.columns else suspend_df.columns[0]
                    suspend_df = suspend_df.copy()
                    suspend_df[date_col] = pd.to_datetime(suspend_df[date_col], format='%Y%m%d')
                    
                    if self.use_cache:
                        self.cache.set("suspend_cal_year", cache_key_params, 
                                      suspend_df[[date_col]], is_complete=True)
                    
                    all_suspend_dates.append(suspend_df[[date_col]])
                    
            except Exception as e:
                logger.debug(f"获取停牌数据失败 {ts_code} ({year}年): {e}")
                continue
        
        if not all_suspend_dates:
            return 0
        
        # 合并所有年份数据
        suspend_df = pd.concat(all_suspend_dates, ignore_index=True)
        # 去重
        suspend_df = suspend_df.drop_duplicates()
        # 按日期范围过滤
        mask = (suspend_df.iloc[:, 0] >= pd.to_datetime(start_date, format='%Y%m%d')) & \
               (suspend_df.iloc[:, 0] <= pd.to_datetime(end_date, format='%Y%m%d'))
        
        return int(mask.sum())

    def _calc_expected_trading_days(self, ts_code: str, start_date: str, end_date: str) -> int:
        """
        计算预期交易日天数（考虑实际交易日和股票停牌）

        逻辑：
        1. 获取交易所交易日历（本地存储，按年份缓存）
        2. 获取股票停牌日期（本地存储，按年份缓存）
        3. 预期交易日 = 交易日 - 停牌日

        Args:
            ts_code: 股票代码
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            预期交易日天数（100% 完整度要求）
        """
        exchange = self._get_exchange(ts_code)

        # 1. 获取交易日历
        try:
            trade_cal = self.get_trade_cal(exchange, start_date, end_date)
            if trade_cal is None or trade_cal.empty:
                # 无法获取交易日历，使用估算
                start_dt = pd.to_datetime(start_date, format='%Y%m%d')
                end_dt = pd.to_datetime(end_date, format='%Y%m%d')
                return int(((end_dt - start_dt).days * 250 / 365))

            total_trading_days = len(trade_cal)

        except Exception as e:
            logger.debug(f"获取交易日历失败 {ts_code}: {e}，使用估算")
            start_dt = pd.to_datetime(start_date, format='%Y%m%d')
            end_dt = pd.to_datetime(end_date, format='%Y%m%d')
            return int(((end_dt - start_dt).days * 250 / 365))

        # 2. 获取停牌日期
        suspend_days = self._get_suspend_days(ts_code, start_date, end_date)

        # 3. 预期交易日 = 交易日 - 停牌日（100% 要求，不容错）
        expected_days = max(0, total_trading_days - suspend_days)
        return expected_days

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

        # 计算预期交易日天数（使用实际交易日日历）
        expected_days = self._calc_expected_trading_days(ts_code, start_date, end_date)

        if self.use_cache:
            cached = self.cache.get("daily", cache_key_params, start_date, end_date, expected_days=expected_days)
            if cached is not None:
                logger.debug(f"缓存命中（完整数据）：{ts_code}")
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

            # 处理数据格式（包含重复数据检测和清理）
            df = self._process_daily(df, ts_code)

            if self.use_cache:
                # 检查数据完整性（100% 要求）
                actual_days = len(df)
                
                # 检测重复数据
                duplicates = df.index.duplicated().sum()
                if duplicates > 0:
                    logger.warning(f"{ts_code}: 检测到 {duplicates} 条重复数据，已清理")
                    df = df[~df.index.duplicated(keep='first')]
                    actual_days = len(df)
                
                # 100% 完整度要求
                is_complete = (actual_days == expected_days)
                
                # 超过 100% 说明有异常数据
                if actual_days > expected_days:
                    logger.warning(f"{ts_code}: 数据异常！实际{actual_days}天 > 预期{expected_days}天，可能存在重复")
                    # 尝试清理重复
                    df = df[~df.index.duplicated(keep='first')]
                    actual_days = len(df)
                    is_complete = (actual_days == expected_days)
                
                self.cache.set("daily", cache_key_params, df, is_complete=is_complete)
                logger.info(f"获取数据：{ts_code} ({actual_days}/{expected_days}天，完整={is_complete})")

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
