# 板块回测使用指南

## 一、板块搜索功能

### 1.1 搜索板块（按名称）

```bash
# 搜索包含关键词的板块
python -m quant_strategy.cli data search-sector \
    --keyword "人工智能" \
    --sector_type all \
    --limit 20
```

**参数说明：**
- `--keyword`: 搜索关键词（支持模糊匹配）
- `--sector_type`: 板块类型
  - `industry`: 行业板块
  - `concept`: 概念板块
  - `area`: 地区板块
  - `all`: 全部类型
- `--limit`: 显示数量限制

**示例：**
```bash
# 搜索人工智能相关概念
python -m quant_strategy.cli data search-sector --keyword "人工智能"

# 搜索医药行业
python -m quant_strategy.cli data search-sector \
    --keyword "医药" \
    --sector_type industry

# 搜索广东地区
python -m quant_strategy.cli data search-sector \
    --keyword "广东" \
    --sector_type area
```

### 1.2 查看板块列表

```bash
# 查看行业板块列表
python -m quant_strategy.cli data list-industries

# 查看概念板块列表
python -m quant_strategy.cli data list-concepts
```

---

## 二、板块回测逻辑

### 2.1 板块回测流程图

```
用户输入板块名称
    ↓
搜索板块成分股
    ↓
获取股票列表（最多 50 只）
    ↓
并行回测每只股票
    ↓
汇总结果并排序
```

### 2.2 回测命令格式

```bash
python -m quant_strategy.cli sector-backtest \
    --strategy <策略名称> \
    --sector_type <板块类型> \
    --sector_name <板块名称> \
    --start_date <开始日期> \
    --end_date <结束日期> \
    --workers <并发数> \
    --use_processes
```

**参数说明：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `--strategy` | ✅ | 策略名称（kdj/rsi/macd 等） |
| `--sector_type` | ✅ | 板块类型（industry/concept/area/custom） |
| `--sector_name` | ❌ | 板块名称（custom 模式不需要） |
| `--ts_codes` | ❌ | 自定义股票列表（custom 模式使用） |
| `--start_date` | ❌ | 开始日期，默认 20200101 |
| `--end_date` | ❌ | 结束日期，默认 20231231 |
| `--workers` | ❌ | 并发工作线程数，默认 CPU 核心数 |
| `--use_processes` | ❌ | 使用多进程（默认多线程） |

---

## 三、使用示例

### 3.1 行业板块回测

```bash
# 回测电子行业
python -m quant_strategy.cli sector-backtest \
    --strategy kdj \
    --sector_type industry \
    --sector_name 电子 \
    --start_date 20250101 \
    --end_date 20251231 \
    --workers 8
```

### 3.2 概念板块回测

```bash
# 回测人工智能概念
python -m quant_strategy.cli sector-backtest \
    --strategy rsi \
    --sector_type concept \
    --sector_name 人工智能 \
    --start_date 20250101 \
    --end_date 20251231
```

### 3.3 地区板块回测

```bash
# 回测广东地区股票
python -m quant_strategy.cli sector-backtest \
    --strategy macd \
    --sector_type area \
    --sector_name 广东 \
    --start_date 20250101 \
    --end_date 20251231
```

### 3.4 自定义股票组合回测

```bash
# 回测自定义股票组合
python -m quant_strategy.cli sector-backtest \
    --strategy dual_ma \
    --sector_type custom \
    --ts_codes 000001.SZ 000002.SZ 300001.SZ \
    --start_date 20250101 \
    --end_date 20251231
```

---

## 四、回测结果解读

### 4.1 输出格式

```
================================================================================
板块回测结果汇总
================================================================================
       代码     收益率    夏普    最大回撤  交易次数
300003.SZ  38.33%  1.09 -14.54%    13
300002.SZ  -6.55% -0.23 -15.64%    13
300001.SZ -33.31% -1.58 -33.31%    17
================================================================================
```

### 4.2 指标说明

| 指标 | 说明 | 优秀标准 |
|------|------|----------|
| 收益率 | 回测期总收益 | >20% |
| 夏普比率 | 风险调整后收益 | >1.0 |
| 最大回撤 | 最大亏损幅度 | <-20% 为差 |
| 交易次数 | 总交易笔数 | 适中为宜 |

---

## 五、板块回测详细逻辑

### 5.1 成分股获取逻辑

```python
# 1. 行业板块
if sector_type == "industry":
    df = ts_provider.get_industry_stocks(industry_name=args.sector_name)
    # 从 Tushare/AKShare 获取行业成分股

# 2. 概念板块
elif sector_type == "concept":
    df = ts_provider.get_concept_stocks(concept_name=args.sector_name)
    # 从 Tushare/AKShare 获取概念成分股

# 3. 地区板块
elif sector_type == "area":
    df = sector_provider.get_area_stocks(area=args.sector_name)
    # 从股票基本信息中提取地区

# 4. 自定义组合
elif sector_type == "custom":
    ts_codes = args.ts_codes
    # 使用用户指定的股票列表
```

### 5.2 股票数量限制

```python
# 限制最多 50 只股票，避免回测时间过长
if df is not None and not df.empty:
    ts_codes = df["ts_code"].tolist()[:50]
```

**原因：**
- 控制回测时间
- 减少 API 调用压力
- 聚焦板块内主要股票

### 5.3 并行回测逻辑

```python
# 1. 初始化并行回测引擎
backtester = ParallelBacktester(
    max_workers=args.workers,
    use_processes=args.use_processes
)

# 2. 获取每只股票数据
data_dict = {}
for ts_code in ts_codes:
    data = data_provider.get_daily_data(ts_code, start_date, end_date)
    data_dict[ts_code] = data

# 3. 并行执行回测
results = backtester.backtest_stocks(
    strategy_class=strategy_class,
    data_dict=data_dict,
    strategy_params={},
    show_progress=True
)

# 4. 汇总结果
summary_data = []
for ts_code, task_result in results.items():
    if task_result.result:
        summary_data.append({
            "代码": ts_code,
            "收益率": task_result.result.total_return,
            "夏普": task_result.result.sharpe_ratio,
            "最大回撤": task_result.result.max_drawdown,
            "交易次数": task_result.result.total_trades
        })

# 5. 按收益率排序
summary_df = pd.DataFrame(summary_data)
summary_df = summary_df.sort_values("收益率", ascending=False)
```

---

## 六、性能优化建议

### 6.1 并发设置

```bash
# 4 核 CPU 推荐配置
--workers 4 --use_processes

# 8 核 CPU 推荐配置
--workers 8 --use_processes
```

### 6.2 数据缓存

```bash
# 首次运行会缓存数据，后续运行更快
export USE_CACHE=true
```

### 6.3 日期范围

```bash
# 回测 1 年数据约需 30 秒（50 只股票）
--start_date 20250101 --end_date 20251231

# 回测 3 年数据约需 90 秒（50 只股票）
--start_date 20230101 --end_date 20251231
```

---

## 七、常见问题

### Q1: 为什么返回的股票数量不足 50 只？

**A:** 
- 板块实际成分股不足 50 只
- 部分股票数据获取失败
- 部分股票停牌/退市

### Q2: 回测结果为空怎么办？

**A:**
1. 检查板块名称是否正确（使用 search-sector 搜索）
2. 检查日期范围是否有数据
3. 检查 TUSHARE_TOKEN 是否有效

### Q3: 如何加快回测速度？

**A:**
1. 增加 `--workers` 并发数
2. 使用 `--use_processes` 多进程模式
3. 缩短回测日期范围
4. 减少股票数量

### Q4: 板块回测和单股票回测有什么区别？

**A:**

| 特性 | 单股票回测 | 板块回测 |
|------|-----------|---------|
| 股票数量 | 1 只 | 多只（最多 50） |
| 回测引擎 | 单进程 | 并行引擎 |
| 结果输出 | 详细报告 | 汇总表格 |
| 适用场景 | 深度分析 | 广度筛选 |

---

## 八、完整工作流示例

### 8.1 发现强势板块

```bash
# 1. 搜索人工智能相关板块
python -m quant_strategy.cli data search-sector --keyword "人工智能"

# 2. 回测该板块
python -m quant_strategy.cli sector-backtest \
    --strategy kdj \
    --sector_type concept \
    --sector_name 人工智能 \
    --start_date 20250101 \
    --end_date 20251231

# 3. 查看回测结果，找出表现最好的股票
# 输出中收益率排名前 5 的股票
```

### 8.2 板块轮动策略测试

```bash
# 1. 回测多个行业板块
for sector in "电子" "医药" "金融" "消费"; do
    python -m quant_strategy.cli sector-backtest \
        --strategy sector_momentum \
        --sector_type industry \
        --sector_name $sector \
        --start_date 20250101 \
        --end_date 20251231
done

# 2. 比较各板块表现
# 3. 选择表现最好的板块进行投资
```

---

## 九、注意事项

1. **板块数据时效性**
   - 板块成分股会定期调整
   - 回测使用的是当前成分股列表
   - 可能存在幸存者偏差

2. **数据质量**
   - 部分股票可能缺少历史数据
   - 停牌股票数据不完整
   - 建议使用缓存提高数据稳定性

3. **回测局限性**
   - 未考虑交易成本（已包含佣金和印花税）
   - 未考虑流动性限制
   - 历史表现不代表未来

---

## 十、相关文档

- `STRATEGY_IMPLEMENTATION.md` - 策略实施报告
- `DATA_SOURCE_CONFIG.md` - 数据源配置
- `ARCHITECTURE_REVIEW.md` - 架构 Review
