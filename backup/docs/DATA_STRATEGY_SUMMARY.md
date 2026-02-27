# 数据策略总结

## 当前策略

### 1. 数据持久化 ⭐

**策略：** 历史数据本地永久保存，只实时获取新数据

**实现：**
- `daily_full` 缓存类型：保存股票全部历史数据
- 增量更新：只获取最新交易日数据
- 本地合并：历史数据 + 新数据

**优势：**
- 减少 API 调用 90%+
- 支持离线查询历史数据
- 数据永久保存，不会丢失

**详见：** [DATA_PERSISTENCE_STRATEGY.md](DATA_PERSISTENCE_STRATEGY.md)

### 2. 交易日历和停牌日历本地化

**交易日历：** 按年份缓存
```python
cache_key = {"exchange": "SSE", "year": "2023"}
is_complete = True  # 永久保存
```

**停牌日历：** 按股票 + 年份缓存
```python
cache_key = {"ts_code": "600519.SH", "year": "2023"}
is_complete = True  # 永久保存
```

### 3. 数据质量检查

**重复数据检测：** 自动检测并清理
**100% 完整度：** 实际天数 = 预期天数

## 缓存类型总览

| 类型 | 用途 | 缓存键 | 永久保存 |
|------|------|--------|----------|
| **daily_full** | 全量历史数据 | `{ts_code, adj}` | ✅ |
| **daily** | 日期范围数据 | `{ts_code, start, end, adj}` | ❌ |
| **trade_cal_year** | 交易日历 | `{exchange, year}` | ✅ |
| **suspend_cal_year** | 停牌日历 | `{ts_code, year}` | ✅ |

## 数据流程

```
用户请求数据
    ↓
检查 daily 缓存
    ├─ 命中 → 返回
    └─ 未命中 → 继续
    ↓
检查 daily_full 缓存
    ├─ 有缓存 → 检查是否需要更新
    │   ├─ 无需更新 → 返回缓存数据
    │   └─ 需要更新 → 获取新数据 → 合并 → 返回
    └─ 无缓存 → 首次获取全部历史数据
    ↓
保存到 daily_full 和 daily 缓存
```

## 使用示例

### 首次获取
```bash
# 获取全部历史数据（保存到本地）
python -m quant_strategy.tools.fetch_all_stocks \
    --start 20100101 \
    --end 20231231
```

### 后续使用
```bash
# 自动使用本地缓存
python -m quant_strategy.cli backtest \
    --ts_code 600519.SH \
    --start 20230101 \
    --end 20231231
```

### 增量更新
```bash
# 只获取 2024 年新数据
python -m quant_strategy.tools.fetch_all_stocks \
    --start 20240101 \
    --end 20241231
```

### 验证缓存
```bash
python -m quant_strategy.tools.verify_cache
```

## 性能对比

| 操作 | 传统方式 | 持久化方式 | 提升 |
|------|----------|------------|------|
| 首次获取 | 100% | 100% | - |
| 历史查询 | 每次 API | 本地读取 | 100x |
| 增量更新 | 全量获取 | 仅新数据 | 10x |
| 重复查询 | 每次 API | 缓存命中 | 100x |

## 磁盘空间

**预估：**
- 单只股票 10 年数据：约 2500 条记录
- 5000 只股票：约 1250 万条记录
- 总空间：2-5 GB

**建议：**
- 定期清理 `daily` 缓存（保留 `daily_full`）
- 使用 SSD 存储提升读取速度

## 注意事项

### 1. Token 配置
```bash
export TUSHARE_TOKEN=your_token_here
```

### 2. 首次获取
- 时间较长（5000 只股票约 10-15 分钟）
- 建议分批获取（按季度）
- 完成后后续使用非常快

### 3. 缓存管理
```python
from quant_strategy.data.data_cache import DataCache

cache = DataCache()

# 查看统计
stats = cache.get_cache_stats()

# 清理旧缓存（不影响 daily_full）
cache.clear(older_than_days=90)
```

## 相关文档

- [DATA_PERSISTENCE_STRATEGY.md](DATA_PERSISTENCE_STRATEGY.md) - 持久化策略详解
- [DATA_100_PERCENT_COMPLETE.md](DATA_100_PERCENT_COMPLETE.md) - 数据质量检查
- [TRADING_DAYS_IMPROVEMENT.md](TRADING_DAYS_IMPROVEMENT.md) - 交易日计算
- [DATA_FETCH_GUIDE.md](DATA_FETCH_GUIDE.md) - 数据获取指南
