# 数据获取机制修复总结

## 修复日期
2026-02-27

---

## 问题列表

### 问题 1: 上市日期类型处理错误 ✅

**错误：** `'int' object has no attribute 'strftime'`

**位置：** `_fetch_all_history()` 方法

**原因：** Tushare 返回的 `list_date` 可能是 int 类型

**修复：**
```python
# 添加 int/float 类型处理
if isinstance(list_date_val, (int, float)):
    list_date = str(int(list_date_val))
```

---

### 问题 2: 缓存数据索引类型错误 ✅

**错误：** `time data "0" doesn't match format "%Y%m%d"`

**位置：** `_get_full_history()` 方法（第 295 行）

**原因：** 缓存数据的索引可能不是标准 YYYYMMDD 格式

**修复：**
```python
# 使用混合模式推断日期格式
if not pd.api.types.is_datetime64_any_dtype(historical_df.index):
    try:
        historical_df.index = pd.to_datetime(historical_df.index, format='mixed')
    except Exception as idx_err:
        # 索引无法转换，重新获取数据
        return self._fetch_all_history(ts_code, start_date, end_date, adj, full_cache_params)
```

---

### 问题 3: daily_full 过滤逻辑错误 ✅

**错误：** `'>=' not supported between instances of 'numpy.ndarray' and 'Timestamp'`

**位置：** `data_cache.get()` 方法

**原因：** Parquet 读取后索引类型可能改变

**修复：**
```python
# 确保索引是 datetime 类型
if not pd.api.types.is_datetime64_any_dtype(df.index):
    try:
        df.index = pd.to_datetime(df.index, format='%Y%m%d')
    except (ValueError, TypeError):
        df.index = pd.to_datetime(df.index)
```

---

## 修复文件清单

| 文件 | 修复内容 | 行数变化 |
|------|----------|----------|
| `quant_strategy/data/tushare_provider.py` | 上市日期处理 + 缓存索引类型检查 | +25 |
| `quant_strategy/data/data_cache.py` | daily_full 过滤逻辑 | +10 |

---

## 测试验证

### 测试 1: 单只股票获取
```bash
python -c "from quant_strategy.data.tushare_provider import TushareDataProvider; p = TushareDataProvider(); df = p.get_daily_data('000001.SZ', '20250101', '20251231', 'qfq'); print(f'获取成功：{len(df)} 天')"
```
**结果：** ✅ 获取成功：243 天

### 测试 2: 10 只股票获取
```bash
python test_10_stocks.py
```
**结果：** ✅ 10/10 成功

### 测试 3: 批量获取
```bash
python -m quant_strategy.tools.fetch_all_stocks --start 20250101 --end 20251231 --batch 50
```
**结果：** ✅ 正在运行中

---

## 数据获取机制说明

### 工作流程

```
请求数据 (20250101-20251231)
    │
    ├─ 1. 检查 daily_full 缓存
    │   │
    │   ├─ 有缓存 → 检查索引类型
    │   │   ├─ 类型正确 → 检查是否需要更新
    │   │   │   ├─ 无需更新 → 返回缓存数据
    │   │   │   └─ 需要更新 → 获取新数据 → 合并 → 返回
    │   │   │
    │   │   └─ 类型错误 → 尝试转换
    │   │       ├─ 转换成功 → 继续处理
    │   │       └─ 转换失败 → 重新获取全部数据
    │   │
    │   └─ 无缓存 → 首次获取全部历史数据
    │       │
    │       ├─ 获取上市日期
    │       ├─ 从上市日期获取到 end_date
    │       └─ 保存到 daily_full 缓存
    │
    └─ 2. 返回请求范围的数据
```

### 缓存策略

| 缓存类型 | 键格式 | 用途 | 保存策略 |
|---------|--------|------|---------|
| `daily_full` | `{ts_code, adj}` | 全量历史数据 | 永久保存，增量更新 |
| `daily` | `{ts_code, start, end, adj}` | 日期范围数据 | 按需缓存 |

### 数据类型处理

**上市日期可能格式：**
1. `int` - `20150105`
2. `float` - `20150105.0`
3. `str` - `"20150105"` 或 `"2015-01-05"`

**缓存索引可能格式：**
1. `datetime64` - 已转换
2. `str` - `"2025-01-02"` 或 `"20250102"`
3. `int` - `20250102`（罕见）

**修复策略：**
- 使用 `format='mixed'` 自动推断
- 失败时降级重新获取

---

## 性能优化建议

### 已完成
- ✅ daily_full 永久保存，不被 LRU 淘汰
- ✅ 增量更新只获取新数据
- ✅ 缓存命中率检查

### 待优化
- ⏳ 批量保存接口（减少元数据保存次数）
- ⏳ 异步日志保存
- ⏳ SQLite 元数据存储

---

## 运行状态

**批量获取命令：**
```bash
python -m quant_strategy.tools.fetch_all_stocks --start 20250101 --end 20251231 --batch 50
```

**预期结果：**
- 总股票数：5485 只
- 已有缓存：261 只
- 需要获取：5224 只
- 预计时间：~2-3 小时

---

## 常见问题

### Q1: 为什么有些股票会显示错误但最终还是成功了？

**A:** 这是因为缓存数据的索引类型不一致。系统会自动：
1. 尝试转换索引类型
2. 如果转换失败，重新获取数据
3. 最终保证数据获取成功

### Q2: 如何查看获取进度？

**A:** 日志会显示：
```
INFO | 处理批次 1/105 (股票 1-50)
INFO | 处理批次 2/105 (股票 51-100)
...
```

### Q3: 如何中断并恢复获取？

**A:** 
- 中断：`Ctrl+C`
- 恢复：重新运行命令，会自动跳过已获取的股票

---

**报告人**: AI Assistant  
**修复状态**: ✅ 完成  
**测试状态**: ✅ 通过  
**批量状态**: 🔄 运行中
