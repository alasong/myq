# 龙头股数据获取指南

## 数据源说明

**仅使用 Tushare**（付费，稳定可靠）⭐⭐⭐⭐⭐

已移除的数据源：
- ~~AKShare~~（免费，稳定性太差）
- ~~聚宽 JoinQuant~~（需要额外配置）

## 数据完整性标记

系统会自动标记缓存数据的完整性：
- **完整数据**：已达到预期交易日天数（95% 以上），直接返回，不再重复获取
- **部分数据**：未达到预期天数，需要更新

## 使用方法

### 获取全量数据

```bash
# 自动跳过已完整的数据
python -m quant_strategy.tools.fetch_all_stocks --start 20230101 --end 20231231

# 强制重新获取（忽略缓存）
python -m quant_strategy.tools.fetch_all_stocks --start 20230101 --end 20231231 --force
```

### 设置 Tushare Token

```bash
# 方式 1：环境变量（推荐）
export TUSHARE_TOKEN=your_token_here

# Windows PowerShell
$env:TUSHARE_TOKEN="your_token_here"

# 方式 2：命令行参数
python -m quant_strategy.tools.fetch_all_stocks --start 20230101 --end 20231231 --token your_token_here
```

### 分批获取（推荐）

```bash
# Q1 季度
python -m quant_strategy.tools.fetch_all_stocks --start 20230101 --end 20230331 --batch 50

# Q2 季度
python -m quant_strategy.tools.fetch_all_stocks --start 20230401 --end 20230630 --batch 50
```

### 验证缓存

```bash
# 检查缓存数据质量
python -m quant_strategy.tools.verify_cache
```

输出示例：
```
缓存统计:
  文件数：4523
  大小：358.42 MB
  股票数：4523
  命中率：95.2%

============================================================
数据完整性统计:
============================================================
✅ 完整数据：4200 只 (92.9%)
⚠️  部分数据：323 只 (7.1%)
❓ 未知标记：0 只 (0.0%)

需要更新的股票示例（前 20 只）:
  600123.SH: 180 条记录，缓存 5 天
  000456.SZ: 200 条记录，缓存 3 天
```

## 参数说明

### fetch_all_stocks

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--start` | 开始日期 YYYYMMDD | 必需 |
| `--end` | 结束日期 YYYYMMDD | 必需 |
| `--batch` | 批次大小 | 100 |
| `--force` | 强制重新获取 | False |
| `--token` | Tushare Token | 从环境变量读取 |

### verify_cache

无参数，直接运行。

## 预计时间

**Tushare（付费）：**
- 每分钟约 300-500 只股票
- 全量 5000 只约 10-15 分钟

**增量更新：**
- 只获取未完整的数据
- 时间取决于缺失数据的数量

## 获取 Token

1. 访问 https://tushare.pro/ 注册账号
2. 在个人中心获取 API Token
3. 设置环境变量

### 积分要求

- 基础日线数据：免费（注册即有）
- 复权因子：需要一定积分
- 高级财务数据：需要更高积分

## 常见问题

### Q1: 获取数据中断怎么办？

A: 缓存会自动保存已完成的数据，重新运行命令即可继续。完整性标记会确保已完整的数据不会被重复获取。

### Q2: 如何查看哪些股票需要更新？

A: 运行 `python -m quant_strategy.tools.verify_cache` 查看部分数据的股票列表。

### Q3: 缓存占用多少空间？

A: 每只股票约 50-100KB，5000 只股票约 250-500MB。

### Q4: 如何清理缓存？

A: 手动删除 `data_cache` 目录，或使用 Python：
```python
from quant_strategy.data.data_cache import DataCache
cache = DataCache()
cache.clear()
```

### Q5: 为什么有些股票数据不完整？

A: 可能原因：
- 新股上市时间晚
- 长期停牌
- 数据获取中断

系统会自动跳过已完整的数据，只更新部分数据的股票。
