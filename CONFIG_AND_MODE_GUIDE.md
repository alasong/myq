# 回测配置与多模式回测指南

## 一、配置文件支持

### 1.1 为什么需要配置文件？

随着回测参数越来越多，命令行输入变得复杂：

```bash
# 命令行参数越来越多...
python -m quant_strategy.cli sector-backtest \
    --strategy kdj \
    --sector_type concept \
    --sector_name 人工智能 \
    --start_date 20250101 \
    --end_date 20251231 \
    --mode portfolio \
    --top_n 5 \
    --workers 8 \
    --use_processes
```

**解决方案：** 使用配置文件

```bash
# 简洁明了
python -m quant_strategy.cli sector-backtest --config configs/sector_backtest.yaml
```

---

### 1.2 配置文件格式

支持 **YAML** 和 **JSON** 两种格式：

#### YAML 格式（推荐）

```yaml
# configs/backtest_config.yaml
strategy: dual_ma
strategy_params:
  short_window: 5
  long_window: 20

ts_code: "000001.SZ"
start_date: "20230101"
end_date: "20231231"

initial_cash: 100000
commission_rate: 0.0003

mode: individual
workers: 4

save_record: true
notes: "双均线策略回测"
```

#### JSON 格式

```json
{
  "strategy": "dual_ma",
  "strategy_params": {
    "short_window": 5,
    "long_window": 20
  },
  "ts_code": "000001.SZ",
  "start_date": "20230101",
  "end_date": "20231231",
  "mode": "individual"
}
```

---

### 1.3 完整配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `strategy` | string | dual_ma | 策略名称 |
| `strategy_params` | object | {} | 策略参数 |
| `ts_code` | string | "" | 股票代码 |
| `ts_codes` | array | [] | 多股票代码列表 |
| `start_date` | string | 20200101 | 开始日期 |
| `end_date` | string | 20231231 | 结束日期 |
| `sector_type` | string | custom | 板块类型 |
| `sector_name` | string | "" | 板块名称 |
| `mode` | string | individual | 回测模式 |
| `top_n` | int | 5 | 龙头股数量 |
| `workers` | int | 4 | 并发数 |
| `use_processes` | bool | false | 多进程模式 |
| `initial_cash` | float | 100000 | 初始资金 |
| `commission_rate` | float | 0.0003 | 佣金率 |
| `slippage_rate` | float | 0.001 | 滑点率 |
| `save_record` | bool | true | 保存回测记录 |
| `export_report` | string | "" | 导出报告格式 |
| `save_plot` | bool | false | 保存图表 |
| `notes` | string | "" | 备注 |

---

### 1.4 使用配置文件

```bash
# 单股票回测
python -m quant_strategy.cli backtest \
    --config configs/backtest_config.yaml

# 板块回测
python -m quant_strategy.cli sector-backtest \
    --config configs/sector_backtest.yaml

# 覆盖配置文件中的参数
python -m quant_strategy.cli backtest \
    --config configs/backtest_config.yaml \
    --ts_code 000002.SZ
```

---

### 1.5 环境变量覆盖

支持通过环境变量覆盖配置：

```bash
# 覆盖回测日期
export BACKTEST_START_DATE=20240101
export BACKTEST_END_DATE=20241231

# 覆盖股票代码
export BACKTEST_TS_CODE=000001.SZ

# 覆盖策略
export BACKTEST_STRATEGY=kdj

# 运行回测（自动应用环境变量）
python -m quant_strategy.cli backtest \
    --config configs/backtest_config.yaml
```

---

## 二、多种回测模式

### 2.1 individual 模式（逐个回测）

**逻辑：** 对板块内每只股票独立回测

```bash
python -m quant_strategy.cli sector-backtest \
    --strategy kdj \
    --sector_type industry \
    --sector_name 电子 \
    --mode individual \
    --start_date 20250101 \
    --end_date 20251231
```

**输出：**
```
================================================================================
板块回测结果汇总
回测模式：individual
================================================================================
       代码     收益率    夏普    最大回撤  交易次数
300003.SZ  38.33%  1.09 -14.54%    13
300002.SZ  -6.55% -0.23 -15.64%    13
300001.SZ -33.31% -1.58 -33.31%    17
================================================================================
```

**适用场景：**
- 发现板块内强势股
- 对比板块内股票表现
- 选股策略

---

### 2.2 portfolio 模式（等权组合）

**逻辑：** 计算板块等权平均收益

```bash
python -m quant_strategy.cli sector-backtest \
    --strategy kdj \
    --sector_type industry \
    --sector_name 电子 \
    --mode portfolio \
    --start_date 20250101 \
    --end_date 20251231
```

**输出：**
```
================================================================================
板块回测结果汇总
回测模式：portfolio
================================================================================
       代码     收益率    夏普    最大回撤  交易次数
PORTFOLIO  12.45%  0.85  -8.23%    35
300003.SZ  38.33%  1.09 -14.54%    13
300002.SZ  -6.55% -0.23 -15.64%    13
...
================================================================================
```

**特点：**
- 新增 `PORTFOLIO` 行显示组合收益
- 组合收益 = 所有股票收益的等权平均

**适用场景：**
- 板块整体配置
- 分散投资风险
- 获取板块平均收益

---

### 2.3 leaders 模式（龙头股）

**逻辑：** 选择板块内前 N 大龙头股回测

```bash
python -m quant_strategy.cli sector-backtest \
    --strategy kdj \
    --sector_type industry \
    --sector_name 电子 \
    --mode leaders \
    --top_n 5 \
    --start_date 20250101 \
    --end_date 20251231
```

**龙头股评分标准：**
- 成交额（40%）：代表市值和流动性
- 收益率（40%）：历史表现
- 波动率（-20%）：风险调整

**输出：**
```
================================================================================
板块回测结果汇总
回测模式：leaders
龙头股模式：选择前 5 只股票
================================================================================
       代码     收益率    夏普    最大回撤  交易次数
300003.SZ  38.33%  1.09 -14.54%    13
300001.SZ -33.31% -1.58 -33.31%    17
...
================================================================================
```

**适用场景：**
- 龙头股策略
- 资金有限无法配置全部
- 关注板块代表性股票

---

## 三、模式对比

| 模式 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **individual** | 简单直接，可发现强势股 | 结果分散，忽略相关性 | 选股策略，板块内对比 |
| **portfolio** | 分散风险，代表板块 | 稀释龙头股收益 | 板块配置，分散投资 |
| **leaders** | 聚焦核心，资金集中 | 可能错过补涨股 | 龙头策略，资金有限 |

---

## 四、配置文件示例

### 4.1 单股票回测配置

```yaml
# configs/backtest_config.yaml
strategy: dual_ma
strategy_params:
  short_window: 5
  long_window: 20

ts_code: "000001.SZ"
start_date: "20230101"
end_date: "20231231"

initial_cash: 100000
save_record: true
notes: "双均线策略回测"
```

### 4.2 板块回测配置（逐个模式）

```yaml
# configs/sector_backtest_individual.yaml
strategy: kdj
strategy_params:
  n: 9
  m1: 3
  m2: 3

sector_type: industry
sector_name: 电子

start_date: "20250101"
end_date: "20251231"

mode: individual
workers: 4

notes: "电子行业回测 - 逐个模式"
```

### 4.3 板块回测配置（组合模式）

```yaml
# configs/sector_backtest_portfolio.yaml
strategy: kdj

sector_type: concept
sector_name: 人工智能

start_date: "20250101"
end_date: "20251231"

mode: portfolio  # 等权组合

workers: 8
use_processes: true

notes: "人工智能概念 - 组合模式"
```

### 4.4 板块回测配置（龙头股模式）

```yaml
# configs/sector_backtest_leaders.yaml
strategy: rsi

sector_type: industry
sector_name: 医药

start_date: "20250101"
end_date: "20251231"

mode: leaders  # 龙头股
top_n: 5  # 前 5 大龙头

workers: 4

notes: "医药行业 - 龙头股模式"
```

### 4.5 自定义股票组合配置

```yaml
# configs/custom_portfolio.yaml
strategy: first_limit_up
strategy_params:
  min_close_ratio: 0.095
  hold_days: 3

sector_type: custom  # 自定义模式
ts_codes:
  - "000001.SZ"
  - "000002.SZ"
  - "300001.SZ"
  - "300002.SZ"
  - "300003.SZ"

start_date: "20250101"
end_date: "20251231"

mode: portfolio  # 组合模式

notes: "自定义股票组合"
```

---

## 五、命令速查

### 5.1 使用配置文件

```bash
# 单股票回测
python -m quant_strategy.cli backtest --config configs/backtest.yaml

# 板块回测
python -m quant_strategy.cli sector-backtest --config configs/sector.yaml

# 覆盖配置参数
python -m quant_strategy.cli backtest \
    --config configs/backtest.yaml \
    --ts_code 000002.SZ
```

### 5.2 指定回测模式

```bash
# 逐个回测
python -m quant_strategy.cli sector-backtest \
    --strategy kdj \
    --sector_type industry \
    --sector_name 电子 \
    --mode individual

# 等权组合
python -m quant_strategy.cli sector-backtest \
    --strategy kdj \
    --sector_type industry \
    --sector_name 电子 \
    --mode portfolio

# 龙头股
python -m quant_strategy.cli sector-backtest \
    --strategy kdj \
    --sector_type industry \
    --sector_name 电子 \
    --mode leaders \
    --top_n 5
```

---

## 六、最佳实践

### 6.1 配置文件管理

```
configs/
├── backtest_config.yaml          # 单股票回测配置
├── sector_backtest_individual.yaml  # 板块逐个回测
├── sector_backtest_portfolio.yaml   # 板块组合回测
├── sector_backtest_leaders.yaml     # 板块龙头回测
└── custom_portfolio.yaml            # 自定义组合
```

### 6.2 工作流示例

```bash
# 1. 创建配置文件
cat > configs/my_backtest.yaml << EOF
strategy: dual_ma
ts_code: "000001.SZ"
start_date: "20230101"
end_date: "20231231"
mode: individual
EOF

# 2. 运行回测
python -m quant_strategy.cli backtest --config configs/my_backtest.yaml

# 3. 查看历史记录
python -m quant_strategy.cli history

# 4. 导出统计
python -m quant_strategy.cli history --stats --export
```

### 6.3 多模式对比

```bash
# 对比不同模式的结果
for mode in individual portfolio leaders; do
    python -m quant_strategy.cli sector-backtest \
        --config configs/sector.yaml \
        --mode $mode
done
```

---

## 七、常见问题

### Q1: 配置文件和命令行参数哪个优先级高？

**A:** 命令行参数优先级更高，会覆盖配置文件中的值。

### Q2: 如何生成示例配置文件？

**A:** 
```python
from quant_strategy.config import create_sample_config
create_sample_config("my_config.yaml")
```

### Q3: portfolio 模式的组合收益如何计算？

**A:** 等权平均所有股票的每日收益率，然后计算累计收益。

### Q4: leaders 模式如何选择龙头股？

**A:** 综合评分：成交额 (40%) + 收益率 (40%) - 波动率 (20%)

### Q5: 配置文件支持环境变量吗？

**A:** 支持！如 `BACKTEST_START_DATE=20240101` 会覆盖配置中的 `start_date`。
