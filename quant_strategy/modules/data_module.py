"""
数据查看模块

支持：
- 查看股票列表
- 查看股票详情
- 查看板块数据
- 查看缓存状态
"""
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime

from .base import BaseModule, ModuleInfo, ModuleType, ModuleResult, register_module


@register_module("data")
class DataModule(BaseModule):
    """数据查看模块"""
    
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="data",
            module_type=ModuleType.DATA,
            description="数据查看与管理",
            tags=["数据", "股票", "板块", "缓存"]
        )
    
    def get_actions(self) -> List[str]:
        return [
            "list-stocks",      # 列出股票
            "stock-info",       # 股票详情
            "list-sectors",     # 列出板块
            "sector-stocks",    # 板块成分
            "cache-status",     # 缓存状态
            "cache-stats",      # 缓存统计
        ]
    
    def execute(self, action: str, **kwargs) -> ModuleResult:
        """执行模块操作"""
        self._record_call(True)
        
        actions = {
            'list-stocks': self.list_stocks,
            'stock-info': self.stock_info,
            'list-sectors': self.list_sectors,
            'sector-stocks': self.sector_stocks,
            'cache-status': self.cache_status,
            'cache-stats': self.cache_stats,
        }
        
        if action not in actions:
            return ModuleResult(
                success=False,
                message=f"未知操作：{action}",
                error=f"支持的操作：{list(actions.keys())}"
            )
        
        try:
            return actions[action](**kwargs)
        except Exception as e:
            self._record_call(False)
            return ModuleResult(
                success=False,
                message=f"执行失败：{str(e)}",
                error=str(e)
            )
    
    def list_stocks(self, limit: int = 20, **kwargs) -> ModuleResult:
        """列出股票"""
        provider = self.ctx.get('provider')
        if not provider:
            return ModuleResult(
                success=False,
                message="数据源未初始化"
            )
        
        try:
            # 获取全部股票
            df = provider.pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,market,list_date')
            
            if df is not None and not df.empty:
                total = len(df)
                df = df.head(limit)
                
                return ModuleResult(
                    success=True,
                    message=f"共 {total} 只股票，显示前 {limit} 只",
                    data=df.to_dict('records'),
                    metadata={'total': total, 'showing': len(df)}
                )
            else:
                return ModuleResult(
                    success=False,
                    message="未获取到股票列表"
                )
                
        except Exception as e:
            return ModuleResult(
                success=False,
                message=f"获取股票列表失败：{str(e)}",
                error=str(e)
            )
    
    def stock_info(self, ts_code: str = None, **kwargs) -> ModuleResult:
        """查看股票详情"""
        if not ts_code:
            return ModuleResult(
                success=False,
                message="请指定股票代码，例如：stock-info ts_code=000001.SZ"
            )
        
        provider = self.ctx.get('provider')
        if not provider:
            return ModuleResult(success=False, message="数据源未初始化")
        
        try:
            # 获取基本信息
            df = provider.pro.stock_basic(ts_code=ts_code)
            
            if df is not None and not df.empty:
                info = df.iloc[0].to_dict()
                
                # 获取最新行情
                try:
                    today = datetime.now().strftime('%Y%m%d')
                    df_daily = provider.pro.daily(ts_code=ts_code, start_date=today, end_date=today)
                    if df_daily is not None and not df_daily.empty:
                        info['latest'] = df_daily.iloc[0].to_dict()
                except:
                    pass
                
                return ModuleResult(
                    success=True,
                    message=f"{info.get('name', ts_code)} ({ts_code})",
                    data=info
                )
            else:
                return ModuleResult(
                    success=False,
                    message=f"未找到股票：{ts_code}"
                )
                
        except Exception as e:
            return ModuleResult(
                success=False,
                message=f"获取股票信息失败：{str(e)}",
                error=str(e)
            )
    
    def list_sectors(self, sector_type: str = "industry", **kwargs) -> ModuleResult:
        """列出板块"""
        provider = self.ctx.get('provider')
        if not provider:
            return ModuleResult(success=False, message="数据源未初始化")
        
        try:
            if sector_type == "industry":
                df = provider.pro.index_classify(src='SW')
            elif sector_type == "concept":
                df = provider.pro.concept(src='ts')
            else:
                return ModuleResult(
                    success=False,
                    message=f"未知板块类型：{sector_type}"
                )
            
            if df is not None and not df.empty:
                sectors = df['name'].unique().tolist() if 'name' in df.columns else []
                return ModuleResult(
                    success=True,
                    message=f"共 {len(sectors)} 个{sector_type}板块",
                    data={'sectors': sectors, 'count': len(sectors)}
                )
            else:
                return ModuleResult(
                    success=False,
                    message="未获取到板块列表"
                )
                
        except Exception as e:
            return ModuleResult(
                success=False,
                message=f"获取板块列表失败：{str(e)}",
                error=str(e)
            )
    
    def sector_stocks(self, sector_name: str = None, **kwargs) -> ModuleResult:
        """查看板块成分"""
        if not sector_name:
            return ModuleResult(
                success=False,
                message="请指定板块名称，例如：sector-stocks sector_name=银行"
            )
        
        provider = self.ctx.get('provider')
        if not provider:
            return ModuleResult(success=False, message="数据源未初始化")
        
        try:
            # 获取板块成分
            df = provider.pro.index_member(src='SW', index_name=sector_name)
            
            if df is not None and not df.empty:
                stocks = df.to_dict('records')
                return ModuleResult(
                    success=True,
                    message=f"{sector_name} 板块包含 {len(stocks)} 只股票",
                    data=stocks,
                    metadata={'sector': sector_name, 'count': len(stocks)}
                )
            else:
                return ModuleResult(
                    success=False,
                    message=f"未找到板块：{sector_name}"
                )
                
        except Exception as e:
            return ModuleResult(
                success=False,
                message=f"获取板块成分失败：{str(e)}",
                error=str(e)
            )
    
    def cache_status(self, **kwargs) -> ModuleResult:
        """查看缓存状态"""
        cache = self.ctx.get('cache')
        if not cache:
            return ModuleResult(success=False, message="缓存未初始化")
        
        try:
            stats = cache.get_cache_report()
            
            message = (
                f"缓存状态:\n"
                f"  总文件数：  {stats['total_files']:,}\n"
                f"  缓存大小：  {stats['total_size_mb']:.2f} MB\n"
                f"  股票数量：  {stats['stock_count']:,}\n"
                f"  完整数据：  {stats['complete_count']:,}\n"
                f"  不完整：    {stats['incomplete_count']:,}"
            )
            
            if stats.get('by_type'):
                message += "\n\n数据类型:"
                for dtype, count in stats['by_type'].items():
                    message += f"\n  {dtype}: {count:,}"
            
            return ModuleResult(
                success=True,
                message=message,
                data=stats
            )
            
        except Exception as e:
            return ModuleResult(
                success=False,
                message=f"获取缓存状态失败：{str(e)}",
                error=str(e)
            )
    
    def cache_stats(self, **kwargs) -> ModuleResult:
        """查看缓存统计"""
        cache = self.ctx.get('cache')
        if not cache:
            return ModuleResult(success=False, message="缓存未初始化")
        
        try:
            stats = cache.get_stats()
            return ModuleResult(
                success=True,
                message="缓存统计",
                data=stats
            )
        except Exception as e:
            return ModuleResult(
                success=False,
                message=f"获取缓存统计失败：{str(e)}",
                error=str(e)
            )
    
    def get_help(self, action: str = None) -> str:
        """获取帮助信息"""
        help_text = {
            'list-stocks': "列出股票列表\n  参数：limit - 显示数量 (默认 20)",
            'stock-info': "查看股票详情\n  参数：ts_code - 股票代码 (必需)",
            'list-sectors': "列出板块\n  参数：sector_type - 板块类型 (industry/concept)",
            'sector-stocks': "查看板块成分\n  参数：sector_name - 板块名称 (必需)",
            'cache-status': "查看缓存状态",
            'cache-stats': "查看缓存详细统计",
        }
        
        if action:
            return help_text.get(action, f"未知操作：{action}")
        
        return "数据查看模块 - 支持股票、板块、缓存查询\n" + "\n".join(
            f"  {k}: {v.split(chr(10))[0]}" for k, v in help_text.items()
        )
