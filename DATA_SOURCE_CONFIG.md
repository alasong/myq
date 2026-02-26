# 数据源配置指南

## 概述

系统现已支持多数据源自动切换，包括：
- **Tushare Pro** - 主数据源（需要 token）
- **AKShare** - 备用数据源（完全免费）
- **聚宽 JoinQuant** - 高质量数据源（可选）

## 快速开始

### 方式 1：自动模式（推荐）

```bash
# 设置环境变量
export TUSHARE_TOKEN=your_token_here
export DATA_SOURCE=auto

# 运行回测
python -m quant_strategy.cli backtest --strategy dual_ma --ts_code 000001.SZ
```

系统会自动：
1. 优先使用 AKShare（免费）
2. AKShare 失败时自动切换到 Tushare
3. 共享缓存，避免重复请求

### 方式 2：指定数据源

```bash
# 仅使用 Tushare
export DATA_SOURCE=tushare
export TUSHARE_TOKEN=your_token

# 仅使用 AKShare
export DATA_SOURCE=akshare

# 多数据源模式
export DATA_SOURCE=multi
```

## 数据源对比

| 特性 | Tushare | AKShare | 聚宽 |
|------|---------|---------|------|
| **成本** | 免费/付费 | 完全免费 | 免费额度 |
| **稳定性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **数据质量** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **实时性** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **板块数据** | 需要积分 | 免费 | 免费 |
| **安装** | `pip install tushare` | `pip install akshare` | `pip install jqdatasdk` |

## 配置选项

### 环境变量

```bash
# 数据源类型
# 可选值：auto, tushare, akshare, multi
export DATA_SOURCE=auto

# Tushare Token
export TUSHARE_TOKEN=your_token_here

# 聚宽账号（可选）
export JQ_USER=your_username
export JQ_PASSWORD=your_password

# 缓存配置
export USE_CACHE=true
export CACHE_DIR=./data_cache
```

### 代码配置

```python
from quant_strategy.data import create_data_provider

# 方式 1: 自动选择
provider = create_data_provider(
    source='auto',
    tushare_token='your_token',
    use_cache=True
)

# 方式 2: 多数据源
provider = create_data_provider(
    source='multi',
    sources=['akshare', 'tushare', 'jqdata'],
    tushare_token='your_token',
    jq_user='your_username',
    jq_password='your_password',
    use_cache=True
)

# 方式 3: 单一数据源
provider = create_data_provider(
    source='akshare',
    use_cache=True
)

# 获取数据
data = provider.get_daily_data('000001.SZ', '20250101', '20251231', adj='qfq')
```

## 数据源故障转移逻辑

```
请求数据
    ↓
┌─────────────────┐
│ 检查本地缓存    │ → 命中 → 返回缓存数据
└─────────────────┘
    ↓ 未命中
┌─────────────────┐
│ 尝试 AKShare    │ → 成功 → 写入缓存 → 返回
└─────────────────┘
    ↓ 失败
┌─────────────────┐
│ 尝试 Tushare    │ → 成功 → 写入缓存 → 返回
└─────────────────┘
    ↓ 失败
┌─────────────────┐
│ 尝试 聚宽       │ → 成功 → 写入缓存 → 返回
└─────────────────┘
    ↓ 失败
返回空 DataFrame + 错误日志
```

## 使用示例

### 1. 单股票回测

```bash
# 使用默认配置（自动选择数据源）
python -m quant_strategy.cli backtest \
    --strategy dual_ma \
    --ts_code 000001.SZ

# 强制使用 AKShare
export DATA_SOURCE=akshare
python -m quant_strategy.cli backtest \
    --strategy dual_ma \
    --ts_code 000001.SZ
```

### 2. 板块回测

```bash
# 使用多数据源（概念数据可能来自 AKShare）
export DATA_SOURCE=multi
python -m quant_strategy.cli sector-backtest \
    --strategy kdj \
    --sector_type custom \
    --ts_codes 000001.SZ 000002.SZ 000003.SZ
```

### 3. 批量回测

```bash
# 使用缓存加速
export DATA_SOURCE=auto
python -m quant_strategy.cli batch-backtest \
    --ts_code 300001.SZ \
    --start_date 20250101 \
    --end_date 20251231 \
    --workers 4
```

## 缓存管理

### 查看缓存

```bash
python -m quant_strategy.cli data list-cache
python -m quant_strategy.cli data cache-stats
```

### 清理缓存

```bash
# Python
from quant_strategy.data import DataCache
cache = DataCache()
cache.clear(older_than_days=30)  # 清理 30 天前的缓存
```

## 故障排查

### 问题 1: AKShare 连接失败

**现象：**
```
AKShare 获取日线数据失败：Max retries exceeded
```

**解决：**
1. 检查网络连接
2. 检查防火墙/代理设置
3. 切换到 Tushare: `export DATA_SOURCE=tushare`

### 问题 2: Tushare 积分不足

**现象：**
```
Tushare 接口无权限
```

**解决：**
1. 使用 AKShare: `export DATA_SOURCE=akshare`
2. 或使用多数据源自动切换

### 问题 3: 数据为空

**现象：**
```
获取数据失败：返回空 DataFrame
```

**解决：**
1. 检查股票代码格式（应为 `000001.SZ`）
2. 检查日期范围是否正确
3. 查看日志确认哪个数据源失败

## 性能优化建议

### 1. 启用缓存

```bash
export USE_CACHE=true
```

首次请求会较慢，后续相同请求直接从缓存读取。

### 2. 批量获取数据

```python
# 使用多数据源批量获取
provider = create_data_provider(source='auto')
data_dict = provider.get_multiple_stocks(
    ts_codes=['000001.SZ', '000002.SZ', '000003.SZ'],
    start_date='20250101',
    end_date='20251231'
)
```

### 3. 合理设置数据源优先级

```python
# 如果 AKShare 网络不好，调整优先级
provider = create_data_provider(
    source='multi',
    sources=['tushare', 'akshare']  # Tushare 优先
)
```

## 新增数据源

如需添加新的数据源，参考以下步骤：

1. 创建数据提供者类：
```python
# quant_strategy/data/my_provider.py
from .provider import BaseDataProvider

class MyDataProvider(BaseDataProvider):
    def get_daily_data(self, ts_code, start_date, end_date, adj="qfq"):
        # 实现数据获取逻辑
        pass
```

2. 注册到多数据源：
```python
# quant_strategy/data/provider.py
def _init_providers(self, **kwargs):
    # ...
    elif source == 'my_source':
        from .my_provider import MyDataProvider
        self.providers['my_source'] = MyDataProvider()
```

## 总结

- **日常使用**: `DATA_SOURCE=auto`（自动选择最优数据源）
- **稳定优先**: `DATA_SOURCE=tushare`（需要 token）
- **免费方案**: `DATA_SOURCE=akshare`（完全免费）
- **专业需求**: `DATA_SOURCE=multi`（多数据源保障）
