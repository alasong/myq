# 数据完整性 100% 要求实现（已更新）

## ⚠️ 策略已更新

**最新策略：数据持久化**

历史数据全部保存到本地，只实时获取新数据。

详见：[DATA_PERSISTENCE_STRATEGY.md](DATA_PERSISTENCE_STRATEGY.md)

## 核心改进（历史文档）

### 1. 本地存储交易日历和停牌日历

#### 交易日历（按年份缓存）
```python
# 改进前：按日期范围缓存，重复获取
cache_key = {"exchange": "SSE", "start": "20230101", "end": "20231231"}

# 改进后：按年份缓存，一次获取多年使用
cache_key = {"exchange": "SSE", "year": "2023"}
# 缓存标记：is_complete=True（交易日历是固定的，永久有效）
```

**优势：**
- 减少 API 调用
- 多年数据只需获取一次
- 交易日历固定不变，永久缓存

#### 停牌日历（按股票 + 年份缓存）
```python
# 按股票和年份缓存
cache_key = {"ts_code": "600519.SH", "year": "2023"}
# 缓存标记：is_complete=True
```

**优势：**
- 停牌数据历史不变，永久缓存
- 减少重复 API 调用

### 2. 100% 完整度要求

#### 改进前
```python
# 90% 阈值，允许 10% 误差
if completeness < 0.9:  # 少于 90% 认为不完整
    return None
elif completeness >= 0.95:  # 95% 以上标记完整
    mark_as_complete()
```

#### 改进后
```python
# 100% 要求，不允许误差
if actual_days < expected_days:
    # 数据不完整，重新获取
    return None
elif actual_days == expected_days:
    # 正好匹配，标记完整
    mark_as_complete()
elif actual_days > expected_days:
    # 超过预期，存在异常（重复数据）
    logger.warning("数据异常！可能存在重复")
    return None
```

### 3. 重复数据检测和清理

#### 获取数据时检测
```python
def _process_daily(self, df, ts_code):
    # 检测重复日期
    duplicates = df["trade_date"].duplicated().sum()
    if duplicates > 0:
        logger.warning(f"{ts_code}: 检测到 {duplicates} 条重复日期数据，保留第一条")
        df = df.drop_duplicates(subset="trade_date", keep="first")
```

#### 缓存检查时检测
```python
def get(self, data_type, params, ...):
    # 检查缓存数据
    if "trade_date" in df.columns:
        duplicates = df["trade_date"].duplicated().sum()
        if duplicates > 0:
            logger.warning(f"缓存数据存在重复：{key}")
            return None  # 强制重新获取
```

#### 超过 100% 处理
```python
if actual_days > expected_days:
    logger.warning(f"数据异常！实际{actual_days}天 > 预期{expected_days}天")
    # 尝试清理重复
    df = df[~df.index.duplicated(keep='first')]
    actual_days = len(df)
    # 清理后重新检查
    is_complete = (actual_days == expected_days)
```

## 实现细节

### 交易日历按年份缓存

```python
def get_trade_cal(self, exchange, start_date, end_date):
    # 解析年份范围
    start_year = int(start_date[:4])
    end_year = int(end_date[:4])
    
    all_dates = []
    for year in range(start_year, end_year + 1):
        cache_key = {"exchange": exchange, "year": str(year)}
        
        # 检查缓存
        cached = self.cache.get("trade_cal_year", cache_key, ...)
        if cached:
            all_dates.append(cached)
            continue
        
        # 获取全年数据
        cal_df = self.pro.trade_cal(exchange=exchange, ...)
        cal_df = cal_df[cal_df["is_open"] == 1]["cal_date"]
        
        # 缓存（标记为完整）
        self.cache.set("trade_cal_year", cache_key, cal_df, is_complete=True)
        all_dates.append(cal_df)
    
    # 合并并过滤日期范围
    result = pd.concat(all_dates, ignore_index=True)
    return result[(result >= start_date) & (result <= end_date)]
```

### 停牌天数计算

```python
def _get_suspend_days(self, ts_code, start_date, end_date):
    # 按年份获取停牌数据
    for year in range(start_year, end_year + 1):
        cache_key = {"ts_code": ts_code, "year": str(year)}
        
        # 检查缓存
        cached = self.cache.get("suspend_cal_year", cache_key, ...)
        if cached:
            all_suspend.append(cached)
            continue
        
        # 获取全年停牌数据
        suspend_df = self.pro.suspend_cal(ts_code=ts_code, ...)
        
        # 缓存（标记为完整）
        self.cache.set("suspend_cal_year", cache_key, suspend_df, is_complete=True)
        all_suspend.append(suspend_df)
    
    # 合并、去重、计数
    suspend_df = pd.concat(all_suspend).drop_duplicates()
    return int(mask.sum())
```

### 预期交易日计算

```python
def _calc_expected_trading_days(self, ts_code, start_date, end_date):
    # 1. 获取交易日历（本地缓存）
    trade_cal = self.get_trade_cal(exchange, start_date, end_date)
    total_trading_days = len(trade_cal)
    
    # 2. 获取停牌天数（本地缓存）
    suspend_days = self._get_suspend_days(ts_code, start_date, end_date)
    
    # 3. 计算预期（100% 要求，不容错）
    expected_days = max(0, total_trading_days - suspend_days)
    return expected_days
```

### 数据获取和验证

```python
def get_daily_data(self, ts_code, start_date, end_date, adj):
    # 计算预期天数
    expected_days = self._calc_expected_trading_days(...)
    
    # 检查缓存
    cached = self.cache.get("daily", params, ..., expected_days=expected_days)
    if cached:
        return cached  # 100% 完整数据
    
    # 获取数据
    df = self.pro.daily(...)
    
    # 处理（检测重复）
    df = self._process_daily(df, ts_code)
    
    # 验证（100% 要求）
    actual_days = len(df)
    duplicates = df.index.duplicated().sum()
    
    if duplicates > 0:
        logger.warning(f"检测到 {duplicates} 条重复数据，已清理")
        df = df[~df.index.duplicated(keep='first')]
        actual_days = len(df)
    
    if actual_days > expected_days:
        logger.warning(f"数据异常！实际{actual_days}天 > 预期{expected_days}天")
        df = df[~df.index.duplicated(keep='first')]
        actual_days = len(df)
    
    # 100% 匹配才标记完整
    is_complete = (actual_days == expected_days)
    self.cache.set("daily", params, df, is_complete=is_complete)
    
    return df
```

## 缓存验证工具

```bash
python -m quant_strategy.tools.verify_cache
```

输出示例：
```
缓存统计:
  文件数：4523
  大小：358.42 MB
  股票数：4523

======================================================================
数据完整性统计 (100% 要求):
======================================================================
[OK] 完整数据：4200 只 (92.9%)
[WARN] 部分数据：323 只 (7.1%)
[UNK] 未知标记：0 只 (0.0%)
[DUP] 抽样发现重复：5 只 (10.0%)

需要更新的股票示例（前 20 只）:
  600123.SH: 180 条记录，缓存 5 天
  000456.SZ: 200 条记录，缓存 3 天
```

## 数据状态说明

| 状态 | 说明 | 处理 |
|------|------|------|
| **[OK] 完整** | 实际天数 = 预期天数 | 直接使用 |
| **[WARN] 部分** | 实际天数 < 预期天数 | 需要重新获取 |
| **[UNK] 未知** | 无完整性标记 | 需要验证 |
| **[DUP] 重复** | 检测到重复数据 | 清理后重新获取 |

## 使用影响

### 正面影响

1. **数据质量提升**：100% 完整度要求，确保数据准确
2. **重复数据清理**：自动检测并清理重复
3. **缓存效率提升**：交易日历和停牌数据按年份缓存
4. **减少 API 调用**：历史数据永久缓存

### 注意事项

1. **首次获取可能变慢**：需要获取交易日历和停牌数据
2. **旧缓存需要更新**：90% 阈值的旧缓存会被标记为不完整
3. **异常数据处理**：超过 100% 的数据会被标记为异常

## 文件变更

### 修改的文件
- `quant_strategy/data/tushare_provider.py`
  - 新增 `_get_suspend_days()` - 按年份获取停牌数据
  - 修改 `get_trade_cal()` - 按年份缓存交易日历
  - 修改 `_calc_expected_trading_days()` - 100% 要求
  - 修改 `_process_daily()` - 重复数据检测
  - 修改 `get_daily_data()` - 100% 验证和重复清理

- `quant_strategy/data/data_cache.py`
  - 修改 `get()` - 100% 完整度检查和重复检测

- `quant_strategy/tools/verify_cache.py`
  - 新增重复数据抽样检查
  - 更新输出格式

### 新增的文件
- `DATA_100_PERCENT_COMPLETE.md` - 本说明文档

## 迁移指南

### 清理旧缓存
```python
from quant_strategy.data.data_cache import DataCache
cache = DataCache()

# 清理所有旧缓存（可选）
cache.clear()

# 或只清理超过 90 天的缓存
cache.clear(older_than_days=90)
```

### 重新获取数据
```bash
# 强制重新获取（忽略旧缓存）
python -m quant_strategy.tools.fetch_all_stocks --start 20230101 --end 20231231 --force
```

### 验证数据质量
```bash
# 检查缓存状态
python -m quant_strategy.tools.verify_cache
```
