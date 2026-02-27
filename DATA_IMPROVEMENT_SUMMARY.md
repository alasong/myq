# 数据完整性判断改进总结

## 核心改进

### 从"估算"到"精确计算"

**改进前：**
```python
# 简单估算：每年 250 个交易日
expected_days = int(((end_dt - start_dt).days * 250 / 365) * 0.95)
```

**改进后：**
```python
# 精确计算：实际交易日 - 停牌日
expected_days = (交易所交易日历天数 - 股票停牌天数) × 0.95
```

## 实现细节

### 1. 交易日历（已实现）

使用 Tushare `trade_cal` 接口获取实际交易日：
- 去掉周末
- 去掉法定节假日
- 包含调休工作日

```python
def get_trade_cal(self, exchange: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取交易日历（带缓存）"""
    # 缓存命中 → 直接返回
    # 缓存未命中 → 调用 API → 缓存
```

### 2. 停牌日历（已实现，降级处理）

使用 Tushare `suspend_cal` 接口获取停牌日期：
- 需要特定积分权限
- 无法获取时自动降级为只使用交易日历

```python
try:
    suspend_df = self.pro.suspend_cal(ts_code=ts_code, ...)
    suspend_days = len(suspend_df)
except:
    suspend_days = 0  # 降级处理
```

### 3. 完整性判断流程

```
获取数据请求
    ↓
检查缓存标记 is_complete
    ├─ True → 直接返回（跳过验证）
    └─ False → 继续检查
        ↓
计算预期交易日（交易日历 - 停牌日）
        ↓
检查实际记录数
        ├─ ≥ 95% → 标记为完整，返回数据
        ├─ 90-95% → 标记为完整，返回数据
        └─ < 90% → 返回 None，触发重新获取
```

## 受益场景

### 1. 长期停牌股票
- **改进前**：误判为不完整，重复获取
- **改进后**：正确判断为完整

### 2. 节假日期间
- **改进前**：按固定比例估算，可能偏多
- **改进后**：按实际交易日，精确匹配

### 3. 跨年度数据
- **改进前**：不同年份节假日不同，估算不准
- **改进后**：每年独立计算交易日历

## 性能优化

### 缓存策略

| 数据类型 | 缓存 | TTL | 说明 |
|----------|------|-----|------|
| 交易日历 | ✅ | 30 天 | 减少 API 调用 |
| 日线数据 | ✅ | 30 天 | 完整数据永久有效 |
| 停牌数据 | ❌ | - | 调用频率低 |

### 减少重复获取

```bash
# 第一次：获取并标记完整
python -m quant_strategy.tools.fetch_all_stocks --start 20230101 --end 20231231

# 第二次：自动跳过已完整的股票
python -m quant_strategy.tools.fetch_all_stocks --start 20230101 --end 20231231
# 输出：[OK] 完整数据：4500 只（跳过）
#       需要获取：50 只
```

## 使用示例

### 检查缓存状态

```bash
python -m quant_strategy.tools.verify_cache
```

输出：
```
缓存统计:
  文件数：4523
  大小：358.42 MB
  股票数：4523

============================================================
数据完整性统计:
============================================================
[OK] 完整数据：4200 只 (92.9%)
[WARN] 部分数据：323 只 (7.1%)
```

### 增量更新

```bash
# 只更新未完整的股票
python -m quant_strategy.tools.fetch_all_stocks --start 20230101 --end 20231231

# 强制重新获取（忽略完整性标记）
python -m quant_strategy.tools.fetch_all_stocks --start 20230101 --end 20231231 --force
```

## 注意事项

### 1. Tushare 积分要求

| 接口 | 权限 | 说明 |
|------|------|------|
| trade_cal | 基础权限 | 注册即可用 |
| suspend_cal | 需要积分 | 无法获取时自动降级 |
| daily | 基础权限 | 日线数据 |

### 2. 新股处理

新股由于上市时间短，会被正确判断为"不完整"：
- 这不是 bug，是正常行为
- 等待上市时间足够长后会自动标记为完整

### 3. 缓存清理

定期清理过期缓存：
```python
from quant_strategy.data.data_cache import DataCache
cache = DataCache()
cache.clear(older_than_days=90)  # 清理 90 天前的缓存
```

## 文件变更

### 修改的文件
- `quant_strategy/data/tushare_provider.py`
  - 新增 `_get_exchange()` 方法
  - 新增 `_calc_expected_trading_days()` 方法
  - 修改 `get_daily_data()` 使用新的计算方法

- `quant_strategy/data/data_cache.py`
  - 已有完整性检查逻辑，无需修改

- `quant_strategy/tools/fetch_all_stocks.py`
  - 更新 `check_cache_completeness()` 支持自定义预期天数

### 新增的文件
- `TRADING_DAYS_IMPROVEMENT.md` - 详细说明文档
- `DATA_IMPROVEMENT_SUMMARY.md` - 本文件

## 下一步优化建议

1. **批量获取交易日历**：一次性获取全市场交易日历，减少 API 调用
2. **新股自动识别**：根据上市日期自动调整预期天数
3. **完整性报告**：生成数据完整性报告，列出所有不完整股票及原因
