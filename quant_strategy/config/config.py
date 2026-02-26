"""
配置管理模块
"""
import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, Any
from pathlib import Path


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_cash: float = 100000.0
    commission_rate: float = 0.0003
    slippage_rate: float = 0.001
    max_position_pct: float = 1.0
    allow_short: bool = False
    save_plot: bool = False  # 是否保存图表


@dataclass
class DataSourceConfig:
    """数据源配置"""
    provider: str = "tushare"
    token: str = ""
    use_cache: bool = True
    cache_dir: str = "./data_cache"


@dataclass
class StrategyConfig:
    """策略配置"""
    name: str = "DualMA"
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Config:
    """
    总配置类
    
    支持从 YAML 文件加载配置
    """
    # 数据源配置
    data_source: DataSourceConfig = field(default_factory=DataSourceConfig)
    
    # 回测配置
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    
    # 策略配置
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    
    # 回测标的
    ts_code: str = "000001.SZ"
    start_date: str = "20200101"
    end_date: str = "20231231"
    benchmark_code: str = "000001.SH"  # 上证指数作为基准
    
    # 日志配置
    log_level: str = "INFO"
    log_file: str = "./logs/backtest.log"
    
    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """从 YAML 文件加载配置"""
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        config = cls()
        
        if "data_source" in data:
            config.data_source = DataSourceConfig(**data["data_source"])
        
        if "backtest" in data:
            config.backtest = BacktestConfig(**data["backtest"])
        
        if "strategy" in data:
            config.strategy = StrategyConfig(**data["strategy"])
        
        for key in ["ts_code", "start_date", "end_date", "benchmark_code", 
                    "log_level", "log_file"]:
            if key in data:
                setattr(config, key, data[key])
        
        # 从环境变量覆盖 token
        if os.getenv("TUSHARE_TOKEN"):
            config.data_source.token = os.getenv("TUSHARE_TOKEN")
        
        return config
    
    def to_yaml(self, path: str):
        """保存配置到 YAML 文件"""
        data = {
            "data_source": {
                "provider": self.data_source.provider,
                "token": self.data_source.token,
                "use_cache": self.data_source.use_cache,
                "cache_dir": self.data_source.cache_dir
            },
            "backtest": {
                "initial_cash": self.backtest.initial_cash,
                "commission_rate": self.backtest.commission_rate,
                "slippage_rate": self.backtest.slippage_rate,
                "max_position_pct": self.backtest.max_position_pct,
                "allow_short": self.backtest.allow_short,
                "save_plot": self.backtest.save_plot
            },
            "strategy": {
                "name": self.strategy.name,
                "params": self.strategy.params
            },
            "ts_code": self.ts_code,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "benchmark_code": self.benchmark_code,
            "log_level": self.log_level,
            "log_file": self.log_file
        }
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    
    def validate(self) -> bool:
        """验证配置"""
        if not self.data_source.token:
            raise ValueError("Tushare token 不能为空，请设置 TUSHARE_TOKEN 环境变量或在配置中指定")
        
        if not self.ts_code:
            raise ValueError("股票代码不能为空")
        
        if self.start_date >= self.end_date:
            raise ValueError("开始日期必须早于结束日期")
        
        if self.backtest.initial_cash <= 0:
            raise ValueError("初始资金必须大于 0")
        
        return True
