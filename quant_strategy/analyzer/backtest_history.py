"""
回测历史记录管理模块
支持回测结果的保存、查询和统计分析
"""
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class BacktestRecord:
    """回测记录"""
    record_id: str              # 记录 ID
    timestamp: str              # 回测时间
    strategy: str               # 策略名称
    ts_code: str                # 股票代码
    start_date: str             # 开始日期
    end_date: str               # 结束日期
    
    # 回测结果指标
    total_return: float         # 总收益率
    annual_return: float        # 年化收益
    sharpe_ratio: float         # 夏普比率
    max_drawdown: float         # 最大回撤
    win_rate: float             # 胜率
    total_trades: int           # 交易次数
    
    # 回测配置
    initial_cash: float = 100000.0
    commission_rate: float = 0.0003
    slippage_rate: float = 0.001
    
    # 备注
    notes: str = ""
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BacktestRecord':
        """从字典创建"""
        return cls(**data)


class BacktestHistory:
    """
    回测历史管理器
    
    功能：
    - 保存回测结果
    - 查询历史记录
    - 统计分析
    - 导出报告
    """
    
    def __init__(self, history_dir: str = "./logs/backtest_history"):
        """
        初始化回测历史管理器
        
        Args:
            history_dir: 历史记录存储目录
        """
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
        self.records_file = self.history_dir / "records.json"
        self.records: List[BacktestRecord] = []
        
        self._load_records()
    
    def _load_records(self):
        """加载历史记录"""
        if self.records_file.exists():
            try:
                with open(self.records_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.records = [BacktestRecord.from_dict(r) for r in data]
                logger.debug(f"加载回测历史记录：{len(self.records)} 条")
            except Exception as e:
                logger.error(f"加载历史记录失败：{e}")
                self.records = []
    
    def _save_records(self):
        """保存历史记录"""
        try:
            with open(self.records_file, 'w', encoding='utf-8') as f:
                data = [r.to_dict() for r in self.records]
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"保存回测历史记录：{len(self.records)} 条")
        except Exception as e:
            logger.error(f"保存历史记录失败：{e}")
    
    def add_record(self, result: Any, strategy: str, ts_code: str,
                   start_date: str, end_date: str,
                   notes: str = "") -> BacktestRecord:
        """
        添加回测记录
        
        Args:
            result: 回测结果对象（BacktestResult）
            strategy: 策略名称
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            notes: 备注信息
            
        Returns:
            BacktestRecord: 创建的回测记录
        """
        record_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        record = BacktestRecord(
            record_id=record_id,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            strategy=strategy,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            total_return=result.total_return,
            annual_return=result.annual_return,
            sharpe_ratio=result.sharpe_ratio,
            max_drawdown=result.max_drawdown,
            win_rate=result.win_rate,
            total_trades=result.total_trades,
            initial_cash=result.initial_cash,
            notes=notes
        )
        
        self.records.append(record)
        self._save_records()
        
        logger.info(f"已保存回测记录：{record_id}")
        return record
    
    def query(self, 
              strategy: str = None,
              ts_code: str = None,
              start_date: str = None,
              end_date: str = None,
              min_return: float = None,
              max_return: float = None,
              limit: int = 100) -> pd.DataFrame:
        """
        查询回测记录
        
        Args:
            strategy: 策略名称过滤
            ts_code: 股票代码过滤
            start_date: 开始日期过滤（记录时间）
            end_date: 结束日期过滤（记录时间）
            min_return: 最小收益率过滤
            max_return: 最大收益率过滤
            limit: 返回记录数量限制
            
        Returns:
            DataFrame: 查询结果
        """
        if not self.records:
            return pd.DataFrame()
        
        # 转换为 DataFrame
        df = pd.DataFrame([r.to_dict() for r in self.records])
        
        # 过滤条件
        if strategy:
            df = df[df['strategy'] == strategy]
        
        if ts_code:
            df = df[df['ts_code'] == ts_code]
        
        if start_date:
            df = df[df['timestamp'] >= start_date]
        
        if end_date:
            df = df[df['timestamp'] <= end_date]
        
        if min_return is not None:
            df = df[df['total_return'] >= min_return]
        
        if max_return is not None:
            df = df[df['total_return'] <= max_return]
        
        # 按时间倒序排序
        df = df.sort_values('timestamp', ascending=False)
        
        # 限制数量
        df = df.head(limit)
        
        return df
    
    def get_strategy_stats(self, strategy: str = None) -> pd.DataFrame:
        """
        获取策略统计
        
        Args:
            strategy: 策略名称，None 表示所有策略
            
        Returns:
            DataFrame: 统计数据
        """
        if not self.records:
            return pd.DataFrame()
        
        df = pd.DataFrame([r.to_dict() for r in self.records])
        
        if strategy:
            df = df[df['strategy'] == strategy]
            group_cols = ['strategy']
        else:
            group_cols = ['strategy']
        
        # 分组统计
        stats = df.groupby(group_cols).agg({
            'total_return': ['mean', 'std', 'min', 'max', 'count'],
            'sharpe_ratio': ['mean', 'std'],
            'max_drawdown': ['mean', 'min'],
            'win_rate': ['mean'],
            'total_trades': ['sum', 'mean']
        }).round(4)
        
        # 扁平化列名
        stats.columns = ['_'.join(col).strip() for col in stats.columns]
        stats = stats.rename(columns={
            'total_return_mean': '平均收益',
            'total_return_std': '收益标准差',
            'total_return_min': '最小收益',
            'total_return_max': '最大收益',
            'total_return_count': '回测次数',
            'sharpe_ratio_mean': '平均夏普',
            'max_drawdown_mean': '平均回撤',
            'max_drawdown_min': '最大回撤',
            'win_rate_mean': '平均胜率',
            'total_trades_sum': '总交易次数',
            'total_trades_mean': '平均交易次数'
        })
        
        return stats
    
    def get_recent_records(self, limit: int = 10) -> pd.DataFrame:
        """
        获取最近回测记录
        
        Args:
            limit: 返回记录数量
            
        Returns:
            DataFrame: 最近记录
        """
        return self.query(limit=limit)
    
    def export_report(self, output_path: str = None) -> str:
        """
        导出回测报告
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            str: 输出文件路径
        """
        if output_path is None:
            output_path = self.history_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        if not self.records:
            logger.warning("没有回测记录可导出")
            return ""
        
        df = pd.DataFrame([r.to_dict() for r in self.records])
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        logger.info(f"已导出回测报告：{output_path}")
        return str(output_path)
    
    def clear(self, older_than_days: int = None):
        """
        清理历史记录
        
        Args:
            older_than_days: 清理超过此天数的记录，None 表示清空所有
        """
        if not self.records:
            return
        
        if older_than_days is None:
            self.records = []
        else:
            cutoff = datetime.now().timestamp() - (older_than_days * 86400)
            cutoff_str = datetime.fromtimestamp(cutoff).strftime("%Y-%m-%d %H:%M:%S")
            self.records = [r for r in self.records if r.timestamp >= cutoff_str]
        
        self._save_records()
        logger.info(f"清理完成，剩余 {len(self.records)} 条记录")
    
    def get_record_count(self) -> int:
        """获取记录总数"""
        return len(self.records)
