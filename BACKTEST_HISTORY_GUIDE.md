# 回测历史与策略管理指南

## 一、回测历史记录

### 1.1 自动保存

每次执行 `backtest` 命令后，回测结果会自动保存到历史记录：

```bash
# 执行回测（自动保存记录）
python -m quant_strategy.cli backtest \
    --strategy dual_ma \
    --ts_code 000001.SZ \
    --start_date 20250101 \
    --end_date 20251231
```

**保存位置：** `./logs/backtest_history/records.json`

### 1.2 查询历史记录

```bash
# 查看最近 20 条记录
python -m quant_strategy.cli history

# 查看最近 50 条记录
python -m quant_strategy.cli history --limit 50

# 按策略名称过滤
python -m quant_strategy.cli history --strategy dual_ma

# 按股票代码过滤
python -m quant_strategy.cli history --ts_code 000001.SZ
```

**输出示例：**
```
====================================================================================================
回测历史记录
====================================================================================================
           timestamp   strategy    ts_code total_return sharpe_ratio max_drawdown total_trades     notes
====================================================================================================
2026-02-26 23:25:30   dual_ma  000001.SZ       15.23%       1.25      -8.56%         12      CLI 回测
2026-02-26 23:20:15      kdj  300001.SZ       -5.67%      -0.45      -12.34%        25      CLI 回测
====================================================================================================
共 2 条记录
```

### 1.3 策略统计

```bash
# 查看所有策略的统计数据
python -m quant_strategy.cli history --stats

# 查看特定策略的统计数据
python -m quant_strategy.cli history --strategy dual_ma --stats
```

**统计指标：**
- 平均收益率
- 收益标准差
- 最小/最大收益
- 平均夏普比率
- 平均最大回撤
- 平均胜率
- 总交易次数
- 回测次数

### 1.4 导出报告

```bash
# 导出 CSV 报告
python -m quant_strategy.cli history --export
```

**导出位置：** `./logs/backtest_history/report_YYYYMMDD_HHMMSS.csv`

### 1.5 清理历史记录

```python
from quant_strategy.analyzer import BacktestHistory

history = BacktestHistory()

# 清空所有记录
history.clear()

# 清理 30 天前的记录
history.clear(older_than_days=30)
```

---

## 二、策略批量管理

### 2.1 单个策略操作

```bash
# 停用单个策略
python -m quant_strategy.cli strategy disable \
    --name dual_ma \
    --reason "收益率太差"

# 激活单个策略
python -m quant_strategy.cli strategy enable --name dual_ma
```

### 2.2 批量操作（新增）

```bash
# 批量停用多个策略
python -m quant_strategy.cli strategy disable-batch \
    --names kdj rsi macd dual_ma \
    --reason "表现不佳"

# 批量激活多个策略
python -m quant_strategy.cli strategy enable-batch \
    --names kdj rsi macd
```

**输出示例：**
```
23:27:16 | INFO | 策略已停用：kdj, 原因：表现不佳
23:27:16 | INFO | 策略 kdj 已停用：表现不佳
23:27:16 | INFO | 策略已停用：rsi, 原因：表现不佳
23:27:16 | INFO | 策略已停用：macd, 原因：表现不佳
23:27:16 | INFO | 批量停用完成：3/3 个策略
```

### 2.3 查看策略状态

```bash
# 查看所有策略状态
python -m quant_strategy.cli strategy list

# 或简写
python -m quant_strategy.cli strategy
```

**输出示例：**
```
======================================================================
策略状态列表
======================================================================
策略名称                 | 状态       | 停用原因                          
----------------------------------------------------------------------
boll                 | 激活       | 
cci                  | 激活       | 
dual_ma              | 停用       | 收益率太差
kdj                  | 停用       | 波动过大
macd                 | 激活       | 
...
======================================================================
总计：12 个策略，激活：10 个，停用：2 个
======================================================================
```

---

## 三、使用场景

### 3.1 策略筛选流程

```bash
# 1. 批量回测所有激活的策略
python -m quant_strategy.cli batch-backtest \
    --ts_code 300001.SZ \
    --start_date 20250101 \
    --end_date 20251231

# 2. 查看回测结果，找出表现差的策略
python -m quant_strategy.cli history --stats

# 3. 批量停用表现差的策略
python -m quant_strategy.cli strategy disable-batch \
    --names kdj rsi macd \
    --reason "收益率不达标"

# 4. 激活表现好的策略
python -m quant_strategy.cli strategy enable-batch \
    --names cci boll fear_greed

# 5. 再次回测验证
python -m quant_strategy.cli batch-backtest \
    --ts_code 300002.SZ \
    --start_date 20250101 \
    --end_date 20251231
```

### 3.2 定期评估流程

```bash
# 1. 导出历史回测报告
python -m quant_strategy.cli history --export

# 2. 查看策略统计
python -m quant_strategy.cli history --stats

# 3. 根据统计结果调整策略池
# 停用平均收益率为负的策略
python -m quant_strategy.cli strategy disable-batch \
    --names dual_ma momentum \
    --reason "长期收益为负"

# 4. 重新激活之前停用的策略进行测试
python -m quant_strategy.cli strategy enable-batch \
    --names kdj
```

### 3.3 策略对比流程

```bash
# 1. 对同一股票运行多个策略的回测
for strategy in dual_ma kdj rsi macd; do
    python -m quant_strategy.cli backtest \
        --strategy $strategy \
        --ts_code 000001.SZ \
        --start_date 20250101 \
        --end_date 20251231
done

# 2. 查看历史记录对比
python -m quant_strategy.cli history --ts_code 000001.SZ

# 3. 查看策略统计
python -m quant_strategy.cli history --stats
```

---

## 四、数据存储

### 4.1 存储位置

```
logs/
└── backtest_history/
    ├── records.json          # 回测记录
    └── report_YYYYMMDD_HHMMSS.csv  # 导出的报告
```

### 4.2 记录格式

```json
{
  "record_id": "20260226_232530",
  "timestamp": "2026-02-26 23:25:30",
  "strategy": "dual_ma",
  "ts_code": "000001.SZ",
  "start_date": "20250101",
  "end_date": "20251231",
  "total_return": 0.1523,
  "annual_return": 0.1523,
  "sharpe_ratio": 1.25,
  "max_drawdown": -0.0856,
  "win_rate": 0.58,
  "total_trades": 12,
  "initial_cash": 100000.0,
  "commission_rate": 0.0003,
  "slippage_rate": 0.001,
  "notes": "CLI 回测"
}
```

---

## 五、命令速查

| 命令 | 功能 |
|------|------|
| `history` | 查看最近回测记录 |
| `history --limit 50` | 查看最近 50 条记录 |
| `history --strategy dual_ma` | 查看特定策略记录 |
| `history --stats` | 查看策略统计 |
| `history --export` | 导出 CSV 报告 |
| `strategy list` | 查看策略状态 |
| `strategy enable --name <名称>` | 激活单个策略 |
| `strategy disable --name <名称> --reason <原因>` | 停用单个策略 |
| `strategy enable-batch --names <名称列表>` | 批量激活策略 |
| `strategy disable-batch --names <名称列表> --reason <原因>` | 批量停用策略 |

---

## 六、最佳实践

### 6.1 定期清理

```bash
# 每月清理一次 90 天前的记录
python -c "from quant_strategy.analyzer import BacktestHistory; h = BacktestHistory(); h.clear(older_than_days=90)"
```

### 6.2 策略分组管理

建议按策略类型分组管理：

```bash
# 趋势策略组
python -m quant_strategy.cli strategy disable-batch \
    --names dual_ma macd dmi \
    --reason "趋势策略表现不佳"

# 短线策略组
python -m quant_strategy.cli strategy enable-batch \
    --names kdj rsi cci
```

### 6.3 添加备注

回测时添加备注便于后续分析：

```python
# 在代码中使用
from quant_strategy.analyzer import BacktestHistory

history = BacktestHistory()
history.add_record(
    result=result,
    strategy="dual_ma",
    ts_code="000001.SZ",
    start_date="20250101",
    end_date="20251231",
    notes="参数优化后回测"
)
```

---

## 七、常见问题

### Q1: 历史记录保存在哪里？

**A:** `./logs/backtest_history/records.json`

### Q2: 如何修改已保存的记录？

**A:** 直接编辑 `records.json` 文件（不建议），或通过 Python API 修改。

### Q3: 批量操作失败怎么办？

**A:** 检查策略名称是否正确，使用 `strategy list` 查看可用策略。

### Q4: 回测记录太多怎么办？

**A:** 使用 `--export` 导出后清理，或定期运行清理命令。

### Q5: 如何备份历史记录？

**A:** 复制 `logs/backtest_history/` 目录到安全位置。
