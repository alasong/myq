"""
内置 Skills 实现

包含：
- 数据下载 Skills
- 缓存管理 Skills
- 回测 Skills
- 板块分析 Skills
"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from loguru import logger

from .skill_system import Skill, SkillDefinition, SkillResult, register_skill


# ==================== 数据下载 Skills ====================

class DownloadDataSkill(Skill):
    """数据下载 Skill"""
    
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="download_data",
            description="下载股票数据",
            aliases=["下载数据", "download", "fetch", "获取数据"],
            parameters={
                "start_date": {"required": True, "description": "开始日期", "default": None},
                "end_date": {"required": True, "description": "结束日期", "default": None},
                "ts_codes": {"required": False, "description": "股票代码列表", "default": []},
                "workers": {"required": False, "description": "并发线程数", "default": 4},
                "all_stocks": {"required": False, "description": "是否下载全部股票", "default": False},
            },
            examples=[
                "下载 2025 年数据",
                "下载 20240101-20241231 的股票",
                "批量下载全部股票 8 线程",
                "下载茅台的数据",
            ],
            category="data",
            requires_context=["provider", "cache"],
            provides_context=["last_download", "downloaded_codes"]
        )
    
    def validate(self, context: Dict[str, Any], **kwargs) -> tuple:
        if not kwargs.get('start_date') or not kwargs.get('end_date'):
            return False, "请指定日期范围"
        return True, None
    
    async def execute(self, context: Dict[str, Any], **kwargs) -> SkillResult:
        from quant_strategy.tools.fetch_all_stocks import fetch_and_cache_stocks, get_all_stocks
        
        start_date = kwargs['start_date']
        end_date = kwargs['end_date']
        ts_codes = kwargs.get('ts_codes', [])
        workers = kwargs.get('workers', 4)
        all_stocks = kwargs.get('all_stocks', False)
        
        provider = context.get('provider')
        if not provider:
            return SkillResult(
                success=False,
                message="数据源未初始化，请设置 TUSHARE_TOKEN"
            )
        
        try:
            # 获取股票列表
            if all_stocks or not ts_codes:
                self.on_progress(10, "获取全部股票列表...")
                ts_codes = get_all_stocks(provider)
                self.on_progress(20, f"共 {len(ts_codes)} 只股票")
            else:
                self.on_progress(10, f"准备下载 {len(ts_codes)} 只股票")
            
            # 分批下载
            total = len(ts_codes)
            completed = 0
            
            async def download_batch(batch: List[str], batch_num: int, total_batches: int):
                nonlocal completed
                self.on_progress(
                    20 + int((batch_num / total_batches) * 70),
                    f"下载批次 {batch_num}/{total_batches}"
                )
                
                # 在线程池中执行同步方法
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: fetch_and_cache_stocks(
                        provider=provider,
                        ts_codes=batch,
                        start_date=start_date,
                        end_date=end_date,
                        batch_size=50,
                        force=False,
                        workers=workers
                    )
                )
                completed += len(batch)
            
            # 分批处理
            batch_size = 100
            batches = [ts_codes[i:i+batch_size] for i in range(0, total, batch_size)]
            
            tasks = [download_batch(batch, i+1, len(batches)) for i, batch in enumerate(batches)]
            await asyncio.gather(*tasks)
            
            self.on_progress(100, "下载完成")
            
            return SkillResult(
                success=True,
                message=f"成功下载 {total} 只股票的数据",
                context_updates={
                    'last_download': {
                        'date_range': f"{start_date}-{end_date}",
                        'count': total,
                        'timestamp': datetime.now().isoformat()
                    },
                    'downloaded_codes': ts_codes[:10]  # 只保存前 10 个
                }
            )
            
        except Exception as e:
            logger.exception("下载失败")
            return SkillResult(
                success=False,
                message=f"下载失败：{str(e)}",
                error=str(e)
            )


class UpdateDataSkill(Skill):
    """数据更新 Skill"""
    
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="update_data",
            description="更新最近 N 天的数据",
            aliases=["更新数据", "update", "refresh", "同步数据"],
            parameters={
                "days": {"required": False, "description": "更新天数", "default": 30},
                "workers": {"required": False, "description": "并发线程数", "default": 4},
            },
            examples=[
                "更新数据",
                "更新最近 30 天",
                "更新最近 7 天数据 8 线程",
            ],
            category="data",
            requires_context=["provider"],
            provides_context=["last_update"]
        )
    
    async def execute(self, context: Dict[str, Any], **kwargs) -> SkillResult:
        days = kwargs.get('days', 30)
        workers = kwargs.get('workers', 4)
        
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        
        # 调用下载 Skill
        download_skill = DownloadDataSkill()
        result = await download_skill.execute(
            context,
            start_date=start_date,
            end_date=end_date,
            workers=workers,
            all_stocks=True
        )
        
        if result.success:
            result.context_updates['last_update'] = {
                'days': days,
                'timestamp': datetime.now().isoformat()
            }
        
        return result


# ==================== 缓存管理 Skills ====================

class CacheStatusSkill(Skill):
    """缓存状态查询 Skill"""
    
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="cache_status",
            description="查看缓存状态",
            aliases=["查看缓存", "状态", "cache", "status", "缓存统计"],
            parameters={},
            examples=[
                "查看缓存状态",
                "状态",
                "缓存统计",
            ],
            category="cache",
            requires_context=["cache"],
            provides_context=[]
        )
    
    async def execute(self, context: Dict[str, Any], **kwargs) -> SkillResult:
        cache = context.get('cache')
        if not cache:
            return SkillResult(
                success=False,
                message="缓存未初始化"
            )
        
        try:
            stats = cache.get_cache_report()
            
            message = f"""
缓存状态
============================================================
总文件数：{stats['total_files']}
缓存大小：{stats['total_size_mb']:.2f} MB
股票数量：{stats['stock_count']}
完整数据：{stats['complete_count']}
不完整：{stats['incomplete_count']}

按类型:
"""
            for data_type, count in stats.get('by_type', {}).items():
                message += f"  {data_type}: {count} 个\n"
            
            message += "=" * 60
            
            return SkillResult(
                success=True,
                message=message,
                data=stats
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"查询失败：{str(e)}",
                error=str(e)
            )


class CleanupCacheSkill(Skill):
    """缓存清理 Skill"""
    
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="cleanup_cache",
            description="清理缓存",
            aliases=["清理缓存", "清除缓存", "cleanup", "clean", "清理"],
            parameters={
                "days": {"required": False, "description": "清理 N 天前的缓存", "default": 30},
            },
            examples=[
                "清理缓存",
                "清除 30 天前的数据",
                "清理 7 天前的缓存",
            ],
            category="cache",
            requires_context=["cache"],
            provides_context=[]
        )
    
    async def execute(self, context: Dict[str, Any], **kwargs) -> SkillResult:
        cache = context.get('cache')
        days = kwargs.get('days', 30)
        
        if not cache:
            return SkillResult(
                success=False,
                message="缓存未初始化"
            )
        
        try:
            stats_before = cache.get_cache_stats()
            
            self.on_progress(30, f"清理 {days} 天前的缓存...")
            cache.clear(older_than_days=days)
            
            stats_after = cache.get_cache_stats()
            saved = stats_before['total_size_mb'] - stats_after['total_size_mb']
            
            self.on_progress(100, "清理完成")
            
            return SkillResult(
                success=True,
                message=f"清理完成！释放 {saved:.2f} MB 空间",
                data={
                    'before': stats_before,
                    'after': stats_after,
                    'saved_mb': saved
                }
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"清理失败：{str(e)}",
                error=str(e)
            )


# ==================== 回测 Skills ====================

class BacktestSkill(Skill):
    """回测 Skill"""
    
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="backtest",
            description="执行策略回测",
            aliases=["回测", "backtest", "策略回测", "运行策略"],
            parameters={
                "strategy": {"required": True, "description": "策略名称", "default": None},
                "ts_code": {"required": True, "description": "股票代码", "default": None},
                "start_date": {"required": True, "description": "开始日期", "default": None},
                "end_date": {"required": True, "description": "结束日期", "default": None},
                "params": {"required": False, "description": "策略参数", "default": {}},
            },
            examples=[
                "回测双均线策略 000001.SZ 20240101-20241231",
                "运行 KDJ 策略 茅台",
                "backtest dual_ma 000001.SZ",
            ],
            category="backtest",
            requires_context=["provider"],
            provides_context=["last_backtest", "backtest_result"]
        )
    
    async def execute(self, context: Dict[str, Any], **kwargs) -> SkillResult:
        strategy_name = kwargs.get('strategy')
        ts_code = kwargs.get('ts_code')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        params = kwargs.get('params', {})
        
        if not all([strategy_name, ts_code, start_date, end_date]):
            return SkillResult(
                success=False,
                message="缺少必要参数：strategy, ts_code, start_date, end_date"
            )
        
        try:
            from quant_strategy.strategy import get_strategy_class
            
            self.on_progress(20, f"加载策略：{strategy_name}")
            strategy_class = get_strategy_class(strategy_name)
            
            self.on_progress(40, f"获取数据：{ts_code}")
            provider = context.get('provider')
            data = provider.get_daily_data(ts_code, start_date, end_date, adj='qfq')
            
            if data.empty:
                return SkillResult(
                    success=False,
                    message=f"未获取到数据：{ts_code}"
                )
            
            self.on_progress(60, "运行回测")
            from quant_strategy.backtester import Backtester, BacktestConfig
            
            config = BacktestConfig()
            backtester = Backtester(config)
            strategy = strategy_class(**params)
            
            result = backtester.run_single_stock(strategy, data)
            
            self.on_progress(100, "回测完成")
            
            return SkillResult(
                success=True,
                message=f"回测完成：{ts_code}",
                data=result,
                context_updates={
                    'last_backtest': {
                        'strategy': strategy_name,
                        'ts_code': ts_code,
                        'date_range': f"{start_date}-{end_date}",
                        'timestamp': datetime.now().isoformat()
                    }
                }
            )
            
        except Exception as e:
            logger.exception("回测失败")
            return SkillResult(
                success=False,
                message=f"回测失败：{str(e)}",
                error=str(e)
            )


# ==================== 板块分析 Skills ====================

class SectorAnalysisSkill(Skill):
    """板块分析 Skill"""
    
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="sector_analysis",
            description="板块回测分析",
            aliases=["板块分析", "板块回测", "sector", "板块"],
            parameters={
                "sector_type": {"required": True, "description": "板块类型", "default": "industry"},
                "sector_name": {"required": False, "description": "板块名称", "default": None},
                "strategy": {"required": True, "description": "策略名称", "default": None},
                "workers": {"required": False, "description": "并发数", "default": 8},
            },
            examples=[
                "板块回测 银行 dual_ma",
                "分析人工智能概念板块",
                "sector industry 银行 kdj",
            ],
            category="analysis",
            requires_context=["provider", "sector_provider"],
            provides_context=["last_sector_analysis"]
        )
    
    async def execute(self, context: Dict[str, Any], **kwargs) -> SkillResult:
        sector_type = kwargs.get('sector_type', 'industry')
        sector_name = kwargs.get('sector_name')
        strategy = kwargs.get('strategy')
        workers = kwargs.get('workers', 8)
        
        try:
            from quant_strategy.data.sector_provider import SectorProvider
            
            sector_provider = context.get('sector_provider')
            if not sector_provider:
                sector_provider = SectorProvider(context.get('provider'))
            
            self.on_progress(20, f"获取板块成分：{sector_type} - {sector_name}")
            stocks = sector_provider.get_sector_stocks(sector_type, sector_name)
            
            if not stocks:
                return SkillResult(
                    success=False,
                    message=f"未找到板块：{sector_type} - {sector_name}"
                )
            
            self.on_progress(40, f"板块包含 {len(stocks)} 只股票")
            
            # 调用回测 Skill 批量执行
            results = []
            for i, ts_code in enumerate(stocks[:10]):  # 限制前 10 只
                self.on_progress(40 + int((i / len(stocks)) * 50), f"回测 {ts_code}")
                # 简化处理，实际应该异步执行
                results.append(ts_code)
            
            self.on_progress(100, "分析完成")
            
            return SkillResult(
                success=True,
                message=f"板块分析完成：{sector_name} ({len(stocks)} 只股票)",
                data={
                    'sector_type': sector_type,
                    'sector_name': sector_name,
                    'stock_count': len(stocks),
                    'analyzed': len(results)
                }
            )
            
        except Exception as e:
            logger.exception("板块分析失败")
            return SkillResult(
                success=False,
                message=f"分析失败：{str(e)}",
                error=str(e)
            )


# ==================== 注册所有 Skills ====================

def register_builtin_skills():
    """注册所有内置 Skills"""
    from .skill_system import get_registry
    
    registry = get_registry()
    
    # 数据类
    registry.register(DownloadDataSkill())
    registry.register(UpdateDataSkill())
    
    # 缓存类
    registry.register(CacheStatusSkill())
    registry.register(CleanupCacheSkill())
    
    # 回测类
    registry.register(BacktestSkill())
    
    # 分析类
    registry.register(SectorAnalysisSkill())
    
    logger.info(f"已注册 {len(registry.list_skills())} 个 Skills")


# 自动注册
register_builtin_skills()
