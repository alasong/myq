# 数据源配置指南

## 数据源优先级

系统按照**稳定性优先**原则自动选择数据源：

| 优先级 | 数据源 | 类型 | 稳定性 | 成本 | 推荐场景 |
|--------|--------|------|--------|------|----------|
| ⭐⭐⭐⭐⭐ | **Tushare** | 付费 | 最高 | 付费 | 生产环境、重要回测 |
| ⭐⭐⭐⭐ | 聚宽 JoinQuant | 免费额度 | 较高 | 免费 | 研究、测试 |
| ⭐⭐⭐ | AKShare | 免费 | 一般 | 免费 | 学习、临时使用 |
| ⭐⭐⭐ | 新浪财经 | 免费 | 一般 | 免费 | 备用数据源 |

---

## 自动选择逻辑

### 默认行为（推荐）

```bash
# 设置 TUSHARE_TOKEN（付费用户）
export TUSHARE_TOKEN=your_token_here

# 自动模式：优先使用 Tushare，失败时切换到 AKShare
export DATA_SOURCE=auto

# 运行回测
python -m quant_strategy.cli backtest --ts_code 000001.SZ
```

**日志输出：**
```
08:40:00 | INFO | 检测到 Tushare Token，优先使用（付费数据源）
08:40:00 | INFO | 数据源初始化：tushare (付费，优先级高)
08:40:00 | INFO | 数据源初始化：akshare (免费，备用)
08:40:00 | INFO | 数据源优先级：Tushare(付费) > AKShare(免费)
```

### 无 Tushare Token

```bash
# 不设置 TUSHARE_TOKEN
unset TUSHARE_TOKEN

# 自动使用免费数据源
export DATA_SOURCE=auto
```

**日志输出：**
```
08:40:00 | WARNING | 未设置 TUSHARE_TOKEN，使用免费数据源
08:40:00 | INFO | 数据源初始化：akshare (免费，备用)
```

---

## 配置方式

### 方式 1：环境变量（推荐）

```bash
# .env 文件

# Tushare Token（付费用户必填）
TUSHARE_TOKEN=your_token_here

# 数据源选择
DATA_SOURCE=auto  # auto/tushare/akshare/multi

# 聚宽账号（可选，作为备用）
JQ_USER=your_username
JQ_PASSWORD=your_password

# 缓存配置
USE_CACHE=true
CACHE_DIR=./data_cache
```

### 方式 2：配置文件

```yaml
# config.yaml

data_source:
  # 自动模式：按优先级选择
  provider: auto
  
  # Tushare Token
  token: your_token_here
  
  # 启用缓存
  use_cache: true
  
  # 缓存目录
  cache_dir: ./data_cache
```

### 方式 3：代码指定

```python
from quant_strategy.data import create_data_provider

# 方式 1：自动选择（推荐）
provider = create_data_provider(
    source='auto',
    tushare_token='your_token',
    use_cache=True
)

# 方式 2：强制使用 Tushare
provider = create_data_provider(
    source='tushare',
    token='your_token'
)

# 方式 3：仅使用 AKShare（免费）
provider = create_data_provider(
    source='akshare',
    use_cache=True
)
```

---

## 故障转移逻辑

### 工作流程

```
请求数据
    ↓
┌─────────────────────────────────┐
│ 1. Tushare（付费，优先级最高）   │
│    ✅ 成功 → 返回数据            │
│    ❌ 失败 → 切换到下一个        │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 2. AKShare（免费，备用）         │
│    ✅ 成功 → 返回数据            │
│    ❌ 失败 → 继续切换            │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 3. 聚宽（如果配置了账号）        │
│    ✅ 成功 → 返回数据            │
│    ❌ 失败 → 报错                │
└─────────────────────────────────┘
```

### 日志示例

```bash
# 首次请求（Tushare 成功）
08:40:00 | DEBUG | 尝试从 tushare 获取数据：000001.SZ
08:40:01 | INFO  | ✅ 成功从 tushare 获取数据：000001.SZ (243 条)

# Tushare 失败，切换到 AKShare
08:40:02 | DEBUG | 尝试从 tushare 获取数据：300001.SZ
08:40:03 | WARN  | ❌ tushare 获取数据失败：API 限流
08:40:03 | DEBUG | 尝试从 akshare 获取数据：300001.SZ
08:40:04 | INFO  | ✅ 成功从 akshare 获取数据：300001.SZ (243 条)
```

---

## 最佳实践

### 生产环境（推荐配置）

```bash
# .env

# 1. 设置 Tushare Token（必须）
TUSHARE_TOKEN=your_token_here

# 2. 启用缓存（必须）
USE_CACHE=true

# 3. 自动模式（优先 Tushare，失败切换 AKShare）
DATA_SOURCE=auto

# 4. 聚宽备用（可选）
JQ_USER=your_jq_user
JQ_PASSWORD=your_jq_password
```

**优势：**
- ✅ Tushare 优先（最稳定）
- ✅ AKShare 备用（防止 Tushare 限流）
- ✅ 缓存加速（减少 API 调用）
- ✅ 聚宽兜底（三重保障）

### 学习/测试环境

```bash
# .env

# 1. 不设置 Tushare Token（使用免费数据源）
# TUSHARE_TOKEN=

# 2. 启用缓存（必须）
USE_CACHE=true

# 3. 自动模式（使用 AKShare）
DATA_SOURCE=auto
```

**优势：**
- ✅ 完全免费
- ✅ 缓存加速
- ✅ 足够学习使用

### 批量回测

```bash
# 1. 预下载数据（使用 Tushare）
python -m quant_strategy.cli data download \
    --ts_codes 000001.SZ 000002.SZ 300001.SZ \
    --start_date 20230101 \
    --end_date 20231231

# 2. 回测时使用缓存（秒级响应）
python -m quant_strategy.cli backtest \
    --ts_code 000001.SZ \
    --start_date 20230101 \
    --end_date 20231231
```

---

## 性能对比

### 场景 1：有 Tushare Token

| 数据源 | 成功率 | 平均耗时 | 稳定性 |
|--------|--------|----------|--------|
| Tushare | 99% | 1-2 秒 | ⭐⭐⭐⭐⭐ |
| AKShare | 80% | 3-5 秒 | ⭐⭐⭐ |

**建议：** 付费用户使用 `DATA_SOURCE=auto`，优先 Tushare。

### 场景 2：无 Tushare Token

| 数据源 | 成功率 | 平均耗时 | 稳定性 |
|--------|--------|----------|--------|
| AKShare | 80% | 3-5 秒 | ⭐⭐⭐ |

**建议：** 启用缓存，批量预下载数据。

---

## 常见问题

### Q1: 如何查看当前使用的数据源？

**A:** 查看日志输出：
```bash
08:40:00 | INFO | ✅ 成功从 tushare 获取数据：000001.SZ
```

或查看统计：
```python
from quant_strategy.data import create_data_provider
provider = create_data_provider(source='auto')
print(provider.get_stats())
```

### Q2: Tushare 限流了怎么办？

**A:** 系统会自动切换到 AKShare：
```
08:40:03 | WARN  | ❌ tushare 获取数据失败：API 限流
08:40:03 | INFO  | ✅ 成功从 akshare 获取数据：000001.SZ
```

### Q3: 如何强制使用某个数据源？

**A:** 
```bash
# 强制使用 Tushare
export DATA_SOURCE=tushare

# 强制使用 AKShare
export DATA_SOURCE=akshare
```

### Q4: 聚宽数据源如何使用？

**A:** 
1. 注册聚宽账号：https://www.joinquant.com/
2. 设置环境变量：
```bash
export JQ_USER=your_username
export JQ_PASSWORD=your_password
```
3. 安装 jqdatasdk：
```bash
pip install jqdatasdk
```

### Q5: 缓存数据在哪里？

**A:** `./data_cache/` 目录

查看缓存：
```bash
python -m quant_strategy.cli data list-cache
```

清理缓存：
```bash
python -c "from quant_strategy.data import DataCache; c = DataCache(); c.clear()"
```

---

## 总结

### 推荐配置

| 用户类型 | 配置 | 说明 |
|---------|------|------|
| **付费用户** | `DATA_SOURCE=auto` + `TUSHARE_TOKEN=xxx` | 优先 Tushare，AKShare 备用 |
| **免费用户** | `DATA_SOURCE=auto` | 使用 AKShare |
| **专业用户** | `DATA_SOURCE=auto` + 聚宽账号 | 三重保障 |

### 核心原则

> **稳定性优先：Tushare（付费）> 聚宽（免费额度）> AKShare（免费）**

### 最佳实践

1. **启用缓存**：减少 API 调用，提高速度
2. **批量预下载**：闲时下载数据，回测时使用缓存
3. **多数据源**：配置备用数据源，防止单点故障
4. **定期检查**：查看缓存状态，清理过期数据

---

**更新时间**: 2026 年 2 月 27 日
