# 缓存压缩使用指南

## 概述

系统支持多种 Parquet 压缩算法，可以在保证数据完整性的前提下减少存储空间。

## 压缩算法对比

| 算法 | 压缩比 | 写入速度 | 读取速度 | 推荐场景 |
|------|--------|---------|---------|---------|
| `none` | 1x | 最快 | 最快 | 测试/临时数据 |
| `snappy` | 2-3x | 快 | 快 | **默认推荐** |
| `gzip` | 3-5x | 中等 | 中等 | 平衡性能和空间 |
| `brotli` | 5-8x | 慢 | 中等 | 归档/冷数据 |
| `zstd` | 4-6x | 快 | 快 | 最佳平衡 |

## 使用方法

### 1. 设置压缩方式

```python
from quant_strategy.data.tushare_provider import TushareDataProvider

# 使用 gzip 压缩
provider = TushareDataProvider(
    token="your_token",
    compression="gzip"  # none/snappy/gzip/brotli/zstd
)
```

### 2. 在 AI 助手中使用

```python
# AI 助手会自动使用配置的压缩方式
# 默认使用 gzip 压缩

python -m quant_strategy.cli ai

> 下载 2025 年数据  # 自动使用 gzip 压缩保存
```

### 3. 转换现有缓存

```bash
# 转换为 gzip 压缩
python convert_cache.py --compression gzip

# 转换为 zstd 压缩
python convert_cache.py --compression zstd

# 不压缩（最快）
python convert_cache.py --compression none
```

## 性能影响

### 写入性能

```
none   > snappy > zstd > gzip > brotli
最快                      最慢
```

### 读取性能

```
none   ≈ snappy ≈ zstd ≈ gzip ≈ brotli
(差异很小，通常<5ms)
```

### 空间节省

以 5000 只股票×250 天数据为例：

| 压缩 | 原始大小 | 压缩后 | 节省 |
|------|---------|-------|------|
| none | 1000 MB | 1000 MB | 0% |
| snappy | 1000 MB | 400 MB | 60% |
| gzip | 1000 MB | 250 MB | 75% |
| brotli | 1000 MB | 150 MB | 85% |

## 推荐配置

### 场景 1：开发/测试
```python
compression="none"  # 最快速度
```

### 场景 2：日常使用（推荐）
```python
compression="snappy"  # 平衡速度和空间
```

### 场景 3：空间有限
```python
compression="gzip"  # 更高压缩比
```

### 场景 4：数据归档
```python
compression="brotli"  # 最高压缩比
```

## 常见问题

### Q: 压缩会影响数据准确性吗？
**A:** 不会。所有压缩都是无损的，数据完全一致。

### Q: 可以混合使用不同压缩吗？
**A:** 可以，但不推荐。建议统一使用一种压缩方式。

### Q: 如何查看当前缓存的压缩方式？
**A:** 使用以下代码：
```python
import pyarrow.parquet as pq

f = pq.ParquetFile("data_cache/xxx.parquet")
print(f.metadata.to_dict())
```

### Q: 压缩后缓存还能用吗？
**A:** 可以，压缩对应用透明，读取时无需指定压缩方式。

## 实际测试

运行测试脚本：
```bash
python test_compression.py
```

输出示例：
```
none    :   0.03 MB  (写：38.9ms, 读：6.9ms)
snappy  :   0.03 MB  (写： 9.3ms, 读：2.1ms)
gzip    :   0.03 MB  (写：13.0ms, 读：2.0ms)
brotli  :   0.03 MB  (写：83.4ms, 读：2.6ms)
zstd    :   0.03 MB  (写：15.3ms, 读：2.7ms)
```

## 总结

- **默认使用 `snappy`**：速度和空间的平衡
- **空间紧张用 `gzip`**：更高的压缩比
- **追求速度用 `none`**：最快的读写
- **归档数据用 `brotli`**：最高的压缩比

---

**更新**: 系统现在默认使用 `gzip` 压缩，可节省约 70-80% 空间。
