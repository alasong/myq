"""
板块数据模块
支持行业板块、概念板块、地区板块等
"""
import pandas as pd
from typing import Optional, List, Dict
from loguru import logger

import tushare as ts


class SectorDataProvider:
    """板块数据提供者"""
    
    def __init__(self, token: str = None):
        """
        初始化板块数据提供者
        
        Args:
            token: Tushare API token
        """
        self.token = token
        if token:
            ts.set_token(token)
            self.pro = ts.pro_api()
        else:
            self.pro = None
        
        # 本地缓存
        self._industry_cache: Optional[pd.DataFrame] = None
        self._concept_cache: Optional[pd.DataFrame] = None
        self._stock_industry_cache: Dict[str, pd.DataFrame] = {}
    
    def get_industry_list(self) -> Optional[pd.DataFrame]:
        """
        获取行业板块列表
        
        Returns:
            行业板块列表 DataFrame
        """
        if self._industry_cache is not None:
            return self._industry_cache
        
        if not self.pro:
            logger.warning("未配置 Tushare token，无法获取行业数据")
            return pd.DataFrame()
        
        try:
            # 获取申万行业分类
            df = self.pro.index_classify(
                level="L1",
                src="SW2021",
                fields="ts_code,name,parent_code,level,src"
            )
            self._industry_cache = df
            return df
        except Exception as e:
            logger.error(f"获取行业列表失败：{e}")
            return pd.DataFrame()
    
    def get_concept_list(self) -> Optional[pd.DataFrame]:
        """
        获取概念板块列表
        
        Returns:
            概念板块列表 DataFrame
        """
        if self._concept_cache is not None:
            return self._concept_cache
        
        if not self.pro:
            logger.warning("未配置 Tushare token，无法获取概念数据")
            return pd.DataFrame()
        
        try:
            # 获取概念板块
            df = self.pro.concept(
                fields="ts_code,name,src"
            )
            self._concept_cache = df
            return df
        except Exception as e:
            logger.error(f"获取概念列表失败：{e}")
            return pd.DataFrame()
    
    def get_industry_stocks(self, industry_code: str = None, 
                           industry_name: str = None) -> Optional[pd.DataFrame]:
        """
        获取某行业包含的股票
        
        Args:
            industry_code: 行业代码
            industry_name: 行业名称
            
        Returns:
            行业内股票列表 DataFrame
        """
        if not self.pro:
            logger.warning("未配置 Tushare token")
            return pd.DataFrame()
        
        try:
            # 先获取行业成分
            if industry_code:
                df = self.pro.index_member(
                    ts_code=industry_code,
                    fields="ts_code,name,weight,in_date"
                )
                return df
            elif industry_name:
                # 根据名称查找行业代码
                industries = self.get_industry_list()
                if industries is not None and not industries.empty:
                    match = industries[industries["name"] == industry_name]
                    if not match.empty:
                        industry_code = match.iloc[0]["ts_code"]
                        return self.get_industry_stocks(industry_code=industry_code)
            
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"获取行业成分股失败：{e}")
            return pd.DataFrame()
    
    def get_concept_stocks(self, concept_code: str = None,
                          concept_name: str = None) -> Optional[pd.DataFrame]:
        """
        获取某概念包含的股票
        
        Args:
            concept_code: 概念代码
            concept_name: 概念名称
            
        Returns:
            概念内股票列表 DataFrame
        """
        if not self.pro:
            logger.warning("未配置 Tushare token")
            return pd.DataFrame()
        
        try:
            if concept_code:
                df = self.pro.concept_detail(
                    ts_code=concept_code,
                    fields="ts_code,name,weight,in_date"
                )
                return df
            elif concept_name:
                # 根据名称查找概念代码
                concepts = self.get_concept_list()
                if concepts is not None and not concepts.empty:
                    match = concepts[concepts["name"] == concept_name]
                    if not match.empty:
                        concept_code = match.iloc[0]["ts_code"]
                        return self.get_concept_stocks(concept_code=concept_code)
            
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"获取概念成分股失败：{e}")
            return pd.DataFrame()
    
    def get_stock_industry(self, ts_code: str) -> Optional[pd.DataFrame]:
        """
        获取股票所属行业
        
        Args:
            ts_code: 股票代码
            
        Returns:
            股票行业信息 DataFrame
        """
        if not self.pro:
            logger.warning("未配置 Tushare token")
            return pd.DataFrame()
        
        try:
            # 获取股票基本信息（包含行业）
            df = self.pro.stock_basic(
                ts_code=ts_code,
                fields="ts_code,name,area,industry,market,list_date"
            )
            return df
        except Exception as e:
            logger.error(f"获取股票行业失败：{e}")
            return pd.DataFrame()
    
    def get_stock_concepts(self, ts_code: str) -> Optional[pd.DataFrame]:
        """
        获取股票所属概念
        
        Args:
            ts_code: 股票代码
            
        Returns:
            股票概念信息 DataFrame
        """
        if not self.pro:
            logger.warning("未配置 Tushare token")
            return pd.DataFrame()
        
        try:
            # 获取股票所属概念
            df = self.pro.stock_concept(
                ts_code=ts_code,
                fields="ts_code,concept_code,concept_name,in_date"
            )
            return df
        except Exception as e:
            logger.error(f"获取股票概念失败：{e}")
            return pd.DataFrame()
    
    def get_area_list(self) -> Optional[pd.DataFrame]:
        """
        获取地区列表
        
        Returns:
            地区列表 DataFrame
        """
        if not self.pro:
            return pd.DataFrame()
        
        try:
            df = self.pro.stock_basic(
                fields="ts_code,name,area"
            )
            if df is not None and not df.empty:
                areas = df["area"].drop_duplicates().sort_values()
                return pd.DataFrame({"area": areas})
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"获取地区列表失败：{e}")
            return pd.DataFrame()
    
    def get_area_stocks(self, area: str) -> Optional[pd.DataFrame]:
        """
        获取某地区的股票
        
        Args:
            area: 地区名称
            
        Returns:
            地区内股票列表 DataFrame
        """
        if not self.pro:
            return pd.DataFrame()
        
        try:
            df = self.pro.stock_basic(
                fields="ts_code,name,area,industry"
            )
            if df is not None and not df.empty:
                return df[df["area"] == area]
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"获取地区股票失败：{e}")
            return pd.DataFrame()
    
    def search_stocks_by_sector(self, sector_type: str, 
                                sector_name: str) -> Optional[List[str]]:
        """
        根据板块类型和名称搜索股票
        
        Args:
            sector_type: 板块类型 (industry/concept/area)
            sector_name: 板块名称
            
        Returns:
            股票代码列表
        """
        if sector_type == "industry":
            df = self.get_industry_stocks(industry_name=sector_name)
        elif sector_type == "concept":
            df = self.get_concept_stocks(concept_name=sector_name)
        elif sector_type == "area":
            df = self.get_area_stocks(area=sector_name)
        else:
            logger.error(f"未知的板块类型：{sector_type}")
            return None
        
        if df is not None and not df.empty:
            return df["ts_code"].tolist()
        return []
    
    def get_stock_sector_map(self, ts_codes: List[str]) -> Dict[str, Dict]:
        """
        批量获取股票的板块映射关系
        
        Args:
            ts_codes: 股票代码列表
            
        Returns:
            {ts_code: {"industry": ..., "concepts": [...], "area": ...}}
        """
        result = {}
        
        for ts_code in ts_codes:
            try:
                # 获取行业
                industry_df = self.get_stock_industry(ts_code)
                industry = industry_df.iloc[0]["industry"] if industry_df is not None and not industry_df.empty else None
                
                # 获取地区
                area = industry_df.iloc[0]["area"] if industry_df is not None and not industry_df.empty else None
                
                # 获取概念
                concepts_df = self.get_stock_concepts(ts_code)
                concepts = concepts_df["concept_name"].tolist() if concepts_df is not None and not concepts_df.empty else []
                
                result[ts_code] = {
                    "industry": industry,
                    "area": area,
                    "concepts": concepts
                }
            except Exception as e:
                logger.debug(f"获取股票板块信息失败 {ts_code}: {e}")
                result[ts_code] = {"industry": None, "area": None, "concepts": []}
        
        return result
