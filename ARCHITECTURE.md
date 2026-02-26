# 量化策略回测系统 - 架构文档

> 详细技术架构说明，供开发者参考

## 系统分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    用户接口层 (CLI)                          │
│  cli.py - 9 个主要命令                                        │
├─────────────────────────────────────────────────────────────┤
│                    应用层 (Application)                      │
│  main.py - 回测流程编排                                       │
├─────────────────────────────────────────────────────────────┤
│                    数据层 (Data Layer)                       │
│  TushareDataProvider / SectorDataProvider / DataCache       │
├─────────────────────────────────────────────────────────────┤
│                    策略层 (Strategy Layer)                   │
│  BaseStrategy + 9 种具体策略实现                               │
├─────────────────────────────────────────────────────────────┤
│                    回测引擎层 (Backtest Engine)              │
│  Backtester / ParallelBacktester / SimulatedBroker          │
├─────────────────────────────────────────────────────────────┤
│                    分析层 (Analysis Layer)                   │
│  PerformanceAnalyzer / Visualizer / ReportExporter          │
├─────────────────────────────────────────────────────────────┤
│                    优化层 (Optimizer Layer)                  │
│  ParamOptimizer (网格搜索/随机搜索)                          │
└─────────────────────────────────────────────────────────────┘
```

## 核心模块说明

### 数据层 (`data/`)

| 模块 | 功能 | 存储格式 |
|------|------|---------|
| `tushare_provider.py` | Tushare API 封装 | - |
| `sector_provider.py` | 板块数据管理 | - |
| `data_cache.py` | 本地缓存 | Parquet |

**缓存结构：**
```
data_cache/
├── metadata.csv          # 元数据索引
├── daily_ts_code=xxx_*.parquet   # 日线数据
└── adj_factor_*.parquet          # 复权因子
```

### 策略层 (`strategy/`)

**策略基类接口：**
```python
class BaseStrategy:
    def on_init(self, data): pass           # 初始化指标
    def on_bar_start(self, data, idx): pass # K 线开始回调
    def generate_signal(self, data, idx):   # 生成信号（抽象）
    def on_bar_end(self, data, idx, signal): pass
    def on_backtest_end(self): pass
```

**9 种策略实现：**
- 趋势跟踪：`dual_ma`, `macd`, `dmi`
- 超买超卖：`kdj`, `rsi`, `cci`
- 均值回归：`boll`
- 动量：`momentum`
- 量价：`volume_price`

### 回测引擎层 (`backtester/`)

**单引擎 (`engine.py`)：**
- 事件驱动回测主循环
- 信号生成与执行
- 每日资产记录

**高并发引擎 (`parallel_engine.py`)：**
- `ProcessPoolExecutor` 多进程
- `ThreadPoolExecutor` 多线程
- 批量回测/板块回测/策略对比

**模拟券商 (`broker.py`)：**
- 订单提交与撮合
- 持仓管理
- 交易成本计算（佣金/印花税/滑点）

### 分析层 (`analyzer/`)

| 模块 | 功能 |
|------|------|
| `analyzer.py` | 夏普比率、最大回撤、Alpha/Beta 等 |
| `visualizer.py` | 资产曲线、回撤、收益分布图 |
| `report.py` | HTML/Markdown 报告导出 |

## 设计模式

### 1. 策略模式
```python
strategy_map = {
    "dual_ma": DualMAStrategy,
    "kdj": KDJStrategy,
    ...
}
strategy = strategy_map[name](**params)
```

### 2. 工厂模式
策略通过名称映射到具体类，支持动态扩展。

### 3. 并行模式
```python
with ProcessPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(task) for task in tasks]
```

## 数据流

```
CLI 命令 → Config → DataProvider → Strategy → Backtester
                                              ↓
                                         Broker → 交易记录
                                              ↓
                                         Analyzer → 报告
```

## 扩展指南

### 添加新策略
1. 继承 `BaseStrategy`
2. 实现 `generate_signal()`
3. 在 `strategy/__init__.py` 导出
4. 在 `cli.py` 和 `main.py` 注册

### 添加新数据源
1. 实现统一接口方法
2. 在 `data/__init__.py` 导出

## 性能优化建议

1. **启用缓存**：减少 Tushare API 调用
2. **多进程回测**：`--workers 8 --use_processes`
3. **关闭图表**：默认 `save_plot=False`
4. **批量获取数据**：使用 `backtest_sector` 而非循环调用

## 依赖说明

| 依赖 | 用途 | 必需 |
|------|------|------|
| pandas | 数据处理 | ✓ |
| numpy | 数值计算 | ✓ |
| tushare | 数据源 | ✓ |
| matplotlib | 图表绘制 | ○ |
| pyyaml | 配置管理 | ✓ |
| loguru | 日志 | ✓ |
| tqdm | 进度条 | ✓ |

○ = 可选（不使用图表可不安装 matplotlib）
