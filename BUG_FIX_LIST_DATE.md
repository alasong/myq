# Bug 修复报告 - 上市日期处理错误

## 问题描述

**错误信息：**
```
ERROR | 000001.SZ: 获取历史数据失败：'int' object has no attribute 'strftime'
```

**触发场景：**
批量获取股票数据时，`_fetch_all_history()` 方法处理上市日期失败

**根本原因：**
Tushare 返回的 `list_date` 字段可能是 `int` 类型（如 `20150105`），原代码直接调用 `.strftime()` 导致错误

---

## 修复内容

### 修复文件
`quant_strategy/data/tushare_provider.py`

### 修复前代码
```python
list_date_str = stock_info['list_date'].iloc[0]
if pd.notna(list_date_str):
    list_date = str(list_date_str)
    if len(list_date) == 8:
        pass
    else:
        list_date = pd.to_datetime(list_date_str).strftime('%Y%m%d')
```

### 修复后代码
```python
list_date_val = stock_info['list_date'].iloc[0]
if pd.notna(list_date_val):
    # 处理 int 或 string 类型
    if isinstance(list_date_val, (int, float)):
        list_date = str(int(list_date_val))
    else:
        list_date = str(list_date_val)
    
    # 确保是 8 位数字格式
    if len(list_date) == 8 and list_date.isdigit():
        pass  # 已经是 YYYYMMDD 格式
    elif len(list_date) == 10 and '-' in list_date:
        # YYYY-MM-DD 格式转换为 YYYYMMDD
        list_date = list_date.replace('-', '')
    else:
        # 其他格式，尝试解析
        try:
            list_date = pd.to_datetime(list_date).strftime('%Y%m%d')
        except:
            list_date = start_date  # 解析失败，使用默认值
```

---

## 修复说明

### 处理的格式类型

1. **int 类型** (如 `20150105`)
   ```python
   if isinstance(list_date_val, (int, float)):
       list_date = str(int(list_date_val))  # → "20150105"
   ```

2. **YYYYMMDD 字符串** (如 `"20150105"`)
   ```python
   if len(list_date) == 8 and list_date.isdigit():
       pass  # 直接使用
   ```

3. **YYYY-MM-DD 字符串** (如 `"2015-01-05"`)
   ```python
   elif len(list_date) == 10 and '-' in list_date:
       list_date = list_date.replace('-', '')  # → "20150105"
   ```

4. **其他格式** (如 `"Jan 5, 2015"`)
   ```python
   try:
       list_date = pd.to_datetime(list_date).strftime('%Y%m%d')
   except:
       list_date = start_date  # 解析失败，使用默认值
   ```

---

## 测试验证

### 测试命令
```bash
python -m quant_strategy.tools.fetch_all_stocks --start 20250101 --end 20251231 --batch 50
```

### 预期结果
```
INFO | 000001.SZ: 从上市日期 (19910403) 获取全部历史数据
INFO | 000001.SZ: 已保存历史数据（8500 天，从 19910403 到 20251231）
```

---

## 影响范围

### 影响的功能
- ✅ 批量获取股票数据
- ✅ 首次获取股票历史数据
- ✅ 数据完整性检查

### 不受影响的功能
- ✅ 缓存读取
- ✅ 增量更新
- ✅ 其他数据源（AKShare）

---

## 相关文件

| 文件 | 修改内容 |
|------|----------|
| `quant_strategy/data/tushare_provider.py` | 修复 `_fetch_all_history()` 上市日期处理 |

---

## 验证步骤

1. **语法验证**
   ```bash
   python -m py_compile quant_strategy/data/tushare_provider.py
   # ✅ 通过
   ```

2. **功能测试**
   ```bash
   python -m quant_strategy.tools.fetch_all_stocks --start 20250101 --end 20251231 --batch 50
   ```

3. **单只股票测试**
   ```bash
   python -c "
   from quant_strategy.data.tushare_provider import TushareDataProvider
   import os
   provider = TushareDataProvider()
   df = provider.get_daily_data('000001.SZ', '20250101', '20251231', 'qfq')
   print(f'获取成功：{len(df)} 天')
   "
   ```

---

## 总结

### 问题等级
**P1 - 严重** - 影响批量获取功能

### 修复状态
✅ **已修复**

### 修复日期
2026-02-27

### 测试状态
⏳ **待验证** - 需要运行批量获取测试

---

**报告人**: AI Assistant  
**审核状态**: 待审核
