"""
回测配置管理模块
支持从 YAML/JSON 文件加载回测配置
"""
import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from loguru import logger


@dataclass
class BacktestConfig:
    """回测配置"""
    strategy: str = "dual_ma"
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    
    ts_code: str = ""
    ts_codes: List[str] = field(default_factory=list)  # 多股票模式
    
    start_date: str = "20200101"
    end_date: str = "20231231"
    
    # 板块配置
    sector_type: str = "custom"  # industry/concept/area/custom
    sector_name: str = ""
    
    # 回测引擎配置
    mode: str = "individual"  # individual/portfolio/leaders
    top_n: int = 5  # 龙头股数量
    workers: int = 4
    use_processes: bool = False
    
    # 交易配置
    initial_cash: float = 100000.0
    commission_rate: float = 0.0003
    slippage_rate: float = 0.001
    max_position_pct: float = 1.0
    
    # 输出配置
    save_record: bool = True
    export_report: str = ""  # html/md/both
    save_plot: bool = False
    output_dir: str = "./output"
    
    # 备注
    notes: str = ""
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BacktestConfig':
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class BacktestConfigLoader:
    """
    回测配置加载器
    
    支持格式：
    - YAML
    - JSON
    """
    
    @staticmethod
    def load(path: str) -> BacktestConfig:
        """
        从文件加载配置
        
        Args:
            path: 配置文件路径
            
        Returns:
            BacktestConfig: 配置对象
        """
        path = Path(path)
        
        # 如果是相对路径，从当前工作目录查找
        if not path.is_absolute():
            # 首先尝试当前工作目录
            if not path.exists():
                # 然后尝试项目根目录
                project_root = Path(__file__).parent.parent.parent
                alt_path = project_root / path
                if alt_path.exists():
                    path = alt_path
                else:
                    raise FileNotFoundError(f"配置文件不存在：{path}")
        
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在：{path}")
        
        # 根据扩展名选择加载方式
        if path.suffix in ['.yaml', '.yml']:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        elif path.suffix == '.json':
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            raise ValueError(f"不支持的配置文件格式：{path.suffix}")
        
        # 合并环境变量覆盖
        data = BacktestConfigLoader._merge_env_vars(data)
        
        logger.info(f"已加载配置文件：{path}")
        return BacktestConfig.from_dict(data)
    
    @staticmethod
    def _merge_env_vars(data: dict) -> dict:
        """
        使用环境变量覆盖配置
        
        支持的环境变量：
        - TUSHARE_TOKEN
        - BACKTEST_START_DATE
        - BACKTEST_END_DATE
        - BACKTEST_TS_CODE
        - 等
        """
        # 环境变量映射
        env_map = {
            'TUSHARE_TOKEN': ('token', str),
            'BACKTEST_START_DATE': ('start_date', str),
            'BACKTEST_END_DATE': ('end_date', str),
            'BACKTEST_TS_CODE': ('ts_code', str),
            'BACKTEST_STRATEGY': ('strategy', str),
            'BACKTEST_WORKERS': ('workers', int),
        }
        
        for env_var, (config_key, type_func) in env_map.items():
            value = os.getenv(env_var)
            if value:
                try:
                    data[config_key] = type_func(value)
                    logger.debug(f"环境变量覆盖：{env_var} -> {config_key}={value}")
                except Exception as e:
                    logger.warning(f"环境变量转换失败：{env_var}={value}")
        
        return data
    
    @staticmethod
    def save(config: BacktestConfig, path: str):
        """
        保存配置到文件
        
        Args:
            config: 配置对象
            path: 保存路径
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = config.to_dict()
        
        if path.suffix in ['.yaml', '.yml']:
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
        elif path.suffix == '.json':
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"不支持的配置文件格式：{path.suffix}")
        
        logger.info(f"已保存配置文件：{path}")


def create_sample_config(output_path: str = "backtest_config.yaml"):
    """
    创建示例配置文件
    
    Args:
        output_path: 输出路径
    """
    config = BacktestConfig(
        strategy="dual_ma",
        strategy_params={
            "short_window": 5,
            "long_window": 20
        },
        ts_code="000001.SZ",
        start_date="20230101",
        end_date="20231231",
        sector_type="custom",
        mode="individual",
        workers=4,
        initial_cash=100000,
        notes="示例配置"
    )
    
    BacktestConfigLoader.save(config, output_path)
    logger.info(f"已创建示例配置文件：{output_path}")
