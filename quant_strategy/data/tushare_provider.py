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
    
    def __init__(self, token: str = None, use_cache: bool = True,
                 cache_dir: str = "./data_cache", compression: str = "gzip"):
        """
        初始化数据提供者

        Args:
            token: Tushare API token，如为 None 则从环境变量读取
            use_cache: 是否启用本地缓存
            cache_dir: 缓存目录
            compression: 缓存压缩方式 (none/snappy/gzip/brotli/zstd)
        """
        self.token = token or os.getenv("TUSHARE_TOKEN")
        if not self.token:
            raise ValueError("请提供 Tushare token 或设置 TUSHARE_TOKEN 环境变量")

        ts.set_token(self.token)
        self.pro = ts.pro_api()
        self.use_cache = use_cache
        
        # 初始化缓存（支持压缩）
        self.cache = DataCache(
            cache_dir=cache_dir,
            compression=compression  # 使用压缩
        ) if use_cache else None

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
        获取股票日线数据（历史数据本地持久化，只实时获取新数据）

        策略：
        1. 优先从本地缓存读取历史数据
        2. 检测是否有新数据需要获取（最新交易日到 end_date）
        3. 只实时获取新数据，然后与历史数据合并
        4. 所有获取的数据都保存到本地

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

        # 1. 尝试从缓存获取全部数据
        if self.use_cache:
            cached = self.cache.get("daily", cache_key_params, start_date, end_date)
            if cached is not None and not cached.empty:
                logger.debug(f"缓存命中：{ts_code}")
                return cached

        # 2. 缓存未命中，尝试获取该股票的所有历史数据（全量持久化）
        df = self._get_full_history(ts_code, start_date, end_date, adj)

        if df is not None and not df.empty:
            return df

        # 3. 全量获取失败，降级为直接获取请求范围的数据
        logger.warning(f"{ts_code}: 全量获取失败，降级为直接获取 {start_date}-{end_date}")
        return self._fetch_daily_range(ts_code, start_date, end_date, adj, cache_key_params)

    def _get_full_history(self, ts_code: str, start_date: str, end_date: str, adj: str) -> pd.DataFrame:
        """
        获取股票全部历史数据（持久化策略）

        逻辑：
        1. 从缓存加载已有的历史数据
        2. 检查是否有新数据（从最后交易日到 end_date）
        3. 只获取新数据，与历史数据合并
        4. 保存到缓存

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            adj: 复权类型

        Returns:
            合并后的数据
        """
        # 使用全量缓存键（不按日期范围）
        full_cache_params = {"ts_code": ts_code, "adj": adj}

        try:
            # 1. 尝试从缓存获取该股票的全部历史数据
            historical_df = self.cache.get("daily_full", full_cache_params)

            if historical_df is not None and not historical_df.empty:
                # 2. 检查是否有新数据
                # 确保索引是 datetime 类型
                if not pd.api.types.is_datetime64_any_dtype(historical_df.index):
                    # 使用混合模式推断日期格式
                    try:
                        historical_df.index = pd.to_datetime(historical_df.index, format='mixed')
                    except Exception as idx_err:
                        logger.warning(f"{ts_code}: 索引转换失败：{idx_err}，尝试重新获取数据")
                        # 索引无法转换，删除旧缓存重新获取
                        return self._fetch_all_history(ts_code, start_date, end_date, adj, full_cache_params)
                
                last_date = historical_df.index.max().strftime('%Y%m%d')
                need_update = last_date < end_date

                if not need_update:
                    # 无需更新，直接返回请求范围的数据
                    logger.debug(f"{ts_code}: 使用缓存历史数据（{len(historical_df)}天）")
                    mask = (historical_df.index >= pd.to_datetime(start_date, format='%Y%m%d')) & \
                           (historical_df.index <= pd.to_datetime(end_date, format='%Y%m%d'))
                    return historical_df[mask]

                # 3. 获取新数据（从最后交易日+1 到 end_date）
                new_start = (pd.to_datetime(last_date, format='%Y%m%d') + pd.Timedelta(days=1)).strftime('%Y%m%d')
                logger.info(f"{ts_code}: 获取新数据 {new_start}-{end_date}")

                new_df = self._fetch_daily_range(ts_code, new_start, end_date, adj,
                                                 {"ts_code": ts_code, "start": new_start, "end": end_date, "adj": adj})

                if new_df is not None and not new_df.empty:
                    # 4. 合并历史数据和新数据
                    combined_df = pd.concat([historical_df, new_df])
                    combined_df = combined_df[~combined_df.index.duplicated(keep='first')]
                    combined_df = combined_df.sort_index()

                    # 5. 保存全量数据到缓存
                    self.cache.set("daily_full", full_cache_params, combined_df, is_complete=True)
                    logger.info(f"{ts_code}: 已更新历史数据（{len(combined_df)}天）")

                    # 返回请求范围的数据
                    mask = (combined_df.index >= pd.to_datetime(start_date, format='%Y%m%d')) & \
                           (combined_df.index <= pd.to_datetime(end_date, format='%Y%m%d'))
                    return combined_df[mask]

                return historical_df

            else:
                # 无缓存，直接获取请求范围的数据（不是全部历史数据）
                logger.info(f"{ts_code}: 获取请求范围数据 {start_date}-{end_date}")
                
                # 创建当前请求的缓存参数
                request_cache_params = {"ts_code": ts_code, "start": start_date, "end": end_date, "adj": adj}
                df = self._fetch_daily_range(ts_code, start_date, end_date, adj, request_cache_params)

                # 同时保存到 daily_full 缓存（标记为完整）
                if df is not None and not df.empty:
                    self.cache.set("daily_full", full_cache_params, df, is_complete=True)
                    logger.info(f"{ts_code}: 已保存缓存（{len(df)}天）")

                return df

        except Exception as e:
            # P1-2: 增强错误处理，区分错误类型
            error_msg = str(e)
            if "积分" in error_msg or "积分不足" in error_msg:
                logger.error(f"{ts_code}: 积分不足，需要升级 Tushare 会员")
            elif "limit" in error_msg.lower() or "限流" in error_msg:
                logger.error(f"{ts_code}: API 调用次数超限，请稍后重试")
            elif "权限" in error_msg or "vip" in error_msg.lower():
                logger.error(f"{ts_code}: 权限不足，需要升级 Tushare 会员级别")
            else:
                logger.error(f"{ts_code}: 获取历史数据失败：{e}")
            return None

    def _fetch_all_history(self, ts_code: str, start_date: str, end_date: str,
                           adj: str, cache_params: dict) -> pd.DataFrame:
        """
        首次获取股票全部历史数据（从上市日期到 end_date）

        Args:
            ts_code: 股票代码
            start_date: 开始日期（请求的，不影响获取范围）
            end_date: 结束日期
            adj: 复权类型
            cache_params: 缓存参数

        Returns:
            历史数据 DataFrame
        """
        try:
            # 1. 获取股票基本信息（包含上市日期）
            list_date = start_date  # 默认使用请求的开始日期
            try:
                stock_info = self.pro.stock_basic(ts_code=ts_code, fields="ts_code,list_date")
                if stock_info is not None and not stock_info.empty:
                    list_date_val = stock_info['list_date'].iloc[0]
                    logger.debug(f"{ts_code}: 原始上市日期值 = {list_date_val}, 类型 = {type(list_date_val).__name__}")
                    
                    # 转换上市日期格式 YYYYMMDD
                    if pd.notna(list_date_val):
                        # 处理 int 或 string 类型
                        if isinstance(list_date_val, (int, float)):
                            list_date = str(int(list_date_val))
                            logger.debug(f"{ts_code}: int/float 转换后 = {list_date}")
                        else:
                            list_date = str(list_date_val)
                            logger.debug(f"{ts_code}: string 转换后 = {list_date}")

                        # 确保是 8 位数字格式
                        if len(list_date) == 8 and list_date.isdigit():
                            pass  # 已经是 YYYYMMDD 格式
                        elif len(list_date) == 10 and '-' in list_date:
                            # YYYY-MM-DD 格式转换为 YYYYMMDD
                            list_date = list_date.replace('-', '')
                        else:
                            # 其他格式，尝试解析
                            try:
                                list_date = pd.to_datetime(list_date).strftime('%Y%m%d')
                            except Exception as parse_err:
                                logger.debug(f"{ts_code}: 日期解析失败：{parse_err}，使用默认值")
                                list_date = start_date  # 解析失败，使用默认值
                    else:
                        list_date = start_date  # 无法获取上市日期，使用请求的开始日期
                else:
                    list_date = start_date  # 无法获取股票信息，使用请求的开始日期
            except Exception as e:
                logger.debug(f"{ts_code}: 获取上市日期失败：{e}，使用请求的开始日期")
                list_date = start_date

            # 2. 从上市日期开始获取全部历史数据
            logger.info(f"{ts_code}: 从上市日期 ({list_date}) 获取全部历史数据")

            if adj:
                adj_factor = self.get_adj_factor(ts_code, list_date, end_date)
                df = self.pro.daily(
                    ts_code=ts_code,
                    start_date=list_date,
                    end_date=end_date
                )
                df = self._apply_adj_factor(df, adj_factor, adj)
            else:
                df = self.pro.daily(
                    ts_code=ts_code,
                    start_date=list_date,
                    end_date=end_date
                )

            # 3. 处理数据
            df = self._process_daily(df, ts_code)

            if df is not None and not df.empty:
                # 4. 保存全量数据到缓存
                self.cache.set("daily_full", {"ts_code": ts_code, "adj": adj}, df, is_complete=True)
                logger.info(f"{ts_code}: 已保存历史数据（{len(df)}天，从{list_date}到{end_date}）")

            return df

        except Exception as e:
            # P1-2: 增强错误处理，区分错误类型
            error_msg = str(e)
            if "积分" in error_msg or "积分不足" in error_msg:
                logger.error(f"{ts_code}: 积分不足，需要升级 Tushare 会员")
            elif "limit" in error_msg.lower() or "限流" in error_msg:
                logger.error(f"{ts_code}: API 调用次数超限，请稍后重试")
            elif "权限" in error_msg or "vip" in error_msg.lower():
                logger.error(f"{ts_code}: 权限不足，需要升级 Tushare 会员级别")
            elif "网络" in error_msg or "timeout" in error_msg.lower():
                logger.error(f"{ts_code}: 网络错误，请检查网络连接")
            else:
                logger.error(f"{ts_code}: 获取历史数据失败：{e}")
            return pd.DataFrame()

    def _fetch_daily_range(self, ts_code: str, start_date: str, end_date: str,
                           adj: str, cache_params: dict) -> pd.DataFrame:
        """
        获取指定日期范围的日线数据

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            adj: 复权类型
            cache_params: 缓存参数

        Returns:
            日线数据 DataFrame
        """
        try:
            if adj:
                adj_factor = self.get_adj_factor(ts_code, start_date, end_date)
                df = self.pro.daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
                df = self._apply_adj_factor(df, adj_factor, adj)
            else:
                df = self.pro.daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )

            # 处理数据（包含重复数据清理）
            df = self._process_daily(df, ts_code)

            if df is not None and not df.empty:
                # 保存到缓存（按日期范围）
                self.cache.set("daily", cache_params, df, is_complete=True)
                logger.info(f"{ts_code}: 获取数据（{len(df)}天）")

            return df

        except Exception as e:
            # P1-2: 增强错误处理，区分错误类型
            error_msg = str(e)
            if "积分" in error_msg or "积分不足" in error_msg:
                logger.error(f"{ts_code}: 积分不足，需要升级 Tushare 会员")
            elif "limit" in error_msg.lower() or "限流" in error_msg:
                logger.error(f"{ts_code}: API 调用次数超限，请稍后重试")
            elif "权限" in error_msg or "vip" in error_msg.lower():
                logger.error(f"{ts_code}: 权限不足，需要升级 Tushare 会员级别")
            elif "网络" in error_msg or "timeout" in error_msg.lower():
                logger.error(f"{ts_code}: 网络错误，请检查网络连接")
            else:
                logger.error(f"{ts_code}: 获取日线数据失败：{e}")
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

    def _validate_data(self, df: pd.DataFrame, ts_code: str, start_date: str, end_date: str) -> dict:
        """
        P2-1: 验证数据完整性
        
        Args:
            df: 要验证的数据
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            验证结果字典
        """
        result = {
            "is_valid": True,
            "missing_dates": [],
            "zero_prices": False,
            "issues": []
        }
        
        if df.empty:
            result["is_valid"] = False
            result["issues"].append("数据为空")
            return result
        
        # 1. 检查日期连续性
        expected_dates = self._get_trade_dates(start_date, end_date)
        actual_dates = [d.strftime('%Y%m%d') for d in df.index]
        
        missing_dates = set(expected_dates) - set(actual_dates)
        if missing_dates:
            result["missing_dates"] = list(missing_dates)
            result["issues"].append(f"缺失 {len(missing_dates)} 个交易日")
            result["is_valid"] = False
            logger.warning(f"{ts_code}: 缺失 {len(missing_dates)} 个交易日")
        
        # 2. 检查数据质量（零价格）
        if 'close' in df.columns and (df['close'] == 0).any():
            result["zero_prices"] = True
            result["issues"].append("存在零价格")
            logger.warning(f"{ts_code}: 存在零价格")
        
        # 3. 检查 NaN 值
        nan_count = df.isna().sum().sum()
        if nan_count > 0:
            result["issues"].append(f"存在 {nan_count} 个 NaN 值")
            logger.warning(f"{ts_code}: 存在 {nan_count} 个 NaN 值")
        
        return result

    def _get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """
        P2-1: 获取指定日期范围内的交易日列表
        
        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            
        Returns:
            交易日列表
        """
        try:
            # 获取交易所（默认 SSE）
            trade_cal = self.get_trade_cal(exchange="SSE", start_date=start_date, end_date=end_date)
            if trade_cal is not None and not trade_cal.empty:
                return trade_cal["cal_date"].tolist()
        except Exception as e:
            logger.debug(f"获取交易日历失败：{e}")
        
        # 无法获取交易日历时，返回空列表
        return []

    def _process_daily(self, df: pd.DataFrame, ts_code: str = None) -> pd.DataFrame:
        """
        处理日线数据格式（包含重复数据清理）
        
        Args:
            df: 原始数据
            ts_code: 股票代码（用于日志）
        
        Returns:
            处理后的数据
        """
        if df.empty:
            return df

        df = df.sort_values("trade_date").reset_index(drop=True)
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
        
        # 检测重复日期
        duplicates = df["trade_date"].duplicated().sum()
        if duplicates > 0:
            logger.warning(f"{ts_code or '未知'}: 检测到 {duplicates} 条重复日期数据，保留第一条")
            df = df.drop_duplicates(subset="trade_date", keep="first")
        
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

    def prefetch_cache(self, ts_codes: List[str], start_date: str, end_date: str, adj: str = "qfq"):
        """
        P2-4: 预加载多只股票的缓存（用于批量回测前预加载）
        
        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            adj: 复权类型
        """
        logger.info(f"预加载缓存：{len(ts_codes)} 只股票，{start_date}-{end_date}")
        
        hit_count = 0
        miss_count = 0
        
        for ts_code in tqdm(ts_codes, desc="预加载缓存"):
            full_params = {"ts_code": ts_code, "adj": adj}
            cached = self.cache.get("daily_full", full_params)
            
            if cached is not None and not cached.empty:
                # 检查缓存是否需要更新
                last_date = cached.index.max().strftime('%Y%m%d') if not cached.empty else None
                if last_date and last_date >= end_date:
                    hit_count += 1
                else:
                    # 缓存需要更新，先加载旧数据
                    miss_count += 1
            else:
                miss_count += 1
        
        logger.info(f"预加载完成：命中 {hit_count}/{len(ts_codes)}，需要更新 {miss_count}/{len(ts_codes)}")

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
