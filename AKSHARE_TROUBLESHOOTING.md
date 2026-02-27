# AKShare 稳定性问题与解决方案

## 一、问题分析

### 1.1 AKShare 不稳定的原因

| 原因 | 说明 | 影响 |
|------|------|------|
| **数据源依赖** | 依赖东方财富/新浪等第三方 API | API 可能随时变更 |
| **无官方保障** | 爬虫接口，非官方服务 | 稳定性无法保证 |
| **反爬虫限制** | 目标网站有反爬机制 | 可能被限流或封禁 |
| **网络波动** | 跨网络请求 | 连接失败率高 |

### 1.2 常见错误

```python
# 错误 1：连接超时
HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): 
Max retries exceeded with url: /api/qt/stock/kline/get...

# 错误 2：代理问题
Caused by ProxyError('Unable to connect to proxy', 
RemoteDisconnected('Remote end closed connection without response'))

# 错误 3：数据为空
返回 DataFrame 为空，无错误信息
```

---

## 二、解决方案

### 方案 1：启用缓存（强烈推荐）⭐⭐⭐⭐⭐

**原理：** 减少 API 调用次数，首次获取后使用缓存

```bash
# 环境变量启用缓存
export USE_CACHE=true

# 或使用配置文件
# config.yaml
data_source:
  use_cache: true
  cache_dir: ./data_cache
```

**效果：**
- 首次获取后，相同请求直接使用缓存
- 缓存永久有效（除非手动清理）
- 大幅减少 API 调用失败

**命令：**
```bash
# 首次运行（获取并缓存）
python -m quant_strategy.cli backtest --ts_code 000001.SZ

# 后续运行（使用缓存，秒级响应）
python -m quant_strategy.cli backtest --ts_code 000001.SZ
```

---

### 方案 2：多数据源自动切换（推荐）⭐⭐⭐⭐⭐

**原理：** AKShare 失败时自动切换到 Tushare

```bash
# 设置多数据源模式
export DATA_SOURCE=auto
export TUSHARE_TOKEN=your_token_here
```

**工作流程：**
```
请求数据
    ↓
尝试 AKShare → 失败
    ↓
自动切换 Tushare → 成功
    ↓
返回数据 + 写入缓存
```

**优势：**
- 无需手动干预
- 充分利用免费资源
- 保证数据获取成功率

---

### 方案 3：增加重试机制（已实现）⭐⭐⭐⭐

**原理：** 失败后自动重试，增加成功概率

**配置：**
```python
# akshare_provider.py
provider = AKShareDataProvider(
    use_cache=True,
    max_retries=3,        # 最大重试次数
    retry_delay=1.0       # 重试延迟（秒）
)
```

**效果：**
- 网络波动时自动恢复
- 随机延迟避免集中请求
- 日志记录便于排查

---

### 方案 4：批量预下载数据（推荐）⭐⭐⭐⭐

**原理：** 闲时批量下载数据到缓存，回测时直接使用

```bash
# 批量下载数据
python -m quant_strategy.cli data download \
    --ts_codes 000001.SZ 000002.SZ 300001.SZ \
    --start_date 20230101 \
    --end_date 20231231
```

**优势：**
- 避开交易高峰期
- 集中处理失败情况
- 回测速度大幅提升

---

### 方案 5：使用替代数据源

| 数据源 | 稳定性 | 成本 | 推荐场景 |
|--------|--------|------|----------|
| **Tushare** | ⭐⭐⭐⭐⭐ | 付费 | 生产环境 |
| **AKShare** | ⭐⭐⭐ | 免费 | 学习/测试 |
| **聚宽** | ⭐⭐⭐⭐ | 免费额度 | 量化研究 |
| **米筐** | ⭐⭐⭐⭐ | 付费 | 专业用户 |

**切换数据源：**
```bash
# 使用 Tushare
export DATA_SOURCE=tushare
export TUSHARE_TOKEN=your_token

# 使用 AKShare
export DATA_SOURCE=akshare

# 自动切换（推荐）
export DATA_SOURCE=auto
```

---

## 三、最佳实践

### 3.1 推荐配置

```bash
# .env 文件
# 数据源配置
DATA_SOURCE=auto
TUSHARE_TOKEN=your_token_here

# 缓存配置
USE_CACHE=true
CACHE_DIR=./data_cache

# 重试配置
MAX_RETRIES=3
RETRY_DELAY=1.0
```

### 3.2 工作流

```
1. 设置 TUSHARE_TOKEN（备用）
   export TUSHARE_TOKEN=xxx

2. 批量预下载数据（可选）
   python -m quant_strategy.cli data download ...

3. 运行回测（自动使用缓存）
   python -m quant_strategy.cli backtest ...

4. 查看缓存统计
   python -m quant_strategy.cli data cache-stats
```

### 3.3 缓存管理

```bash
# 查看缓存
python -m quant_strategy.cli data list-cache

# 缓存统计
python -m quant_strategy.cli data cache-stats

# 清理过期缓存（30 天前）
python -c "from quant_strategy.data import DataCache; c = DataCache(); c.clear(older_than_days=30)"

# 清空缓存
python -c "from quant_strategy.data import DataCache; c = DataCache(); c.clear()"
```

---

## 四、故障排查

### 4.1 检查网络连接

```bash
# 测试是否能访问东方财富
curl -I https://push2his.eastmoney.com

# 测试 Tushare
curl -I https://api.tushare.pro
```

### 4.2 检查代理设置

```bash
# 查看代理
echo $HTTP_PROXY
echo $HTTPS_PROXY

# 临时禁用代理
unset HTTP_PROXY
unset HTTPS_PROXY
```

### 4.3 查看详细日志

```bash
# 启用调试日志
export LOG_LEVEL=DEBUG

# 运行回测
python -m quant_strategy.cli backtest --config test.yaml 2>&1 | tee backtest.log
```

### 4.4 常见问题

**Q1: AKShare 一直失败怎么办？**

A: 
1. 检查网络连接
2. 检查代理设置
3. 使用 `DATA_SOURCE=tushare` 切换数据源
4. 使用缓存数据

**Q2: 缓存数据在哪里？**

A: `./data_cache/` 目录，Parquet 格式

**Q3: 如何确保数据准确性？**

A:
1. 使用多个数据源交叉验证
2. 定期更新缓存数据
3. 重要场景使用付费数据源

---

## 五、配置示例

### 5.1 开发环境（免费优先）

```yaml
# config.dev.yaml
data_source:
  provider: auto  # 自动选择
  token: ""       # AKShare 不需要 token
  use_cache: true
  cache_dir: ./data_cache

backtest:
  workers: 4
```

### 5.2 生产环境（稳定优先）

```yaml
# config.prod.yaml
data_source:
  provider: tushare  # 使用 Tushare
  token: your_token  # 付费 token
  use_cache: true

backtest:
  workers: 8
  use_processes: true
```

### 5.3 混合模式（推荐）

```yaml
# config.hybrid.yaml
# 默认使用 AKShare（免费）
# AKShare 失败时自动切换 Tushare（保底）
data_source:
  provider: auto
  token: your_token  # Tushare token 作为备用
  use_cache: true
```

---

## 六、总结

### 稳定性对比

| 方案 | 稳定性 | 成本 | 推荐度 |
|------|--------|------|--------|
| 纯 AKShare | ⭐⭐⭐ | 免费 | ⭐⭐⭐ |
| AKShare + 缓存 | ⭐⭐⭐⭐ | 免费 | ⭐⭐⭐⭐⭐ |
| AKShare + Tushare 备用 | ⭐⭐⭐⭐⭐ | 可选付费 | ⭐⭐⭐⭐⭐ |
| 纯 Tushare | ⭐⭐⭐⭐⭐ | 付费 | ⭐⭐⭐⭐ |

### 最终建议

1. **学习/研究：** AKShare + 缓存（免费够用）
2. **工作项目：** AKShare + Tushare 备用（稳定优先）
3. **生产环境：** 纯 Tushare 或其他付费服务（可靠性第一）

### 核心原则

> **缓存是最好的优化！**

无论使用哪个数据源，都建议启用缓存：
- 减少 API 调用
- 提高回测速度
- 降低失败概率
