# 量化策略回测系统

> 一个功能完整的 Python 量化策略回测系统，支持高并发回测、板块分析、多策略对比

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 设置 Tushare Token
export TUSHARE_TOKEN=your_token_here

# 查看可用策略
python -m quant_strategy.cli strategies

# 运行回测
python -m quant_strategy.cli backtest --strategy dual_ma --ts_code 000001.SZ
```

## 核心功能

| 功能 | 描述 | 命令示例 |
|------|------|----------|
| 📊 **策略回测** | 支持 9 种交易策略 | `backtest --strategy kdj --ts_code 000001.SZ` |
| 🚀 **高并发回测** | 多进程/多线程并行 | `sector-backtest --workers 8 --use_processes` |
| 📈 **板块回测** | 行业/概念/地区板块 | `sector-backtest --sector_type industry --sector_name 银行` |
| ⚖️ **多策略对比** | 同时对比多个策略 | `compare --strategies dual_ma kdj rsi` |
| 🔧 **参数优化** | 网格搜索/随机搜索 | `optimize --strategy dual_ma --method grid` |
| 💾 **数据缓存** | 本地 Parquet 缓存 | `data list-cache` |
| 📄 **报告导出** | HTML/Markdown 格式 | `backtest --export html` |

## 策略列表

| 策略代码 | 策略名称 | 类型 | 核心指标 |
|---------|---------|------|---------|
| `dual_ma` | 双均线策略 | 趋势跟踪 | MA |
| `momentum` | 动量策略 | 动量 | RSI, Momentum |
| `kdj` | KDJ 短线策略 | 超买超卖 | KDJ |
| `rsi` | RSI 短线策略 | 超买超卖 | RSI |
| `boll` | 布林线策略 | 均值回归 | Bollinger Bands |
| `dmi` | DMI 趋势策略 | 趋势强度 | DMI, ADX |
| `cci` | CCI 顺势策略 | 超买超卖 | CCI |
| `macd` | MACD 策略 | 趋势跟踪 | MACD |
| `volume_price` | 量价策略 | 量价分析 | Volume, MA |

## 使用示例

### 1. 单股票回测

```bash
# 基础回测（不生成图表）
python -m quant_strategy.cli backtest \
    --strategy dual_ma \
    --ts_code 000001.SZ

# 回测并导出 HTML 报告
python -m quant_strategy.cli backtest \
    --strategy kdj \
    --ts_code 000001.SZ \
    --export html

# 回测并保存图表
python -m quant_strategy.cli backtest \
    --strategy rsi \
    --ts_code 000001.SZ \
    --save_plot
```

### 2. 板块/组合回测（高并发）

```bash
# 行业板块回测
python -m quant_strategy.cli sector-backtest \
    --strategy dual_ma \
    --sector_type industry \
    --sector_name 银行 \
    --workers 8 \
    --use_processes

# 概念板块回测
python -m quant_strategy.cli sector-backtest \
    --strategy kdj \
    --sector_type concept \
    --sector_name 人工智能

# 自定义股票组合
python -m quant_strategy.cli sector-backtest \
    --strategy rsi \
    --sector_type custom \
    --ts_codes 000001.SZ 000002.SZ 000063.SZ
```

### 3. 多策略对比

```bash
python -m quant_strategy.cli compare \
    --strategies dual_ma kdj rsi boll macd \
    --ts_code 000001.SZ \
    --workers 4
```

### 4. 参数优化

```bash
# 网格搜索
python -m quant_strategy.cli optimize \
    --strategy dual_ma \
    --ts_code 000001.SZ \
    --method grid

# 随机搜索
python -m quant_strategy.cli optimize \
    --strategy kdj \
    --method random \
    --n_iterations 100
```

### 5. 数据管理

```bash
# 列出本地缓存
python -m quant_strategy.cli data list-cache

# 缓存统计
python -m quant_strategy.cli data cache-stats

# 批量下载数据
python -m quant_strategy.cli data download \
    --ts_codes 000001.SZ 000002.SZ \
    --start_date 20200101 \
    --end_date 20231231
```

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI 命令行接口                          │
├─────────────────────────────────────────────────────────────┤
│  backtest  │  sector-backtest  │  compare  │  optimize      │
├─────────────────────────────────────────────────────────────┤
│                     回测引擎层                                │
│  ┌─────────────────┐  ┌─────────────────────────────┐       │
│  │  Backtester     │  │  ParallelBacktester         │       │
│  │  (单进程)       │  │  (多进程/多线程)             │       │
│  └─────────────────┘  └─────────────────────────────┘       │
├─────────────────────────────────────────────────────────────┤
│                     策略层                                   │
│  DualMA │ Momentum │ KDJ │ RSI │ BOLL │ DMI │ CCI │ MACD   │
├─────────────────────────────────────────────────────────────┤
│                     数据层                                   │
│  TushareProvider  │  SectorProvider  │  DataCache          │
└─────────────────────────────────────────────────────────────┘
```

详细架构文档请参阅 [ARCHITECTURE.md](ARCHITECTURE.md)

## 项目结构

```
quant_strategy/
├── cli.py                 # CLI 命令行入口
├── main.py                # 回测主流程
├── config/                # 配置模块
├── data/                  # 数据层 (Tushare/板块/缓存)
├── strategy/              # 策略层 (9 种策略)
├── backtester/            # 回测引擎层 (单进程/高并发)
├── analyzer/              # 分析层 (绩效/可视化/报告)
├── optimizer/             # 优化层 (参数优化)
└── broker/                # 券商接口扩展
```

## 配置示例

### 环境变量
```bash
export TUSHARE_TOKEN=your_token_here
```

### YAML 配置文件
```yaml
# config.yaml
data_source:
  token: your_token_here
  use_cache: true

backtest:
  initial_cash: 100000
  commission_rate: 0.0003
  slippage_rate: 0.001
  save_plot: false

strategy:
  name: dual_ma
  params:
    short_window: 5
    long_window: 20

ts_code: 000001.SZ
start_date: "20200101"
end_date: "20231231"
```

## CLI 命令速查

```
命令:
  strategies              列出所有可用策略
  backtest               单股票回测
  sector-backtest        板块/组合回测
  compare                多策略对比
  optimize               参数优化
  data                   数据相关操作

数据命令:
  data list-stocks       列出股票
  data list-indices      列出指数
  data list-industries   列出行业板块
  data list-concepts     列出概念板块
  data stock-info        查询股票信息
  data download          批量下载数据
  data list-cache        列出本地缓存
  data cache-stats       显示缓存统计
  data scan              策略扫描器
```

## 依赖

```txt
tushare>=1.2.89      # 数据源
pandas>=2.0.0        # 数据处理
numpy>=1.24.0        # 数值计算
matplotlib>=3.7.0    # 图表绘制
pyyaml>=6.0          # 配置管理
loguru>=0.7.0        # 日志
tqdm>=4.65.0         # 进度条
```

## 开发指南

### 添加新策略

1. 继承 `BaseStrategy` 类
2. 实现 `generate_signal()` 方法
3. 在 `strategy/__init__.py` 中导出
4. 在 CLI 中注册

```python
from quant_strategy.strategy import BaseStrategy, Signal, SignalType

class MyStrategy(BaseStrategy):
    def generate_signal(self, data, idx):
        # 实现你的策略逻辑
        if buy_condition:
            return Signal(SignalType.BUY, price, strength=0.8)
        return None
```

### 性能调优

- 使用 `--workers` 指定并发数
- 启用 `--use_processes` 使用多进程
- 开启数据缓存减少 API 调用
- 关闭图表生成 (`--save_plot` 默认关闭)

## 常见问题

**Q: 如何获取 Tushare Token?**
A: 访问 [tushare.pro](https://tushare.pro) 注册并获取 Token

**Q: 回测结果为什么和实际交易有差异？**
A: 回测使用历史数据，未考虑市场冲击、流动性等因素，仅供参考

**Q: 如何加快回测速度？**
A: 使用 `--workers` 参数增加并发数，启用数据缓存

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

---

**免责声明**: 本系统仅供学习研究使用，不构成投资建议。使用本系统进行实盘交易的风险由用户自行承担。
