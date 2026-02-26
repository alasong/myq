# 策略管理功能使用说明

## 功能概述

策略管理功能支持对量化策略进行激活/停用管理，并可以对激活的策略进行批量回测。

## 命令列表

### 1. 查看策略状态

```bash
# 查看所有策略状态
python -m quant_strategy.cli strategy list

# 或简写
python -m quant_strategy.cli strategy
```

输出示例：
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
...
======================================================================
总计：12 个策略，激活：10 个，停用：2 个
======================================================================
```

### 2. 停用策略

当某个策略表现不佳时，可以将其停用：

```bash
python -m quant_strategy.cli strategy disable --name <策略名称> --reason "<停用原因>"
```

示例：
```bash
# 停用双均线策略
python -m quant_strategy.cli strategy disable --name dual_ma --reason "收益率太差"

# 停用 KDJ 策略
python -m quant_strategy.cli strategy disable --name kdj --reason "波动过大"
```

### 3. 激活策略

当需要重新启用某个策略时：

```bash
python -m quant_strategy.cli strategy enable --name <策略名称>
```

示例：
```bash
# 重新启用双均线策略
python -m quant_strategy.cli strategy enable --name dual_ma
```

### 4. 批量回测激活的策略

对所有已激活的策略进行批量回测：

```bash
python -m quant_strategy.cli batch-backtest \
    --ts_code <股票代码> \
    --start_date <开始日期> \
    --end_date <结束日期> \
    --workers <并发数> \
    --show-details
```

参数说明：
- `--ts_code`: 股票代码（必需）
- `--start_date`: 开始日期，格式 YYYYMMDD（可选，默认 20200101）
- `--end_date`: 结束日期，格式 YYYYMMDD（可选，默认 20231231）
- `--workers`: 并发工作线程数（可选，默认 4）
- `--show-details`: 是否导出详细结果到 CSV 文件（可选）

示例：
```bash
# 回测 300001.SZ 在 2025 年的表现
python -m quant_strategy.cli batch-backtest \
    --ts_code 300001.SZ \
    --start_date 20250101 \
    --end_date 20251231 \
    --workers 4
```

输出示例：
```
================================================================================
批量回测结果汇总
股票代码：300001.SZ
日期范围：20250101 - 20251231
================================================================================
  ts_code         strategy  total_return  sharpe_ratio  max_drawdown
300001.SZ              cci      0.456984      1.963917     -0.055136
300001.SZ             boll      0.163936      1.423923     -0.054641
300001.SZ       fear_greed      0.125796      1.002946     -0.054884
...

--------------------------------------------------------------------------------
统计摘要:
  策略数量：10
  平均收益率：-1.65%
  平均夏普比率：0.06
  平均最大回撤：-15.27%
  最佳策略：cci (45.70%)
  最差策略：dual_ma (-33.31%)
================================================================================
```

## 可用策略列表

| 策略名称 | 策略类型 | 说明 |
|---------|---------|------|
| dual_ma | 经典策略 | 双均线交叉策略 |
| momentum | 经典策略 | 动量策略 |
| kdj | 短线策略 | KDJ 指标策略 |
| rsi | 短线策略 | RSI 指标策略 |
| boll | 短线策略 | 布林带策略 |
| dmi | 短线策略 | DMI 趋势策略 |
| cci | 短线策略 | CCI 顺势策略 |
| macd | 短线策略 | MACD 策略 |
| volume_price | 量价策略 | 成交量价格配合策略 |
| volume_sentiment | 情绪策略 | 成交量情绪策略 |
| fear_greed | 情绪策略 | 恐惧贪婪指数策略 |
| open_interest | 情绪策略 | 开盘情绪策略 |

## 配置文件

策略状态配置保存在 `~/.qwen/strategy_config.json`，格式如下：

```json
{
  "strategies": {
    "dual_ma": {
      "enabled": false,
      "disabled_reason": "收益率太差",
      "disabled_at": "2026-02-26 19:08:24",
      "notes": ""
    },
    "cci": {
      "enabled": true,
      "disabled_reason": "",
      "disabled_at": null,
      "notes": ""
    }
  },
  "last_updated": "2026-02-26 19:08:24"
}
```

## 使用建议

1. **定期回测评估**: 使用 `batch-backtest` 定期对所有激活策略进行回测，评估策略表现

2. **及时停用表现差的策略**: 根据回测结果，使用 `strategy disable` 停用表现不佳的策略

3. **保留策略配置**: 策略状态配置会自动保存，下次运行时会自动加载

4. **多股票测试**: 对多只股票进行批量回测，验证策略的普适性

5. **导出详细结果**: 使用 `--show-details` 参数将回测结果导出为 CSV 文件，便于后续分析

## 示例工作流

```bash
# 1. 查看所有策略状态
python -m quant_strategy.cli strategy list

# 2. 停用表现差的策略
python -m quant_strategy.cli strategy disable --name dual_ma --reason "连续亏损"
python -m quant_strategy.cli strategy disable --name kdj --reason "波动过大"

# 3. 对剩余激活策略进行批量回测
python -m quant_strategy.cli batch-backtest \
    --ts_code 300001.SZ \
    --start_date 20250101 \
    --end_date 20251231 \
    --show-details

# 4. 根据回测结果，重新激活有潜力的策略
python -m quant_strategy.cli strategy enable --name cci

# 5. 再次回测验证
python -m quant_strategy.cli batch-backtest \
    --ts_code 300002.SZ \
    --start_date 20250101 \
    --end_date 20251231
```
