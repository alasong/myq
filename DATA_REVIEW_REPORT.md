# 数据获取和保存机制审查报告

## 审查日期
2026-02-27

## 审查范围
- 数据获取机制 (`tushare_provider.py`)
- 数据本地保存机制 (`data_cache.py`)
- 数据使用流程

---

## 一、数据获取机制审查

### 1.1 当前架构

```
get_daily_data(ts_code, start_date, end_date, adj)
    │
    ├─ 1. 检查 daily 缓存（日期范围）
    │   └─ 命中 → 直接返回
    │
    ├─ 2. 调用 _get_full_history()
    │   │
    │   ├─ 2a. 检查 daily_full 缓存（全量历史）
    │   │   ├─ 有缓存且无需更新 → 返回缓存数据
    │   │   ├─ 有缓存但需更新 → 获取新数据 → 合并 → 返回
    │   │   └─ 无缓存 → 调用 _fetch_all_history()
    │   │
    │   └─ 失败 → 降级
    │
    └─ 3. 调用 _fetch_daily_range()（直接获取请求范围）
```

### 1.2 优点 ✅

1. **持久化策略正确**
   - 历史数据保存到 `daily_full`
   - 增量更新只获取新数据
   - 减少重复 API 调用

2. **降级机制完善**
   - `daily_full` 失败 → `_fetch_daily_range()`
   - 保证数据获取成功率

3. **复权处理正确**
   - 获取复权因子
   - 应用复权到 OHLCV 数据

### 1.3 发现的问题 ❌

#### 问题 1: `_fetch_all_history` 获取逻辑不正确

**当前代码：**
```python
def _fetch_all_history(self, ts_code, start_date, end_date, adj, cache_params):
    # 问题：只获取了 start_date 到 end_date 的数据
    # 而不是"全部历史数据"
    df = self.pro.daily(
        ts_code=ts_code,
        start_date=start_date,  # ← 这是请求的开始日期，不是上市日期
        end_date=end_date
    )
```

**问题：**
- 方法名是"获取全部历史"，但实际只获取请求范围
- 应该从上市日期开始获取，而不是从 `start_date` 开始
- 导致 `daily_full` 缓存的不是真正的全量数据

**修复建议：**
```python
def _fetch_all_history(self, ts_code, start_date, end_date, adj, cache_params):
    # 1. 获取股票基本信息（包含上市日期）
    stock_info = self.pro.stock_basic(ts_code=ts_code)
    list_date = stock_info['list_date'].iloc[0]  # 上市日期
    
    # 2. 从上市日期开始获取全部数据
    df = self.pro.daily(
        ts_code=ts_code,
        start_date=list_date,  # ← 从上市日期开始
        end_date=end_date
    )
```

#### 问题 2: 增量更新逻辑存在数据丢失风险

**当前代码：**
```python
# _get_full_history()
last_date = historical_df.index.max().strftime('%Y%m%d')
new_start = (last_date + 1 day).strftime('%Y%m%d')
new_df = self._fetch_daily_range(ts_code, new_start, end_date, adj, ...)
```

**问题：**
1. **假设数据连续**：如果 `historical_df` 中间有缺失，不会补全
2. **停牌处理**：停牌股票 `last_date` 可能早于实际交易日期
3. **边界问题**：`last_date + 1 day` 可能不是交易日

**修复建议：**
```python
# 检查是否有数据缺口
expected_days = self._calc_expected_trading_days(ts_code, start_date, end_date)
actual_days = len(historical_df)

if actual_days < expected_days:
    # 数据不完整，需要获取缺失的数据
    missing_dates = get_missing_dates(historical_df, start_date, end_date)
    # 获取缺失数据并合并
```

#### 问题 3: 缓存键设计不一致

**当前设计：**
```python
# daily_full 缓存键
{"ts_code": ts_code, "adj": adj}

# daily 缓存键
{"ts_code": ts_code, "start": start_date, "end": end_date, "adj": adj}
```

**问题：**
- `daily_full` 没有区分复权类型可能导致混淆
- 同一股票不同复权类型会覆盖

**修复建议：**
保持当前设计（已包含 `adj`），但需要确保：
- `daily_full` 和 `daily` 的 `adj` 参数一致
- 文档说明缓存键设计

### 1.4 建议的新增功能

#### 建议 1: 添加数据完整性验证

```python
def _validate_data(self, df, ts_code, start_date, end_date):
    """验证数据完整性"""
    # 1. 检查日期连续性
    expected_dates = self._get_trade_dates(start_date, end_date)
    actual_dates = df.index.tolist()
    
    missing_dates = set(expected_dates) - set(actual_dates)
    if missing_dates:
        logger.warning(f"{ts_code}: 缺失 {len(missing_dates)} 个交易日")
    
    # 2. 检查数据质量
    if (df['close'] == 0).any():
        logger.warning(f"{ts_code}: 存在零价格")
    
    return len(missing_dates) == 0
```

#### 建议 2: 添加批量获取接口

```python
def get_multiple_stocks_daily(self, ts_codes, start_date, end_date, adj):
    """批量获取多只股票数据"""
    results = {}
    for ts_code in tqdm(ts_codes):
        results[ts_code] = self.get_daily_data(ts_code, start_date, end_date, adj)
    return results
```

---

## 二、数据本地保存机制审查

### 2.1 当前架构

```
DataCache
├── 缓存类型
│   ├── daily_full (全量历史数据)
│   ├── daily (日期范围数据)
│   ├── trade_cal_year (交易日历)
│   └── suspend_cal_year (停牌日历)
│
├── 缓存策略
│   ├── TTL 过期检查 (30 天)
│   ├── LRU 淘汰 (max_size_mb=1024MB)
│   └── 完整性标记 (is_complete)
│
└── 存储格式
    └── Parquet (按 key_timestamp.parquet)
```

### 2.2 优点 ✅

1. **缓存类型设计合理**
   - `daily_full` 永久保存
   - `daily` 按需缓存
   - 元数据记录完整

2. **完整性检查机制**
   - `is_complete` 标记
   - 100% 完整度要求
   - 重复数据检测

3. **LRU 淘汰策略**
   - 限制缓存大小
   - 淘汰旧数据保留新数据

### 2.3 发现的问题 ❌

#### 问题 1: `daily_full` 类型可能被 LRU 淘汰

**当前代码：**
```python
def _enforce_size_limit(self):
    # LRU 淘汰，不区分缓存类型
    for key in keys_to_remove:
        # daily_full 也可能被淘汰
        self._delete_cache_entry(key)
```

**问题：**
- `daily_full` 应该永久保存，不应被淘汰
- 当前实现可能导致历史数据丢失

**修复建议：**
```python
def _enforce_size_limit(self):
    # 获取所有缓存条目
    for key in keys_to_remove:
        # 跳过 daily_full 类型
        cache_entry = self._metadata[self._metadata["key"] == key]
        if not cache_entry.empty:
            data_type = cache_entry.iloc[0].get("data_type", "")
            if data_type == "daily_full":
                continue  # 跳过永久缓存
        
        # 淘汰其他类型
        self._delete_cache_entry(key)
```

#### 问题 2: 缓存键生成可能导致冲突

**当前代码：**
```python
def _generate_key(self, data_type, params):
    param_str = "_".join(f"{k}={v}" for k, v in sorted(params.items()))
    return f"{data_type}_{param_str}"
```

**问题：**
- 如果 `params` 包含特殊字符可能出错
- 没有长度限制，可能超过文件系统限制

**修复建议：**
```python
def _generate_key(self, data_type, params):
    param_str = "_".join(f"{k}={v}" for k, v in sorted(params.items()))
    # 限制长度，使用哈希
    if len(param_str) > 100:
        import hashlib
        param_str = hashlib.md5(param_str.encode()).hexdigest()
    return f"{data_type}_{param_str}"
```

#### 问题 3: 元数据管理不够健壮

**当前代码：**
```python
def set(self, data_type, params, df, is_complete=False):
    # 每次保存都创建新的元数据条目
    new_entry = pd.DataFrame([{...}])
    self._metadata = pd.concat([self._metadata, new_entry])
```

**问题：**
- 同一 `key` 可能有多条记录（不同时间戳）
- 清理旧记录逻辑复杂
- 元数据文件可能变得很大

**修复建议：**
```python
def set(self, data_type, params, df, is_complete=False):
    key = self._generate_key(data_type, params)
    
    # 删除旧的相同 key 的记录
    self._metadata = self._metadata[self._metadata["key"] != key]
    
    # 添加新记录
    new_entry = pd.DataFrame([{...}])
    self._metadata = pd.concat([self._metadata, new_entry])
```

#### 问题 4: `get()` 方法对 `daily_full` 的过滤不完整

**当前代码：**
```python
if data_type == "daily_full" and start_date and end_date:
    if "trade_date" in df.columns:
        # 使用 trade_date 列过滤
        mask = (df["trade_date"] >= start_date) & ...
```

**问题：**
- `daily_full` 数据已设置索引为 `trade_date`
- 应该使用索引过滤，而不是列

**修复建议：**
```python
if data_type == "daily_full" and start_date and end_date:
    # 使用索引过滤
    start_dt = pd.to_datetime(start_date, format='%Y%m%d')
    end_dt = pd.to_datetime(end_date, format='%Y%m%d')
    mask = (df.index >= start_dt) & (df.index <= end_dt)
    return df[mask].copy()
```

### 2.4 建议的新增功能

#### 建议 1: 添加缓存统计报告

```python
def get_cache_report(self):
    """生成缓存统计报告"""
    report = {
        "total_size_mb": self._get_total_size_mb(),
        "total_files": len(self._metadata),
        "by_type": self._metadata.groupby("data_type").size().to_dict(),
        "complete_count": len(self._metadata[self._metadata["is_complete"] == True]),
        "oldest_cache": self._metadata["updated_at"].min(),
        "newest_cache": self._metadata["updated_at"].max(),
    }
    return report
```

#### 建议 2: 添加缓存迁移工具

```python
def export_cache(self, output_dir, ts_codes=None):
    """导出指定股票的缓存数据"""
    # 用于备份或迁移
    pass

def import_cache(self, input_dir):
    """导入缓存数据"""
    # 从备份恢复
    pass
```

---

## 三、数据流审查

### 3.1 典型数据流

```
用户请求
    ↓
cli.py / main.py
    ↓
TushareDataProvider.get_daily_data()
    ↓
DataCache.get()  ← 检查缓存
    ↓
Tushare API      ← 缓存未命中
    ↓
DataCache.set()  ← 保存缓存
    ↓
返回数据
```

### 3.2 发现的问题

#### 问题 1: 批量获取时重复检查缓存

**场景：** 批量回测时，多只股票可能重复请求相同日期范围

**当前：** 每次请求都独立检查缓存

**建议：** 批量获取时预加载缓存
```python
def prefetch_cache(self, ts_codes, start_date, end_date):
    """预加载多只股票的缓存"""
    for ts_code in ts_codes:
        self.cache.get("daily_full", {"ts_code": ts_code, "adj": "qfq"})
```

#### 问题 2: 错误处理不够细致

**当前：**
```python
try:
    df = self.pro.daily(...)
except Exception as e:
    logger.error(f"获取数据失败：{e}")
    return pd.DataFrame()
```

**问题：**
- 所有错误都返回空 DataFrame
- 无法区分网络错误、数据错误、权限错误

**建议：**
```python
try:
    df = self.pro.daily(...)
except Exception as e:
    if "积分" in str(e):
        logger.error("积分不足，需要升级 Tushare 会员")
    elif "limit" in str(e):
        logger.error("API 调用次数超限，请稍后重试")
    else:
        logger.error(f"获取数据失败：{e}")
    return pd.DataFrame()
```

---

## 四、优先级修复清单

### P0 - 立即修复

1. **修复 `_fetch_all_history` 获取逻辑**
   - 从上市日期开始获取，而不是请求日期
   - 确保 `daily_full` 是真正的全量数据

2. **保护 `daily_full` 不被 LRU 淘汰**
   - 在 `_enforce_size_limit()` 中跳过 `daily_full`

3. **修复 `daily_full` 过滤逻辑**
   - 使用索引过滤，而不是列过滤

### P1 - 近期修复

4. **增强增量更新逻辑**
   - 检查数据缺口
   - 处理停牌股票

5. **优化元数据管理**
   - 同一 key 只保留一条记录
   - 定期清理旧元数据

6. **增强错误处理**
   - 区分错误类型
   - 提供明确的错误信息

### P2 - 长期优化

7. **添加数据完整性验证**
   - 检查日期连续性
   - 检查数据质量

8. **添加批量获取接口**
   - 批量获取多只股票
   - 预加载缓存

9. **添加缓存管理工具**
   - 缓存统计报告
   - 缓存导出/导入

---

## 五、总结

### 整体评价

**架构设计：** ⭐⭐⭐⭐ (4/5)
- 持久化策略正确
- 缓存类型设计合理
- 降级机制完善

**代码实现：** ⭐⭐⭐ (3/5)
- 存在多处逻辑错误
- 错误处理不够细致
- 元数据管理需优化

**文档完整性：** ⭐⭐⭐⭐ (4/5)
- 有详细的使用文档
- 缺少内部实现文档
- 缺少故障排查指南

### 核心问题

1. **`_fetch_all_history` 名不副实** - 最严重，导致 `daily_full` 不是真正的全量数据
2. **`daily_full` 可能被淘汰** - 可能导致历史数据丢失
3. **增量更新不检查缺口** - 可能导致数据不完整

### 建议

1. **立即修复 P0 问题** - 确保数据获取和保存逻辑正确
2. **添加单元测试** - 覆盖各种场景
3. **监控和日志** - 添加详细的运行日志
4. **用户文档** - 添加故障排查指南
