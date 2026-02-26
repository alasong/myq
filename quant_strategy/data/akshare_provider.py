"""
AKShare 数据提供者模块
完全免费的开源金融数据接口
https://akshare.akfamily.xyz/
"""
import os
import pandas as pd
from datetime import datetime
from typing import Optional, List
from loguru import logger

from .data_cache import DataCache


class AKShareDataProvider:
    """AKShare 数据提供者"""

    def __init__(self, use_cache: bool = True, cache_dir: str = "./data_cache"):
        """
        初始化 AKShare 数据提供者

        Args:
            use_cache: 是否启用本地缓存
            cache_dir: 缓存目录
        """
        self.use_cache = use_cache
        self.cache = DataCache(cache_dir) if use_cache else None
        
        # 延迟导入 akshare（避免不必要的依赖）
        self._ak = None
        
        logger.info("AKShare 数据提供者初始化成功")

    @property
    def ak(self):
        """延迟加载 akshare"""
        if self._ak is None:
            try:
                import akshare as ak
                self._ak = ak
            except ImportError:
                raise ImportError("请安装 akshare: pip install akshare")
        return self._ak

    def _convert_ts_code(self, ts_code: str) -> str:
        """
        转换股票代码格式
        
        Tushare: 000001.SZ
        AKShare: 000001 或 sz000001
        
        Args:
            ts_code: Tushare 格式股票代码
            
        Returns:
            AKShare 格式股票代码
        """
        if '.' in ts_code:
            code, exchange = ts_code.split('.')
            # 转换交易所代码
            exchange_map = {
                'SZ': 'sz',
                'SH': 'sh',
                'BJ': 'bj'
            }
            prefix = exchange_map.get(exchange, '')
            return f"{prefix}{code}"
        return ts_code

    def get_daily_data(self, ts_code: str, start_date: str, end_date: str,
                       adj: str = "qfq") -> pd.DataFrame:
        """
        获取股票日线数据

        Args:
            ts_code: 股票代码 (Tushare 格式，如 000001.SZ)
            start_date: 开始日期 YYYYMMDD
            start_date: 结束日期 YYYYMMDD
            adj: 复权类型 qfq(前复权)/hfq(后复权)/none(不复权)

        Returns:
            包含 open, high, low, close, vol 等字段的 DataFrame
        """
        # 检查缓存
        if self.use_cache:
            params = {"ts_code": ts_code, "start": start_date, "end": end_date, "adj": adj}
            cached = self.cache.get("daily_ak", params, start_date, end_date)
            if cached is not None:
                logger.debug(f"AKShare 缓存命中：{ts_code}")
                return cached

        try:
            # 转换股票代码格式
            symbol = self._convert_ts_code(ts_code)
            
            # 转换日期格式
            start_str = self._format_date(start_date)
            end_str = self._format_date(end_date)
            
            # 获取数据 - 使用 AKShare 的 stock_zh_a_hist 接口
            df = self.ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_str.replace('-', ''),
                end_date=end_str.replace('-', ''),
                adjust=adj
            )
            
            # 数据格式转换
            df = self._process_daily(df, ts_code)
            
            # 保存到缓存
            if self.use_cache and df is not None and not df.empty:
                params = {"ts_code": ts_code, "start": start_date, "end": end_date, "adj": adj}
                self.cache.set("daily_ak", params, df)
            
            return df
            
        except Exception as e:
            logger.error(f"AKShare 获取日线数据失败 {ts_code}: {e}")
            return pd.DataFrame()

    def _format_date(self, date_str: str) -> str:
        """
        格式化日期
        
        Args:
            date_str: YYYYMMDD 格式
            
        Returns:
            YYYY-MM-DD 格式
        """
        if len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        return date_str

    def _process_daily(self, df: pd.DataFrame, ts_code: str) -> pd.DataFrame:
        """
        处理数据格式
        
        AKShare 返回的列名：
        日期，开盘，最高，最低，收盘，成交量，成交额，振幅，涨跌幅，涨跌额，换手率
        
        转换为标准格式：
        trade_date, open, high, low, close, vol, amount, pct_chg, change
        """
        if df is None or df.empty:
            return df
        
        # 列名映射
        column_map = {
            '日期': 'trade_date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'vol',
            '成交额': 'amount',
            '涨跌幅': 'pct_chg',
            '涨跌额': 'change',
            '振幅': 'amplitude',
            '换手率': 'turnover'
        }
        
        # 重命名列
        df = df.rename(columns=column_map)
        
        # 添加 ts_code
        df['ts_code'] = ts_code
        
        # 转换日期格式
        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y%m%d')
        
        # 确保数值列类型正确
        numeric_cols = ['open', 'high', 'low', 'close', 'vol', 'amount', 'pct_chg', 'change']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 按日期排序
        df = df.sort_values('trade_date')
        
        # 设置索引
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        df.set_index('trade_date', inplace=True)
        
        return df

    def get_stock_list(self, exchange: str = None) -> pd.DataFrame:
        """
        获取股票列表

        Args:
            exchange: 交易所 SSE/SZSE/BJSE，None 表示全部

        Returns:
            股票列表 DataFrame
        """
        try:
            # 获取 A 股股票列表
            df = self.ak.stock_info_a_code_name()
            
            # 添加交易所信息
            def get_exchange(code):
                if code.startswith('6'):
                    return 'SSE'
                elif code.startswith('0') or code.startswith('3'):
                    return 'SZSE'
                elif code.startswith('4') or code.startswith('8'):
                    return 'BJSE'
                return 'UNKNOWN'
            
            df['exchange'] = df['code'].apply(get_exchange)
            df['ts_code'] = df['code'] + '.' + df['exchange'].map({
                'SSE': 'SH',
                'SZSE': 'SZ',
                'BJSE': 'BJ'
            })
            
            # 过滤交易所
            if exchange:
                df = df[df['exchange'] == exchange]
            
            return df[['ts_code', 'name', 'exchange', 'code']]
            
        except Exception as e:
            logger.error(f"AKShare 获取股票列表失败：{e}")
            return pd.DataFrame()

    def get_index_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取指数日线数据

        Args:
            ts_code: 指数代码，如 000001.SH
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            指数数据 DataFrame
        """
        try:
            # 转换指数代码
            symbol = self._convert_ts_code(ts_code)
            
            # 获取指数数据
            df = self.ak.stock_zh_index_daily(symbol=symbol)
            
            # 日期过滤
            start_dt = pd.to_datetime(start_date, format='%Y%m%d')
            end_dt = pd.to_datetime(end_date, format='%Y%m%d')
            df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]
            
            # 格式转换
            df = df.rename(columns={
                'date': 'trade_date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close'
            })
            
            df['ts_code'] = ts_code
            df.set_index('trade_date', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"AKShare 获取指数数据失败 {ts_code}: {e}")
            return pd.DataFrame()

    def get_concept_list(self) -> pd.DataFrame:
        """
        获取概念板块列表

        Returns:
            概念板块列表 DataFrame
        """
        try:
            # 获取东方财富概念板块
            df = self.ak.stock_board_concept_name_em()
            
            if df is not None and not df.empty:
                df = df.rename(columns={
                    '板块名称': 'name',
                    '板块代码': 'ts_code'
                })
            
            return df
            
        except Exception as e:
            logger.error(f"AKShare 获取概念列表失败：{e}")
            return pd.DataFrame()

    def get_concept_stocks(self, concept_name: str = None) -> pd.DataFrame:
        """
        获取某概念包含的股票

        Args:
            concept_name: 概念名称

        Returns:
            概念内股票列表 DataFrame
        """
        try:
            if concept_name:
                # 获取东方财富概念成分股
                df = self.ak.stock_board_concept_cons_em(symbol=concept_name)
                
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        '代码': 'ts_code',
                        '名称': 'name'
                    })
                    # 添加交易所后缀
                    df['ts_code'] = df['ts_code'].apply(
                        lambda x: f"{x}.SZ" if x.startswith(('0', '3')) else f"{x}.SH"
                    )
                
                return df[['ts_code', 'name']]
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"AKShare 获取概念成分股失败：{e}")
            return pd.DataFrame()

    def get_industry_list(self) -> pd.DataFrame:
        """
        获取行业板块列表

        Returns:
            行业板块列表 DataFrame
        """
        try:
            # 获取申万行业
            df = self.ak.stock_board_industry_name_em()
            
            if df is not None and not df.empty:
                df = df.rename(columns={
                    '板块名称': 'name',
                    '板块代码': 'ts_code'
                })
            
            return df
            
        except Exception as e:
            logger.error(f"AKShare 获取行业列表失败：{e}")
            return pd.DataFrame()

    def get_industry_stocks(self, industry_name: str = None) -> pd.DataFrame:
        """
        获取某行业包含的股票

        Args:
            industry_name: 行业名称

        Returns:
            行业内股票列表 DataFrame
        """
        try:
            if industry_name:
                # 获取东方财富行业成分股
                df = self.ak.stock_board_industry_cons_em(symbol=industry_name)
                
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        '代码': 'ts_code',
                        '名称': 'name'
                    })
                    # 添加交易所后缀
                    df['ts_code'] = df['ts_code'].apply(
                        lambda x: f"{x}.SZ" if x.startswith(('0', '3')) else f"{x}.SH"
                    )
                
                return df[['ts_code', 'name']]
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"AKShare 获取行业成分股失败：{e}")
            return pd.DataFrame()

    def get_area_list(self) -> pd.DataFrame:
        """
        获取地区列表

        Returns:
            地区列表 DataFrame
        """
        try:
            # 获取股票列表并提取地区
            stock_df = self.get_stock_list()
            
            if stock_df is not None and not stock_df.empty:
                # 获取地区信息（需要额外接口）
                areas = stock_df['name'].drop_duplicates().sort_values()
                return pd.DataFrame({"area": areas})
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"AKShare 获取地区列表失败：{e}")
            return pd.DataFrame()

    def get_area_stocks(self, area: str) -> pd.DataFrame:
        """
        获取某地区的股票

        Args:
            area: 地区名称

        Returns:
            地区内股票列表 DataFrame
        """
        try:
            # 获取股票列表
            stock_df = self.get_stock_list()
            
            # 这里需要额外的接口获取地区信息
            # 暂时返回空 DataFrame
            logger.warning("AKShare 地区股票数据暂不支持")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"AKShare 获取地区股票失败：{e}")
            return pd.DataFrame()

    def get_adj_factor(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取复权因子

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            复权因子 DataFrame
        """
        # AKShare 的 stock_zh_a_hist 接口已经直接支持复权参数
        # 这里返回空 DataFrame，由 get_daily_data 直接处理复权
        return pd.DataFrame()

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
        from tqdm import tqdm
        
        result = {}
        for ts_code in tqdm(ts_codes, desc="AKShare 获取股票数据"):
            df = self.get_daily_data(ts_code, start_date, end_date, adj)
            if not df.empty:
                result[ts_code] = df
        return result
