# 数据持久化策略

## 核心策略

**历史数据本地持久化，只实时获取新数据**

### 数据流程

```
请求数据 (start_date 到 end_date)
    ↓
1. 检查日期范围缓存
   └─ 命中 → 直接返回
   └─ 未命中 → 继续
    ↓
2. 获取全量历史数据 (daily_full)
   ├─ 有缓存 → 检查是否需要更新
   │   ├─ 无需更新 → 返回缓存数据
   │   └─ 需要更新 → 获取新数据，合并后返回
   └─ 无缓存 → 首次获取全部历史数据
    ↓
3. 保存到本地缓存
   ├─ daily_full: 全量历史数据（永久保存）
   └─ daily: 日期范围数据（按需缓存）
```

## 缓存类型

### 1. daily_full（全量历史数据）

**用途：** 永久保存股票的全部历史数据

**缓存键：**
```python
{"ts_code": "600519.SH", "adj": "qfq"}
```

**特点：**
- 不按日期范围区分
- 标记为 `is_complete=True`
- 增量更新：只获取新数据
- 永久保存，不清理

**示例：**
```
首次获取：600519.SH (2010-2023 年全部数据)
  → 保存到 daily_full
  → 2024 年再次请求
  → 只获取 2024 年新数据
  → 合并后更新 daily_full
```

### 2. daily（日期范围数据）

**用途：** 按请求日期范围缓存

**缓存键：**
```python
{"ts_code": "600519.SH", "start": "20230101", "end": "20231231", "adj": "qfq"}
```

**特点：**
- 按日期范围区分
- 可能标记为完整或不完整
- 用于快速响应相同范围的请求

### 3. trade_cal_year（交易日历）

**用途：** 按年份缓存交易日历

**缓存键：**
```python
{"exchange": "SSE", "year": "2023"}
```

**特点：**
- 交易日历固定不变
- 标记为 `is_complete=True`
- 永久保存

### 4. suspend_cal_year（停牌日历）

**用途：** 按股票 + 年份缓存停牌日期

**缓存键：**
```python
{"ts_code": "600519.SH", "year": "2023"}
```

**特点：**
- 历史停牌数据不变
- 标记为 `is_complete=True`
- 永久保存

## 实现细节

### 首次获取数据

```python
# 请求：2023 年全年数据
get_daily_data("600519.SH", "20230101", "20231231")

# 流程：
# 1. 检查 daily 缓存 → 未命中
# 2. 检查 daily_full 缓存 → 未命中
# 3. 获取全部历史数据（从上市到 2023-12-31）
# 4. 保存到 daily_full
# 5. 返回 2023 年数据
```

### 增量更新

```python
# 请求：2024 年数据（已有 2023 年及之前的缓存）
get_daily_data("600519.SH", "20240101", "20240227")

# 流程：
# 1. 检查 daily 缓存 → 未命中
# 2. 检查 daily_full 缓存 → 命中（最后日期 2023-12-31）
# 3. 检测需要更新：2024-01-01 到 2024-02-27
# 4. 只获取新数据（2024 年）
# 5. 合并到 daily_full
# 6. 返回 2024 年数据
```

### 重复使用缓存

```python
# 第一次请求
get_daily_data("600519.SH", "20230101", "20231231")
# → 从 daily_full 读取，返回 2023 年数据

# 第二次请求（相同范围）
get_daily_data("600519.SH", "20230101", "20231231")
# → daily 缓存命中，直接返回
```

## 代码实现

### 主方法

```python
def get_daily_data(self, ts_code, start_date, end_date, adj):
    # 1. 尝试从缓存获取
    cached = self.cache.get("daily", params, start_date, end_date)
    if cached:
        return cached
    
    # 2. 获取全量历史数据
    df = self._get_full_history(ts_code, start_date, end_date, adj)
    if df:
        return df
    
    # 3. 降级：直接获取请求范围
    return self._fetch_daily_range(ts_code, start_date, end_date, adj, params)
```

### 全量历史数据获取

```python
def _get_full_history(self, ts_code, start_date, end_date, adj):
    full_params = {"ts_code": ts_code, "adj": adj}
    
    # 1. 从缓存加载历史数据
    historical_df = self.cache.get("daily_full", full_params)
    
    if historical_df:
        # 2. 检查是否需要更新
        last_date = historical_df.index.max()
        if last_date >= end_date:
            # 无需更新
            return historical_df[start_date:end_date]
        
        # 3. 获取新数据
        new_start = (last_date + 1 day).strftime('%Y%m%d')
        new_df = self._fetch_daily_range(ts_code, new_start, end_date, adj)
        
        # 4. 合并并保存
        combined = pd.concat([historical_df, new_df])
        combined = combined[~combined.index.duplicated(keep='first')]
        self.cache.set("daily_full", full_params, combined, is_complete=True)
        
        return combined[start_date:end_date]
    
    else:
        # 5. 首次获取全部历史
        return self._fetch_all_history(ts_code, start_date, end_date, adj, full_params)
```

### 缓存支持 daily_full 过滤

```python
def get(self, data_type, params, start_date, end_date):
    if is_complete:
        df = pd.read_parquet(cache_path)
        
        # daily_full 类型需要按日期过滤
        if data_type == "daily_full" and start_date and end_date:
            mask = (df.index >= start_date) & (df.index <= end_date)
            return df[mask]
        
        return df
```

## 优势

### 1. 减少 API 调用

| 场景 | 传统方式 | 持久化方式 |
|------|----------|------------|
| 首次获取 | 1 次 | 1 次 |
| 相同范围再次请求 | 1 次 | 0 次（缓存） |
| 增量更新 | 1 次（全量） | 1 次（仅新增） |
| 历史数据查询 | 每次都调用 | 0 次（本地） |

### 2. 数据永久保存

- 所有获取的数据都保存到本地
- 不会因为缓存清理而丢失
- `daily_full` 类型永久保留

### 3. 增量更新高效

```
传统方式：
  每次获取 2024 年数据 → 重新获取 2010-2024 全部数据

持久化方式：
  首次：获取 2010-2023
  更新：只获取 2024 年新数据
  合并：本地完成
```

### 4. 支持离线使用

- 历史数据都在本地
- 断网也能查询历史数据
- 只需联网获取最新数据

## 使用示例

### 批量获取历史数据

```bash
# 首次获取（会保存全部历史数据）
python -m quant_strategy.tools.fetch_all_stocks --start 20100101 --end 20231231

# 后续使用（自动使用本地缓存）
python -m quant_strategy.cli backtest \
    --ts_code 600519.SH \
    --start 20230101 \
    --end 20231231
```

### 查看缓存状态

```bash
python -m quant_strategy.tools.verify_cache
```

输出示例：
```
缓存统计:
  文件数：5000
  大小：2.5 GB
  股票数：5000

======================================================================
数据完整性统计 (100% 要求):
======================================================================
[OK] 完整数据：4800 只 (96.0%)
[WARN] 部分数据：200 只 (4.0%)
```

### 缓存管理

```python
from quant_strategy.data.data_cache import DataCache

cache = DataCache()

# 查看缓存统计
stats = cache.get_cache_stats()
print(f"总大小：{stats['total_size_mb']:.2f} MB")
print(f"股票数：{stats['stock_count']}")

# 清理旧缓存（不影响 daily_full）
cache.clear(older_than_days=90)
```

## 注意事项

### 1. 磁盘空间

- 全量历史数据会占用较多空间
- 5000 只股票 × 10 年 × 250 天/年 ≈ 1250 万条记录
- 预计占用 2-5 GB 空间

### 2. 首次获取时间

- 首次获取全部历史数据需要较长时间
- 建议分批获取（按季度或年份）
- 获取完成后后续使用非常快

### 3. 数据更新

- 每日收盘后自动获取新数据
- 只需获取最新交易日的数据
- 合并过程在本地完成

### 4. 缓存迁移

```python
# 备份缓存目录
cp -r data_cache /backup/location

# 恢复缓存
# 设置 cache_dir 参数
cache = DataCache(cache_dir="/backup/location")
```

## 文件变更

### 修改的文件
- `quant_strategy/data/tushare_provider.py`
  - 新增 `get_daily_data()` - 持久化策略主入口
  - 新增 `_get_full_history()` - 获取全量历史数据
  - 新增 `_fetch_all_history()` - 首次获取全部历史
  - 新增 `_fetch_daily_range()` - 获取日期范围数据

- `quant_strategy/data/data_cache.py`
  - 修改 `get()` - 支持 daily_full 类型过滤

### 新增的文件
- `DATA_PERSISTENCE_STRATEGY.md` - 本说明文档
