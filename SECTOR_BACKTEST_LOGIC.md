# 板块/概念回测逻辑详解

## 一、当前系统实现

### 1.1 实现方式：逐个股票回测

```
板块回测流程
┌─────────────────────────────────────────────────────────┐
│ 1. 获取板块成分股列表                                     │
│    - 行业板块：get_industry_stocks()                    │
│    - 概念板块：get_concept_stocks()                     │
│    - 地区板块：get_area_stocks()                        │
│    - 自定义：用户指定 ts_codes                           │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 2. 获取每只股票的历史数据                                 │
│    - data_dict[ts_code] = DataFrame                     │
│    - 限制最多 50 只股票（避免回测时间过长）                 │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 3. 并行回测每只股票（独立回测）                           │
│    - 每只股票独立运行完整的回测流程                       │
│    - 使用 ThreadPoolExecutor 或 ProcessPoolExecutor     │
│    - 默认多线程，可配置多进程                             │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 4. 汇总结果并排序                                        │
│    - 收集每只股票的回测结果                              │
│    - 按收益率排序                                        │
│    - 输出汇总表格                                        │
└─────────────────────────────────────────────────────────┘
```

### 1.2 代码实现

```python
# quant_strategy/backtester/parallel_engine.py

def backtest_sector(self, strategy_class, ts_codes, data_provider, ...):
    # 1. 获取所有股票数据
    data_dict = {}
    for ts_code in ts_codes:
        data = data_provider.get_daily_data(ts_code, start_date, end_date)
        if not data.empty:
            data_dict[ts_code] = data
    
    # 2. 创建回测任务
    tasks = []
    for ts_code, data in data_dict.items():
        tasks.append(BacktestTask(
            ts_code=ts_code,
            data=data,
            strategy_class=strategy_class,
            strategy_params=strategy_params,
            config=config
        ))
    
    # 3. 并行执行回测
    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
        futures = {executor.submit(_run_single_backtest, task): task 
                   for task in tasks}
        for future in as_completed(futures):
            result = future.result()
            results[result.ts_code] = result
    
    # 4. 汇总结果
    return results
```

### 1.3 特点分析

**优点：**
- ✅ 实现简单，易于理解
- ✅ 每只股票独立，结果可对比
- ✅ 支持并行，速度较快
- ✅ 可以发现板块内的强势股

**缺点：**
- ❌ 忽略股票间的相关性
- ❌ 没有考虑板块整体效应
- ❌ 无法模拟板块轮动策略
- ❌ 资金分配过于分散（假设每只股票独立建仓）

---

## 二、业界通常做法

### 2.1 方法一：等权组合回测（推荐）

**逻辑：**
```
1. 计算板块综合指数（等权或市值加权）
2. 对板块指数应用策略信号
3. 或者：每只股票产生信号后，综合投票决定板块信号
```

**实现示例：**
```python
class SectorPortfolioBacktester:
    def backtest(self, strategy, sector_stocks_data):
        # 方法 1: 等权组合
        portfolio_returns = {}
        for ts_code, data in sector_stocks_data.items():
            # 每只股票独立回测
            result = self.backtest_single(strategy, data)
            portfolio_returns[ts_code] = result
        
        # 计算组合收益（等权）
        daily_returns = pd.DataFrame({
            k: v.daily_values['daily_return'] 
            for k, v in portfolio_returns.items()
        })
        portfolio_return = daily_returns.mean(axis=1)  # 等权平均
        
        # 计算组合指标
        sharpe = portfolio_return.mean() / portfolio_return.std() * np.sqrt(252)
        total_return = (1 + portfolio_return).prod() - 1
        
        return {
            'portfolio_return': total_return,
            'sharpe_ratio': sharpe,
            'stock_results': portfolio_returns
        }
```

**适用场景：**
- 板块整体配置
- 分散投资风险
- 获取板块平均收益

---

### 2.2 方法二：龙头股回测

**逻辑：**
```
1. 识别板块龙头股（市值最大/成交量最大/涨幅最大）
2. 只对龙头股进行回测
3. 或者：龙头股 + 前 N 大权重股
```

**实现示例：**
```python
def select_sector_leaders(sector_stocks, top_n=5):
    """
    选择板块龙头股
    
    标准：
    1. 市值最大
    2. 成交量最大
    3. 板块内权重最高
    """
    # 获取股票市值数据
    market_caps = {}
    for ts_code in sector_stocks:
        info = get_stock_info(ts_code)
        market_caps[ts_code] = info['market_cap']
    
    # 选择前 N 大
    leaders = sorted(market_caps.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [ts_code for ts_code, _ in leaders]

# 回测
leaders = select_sector_leaders(sector_stocks, top_n=5)
results = backtest_sector(strategy, leaders)
```

**适用场景：**
- 龙头股策略
- 资金有限，无法配置全部成分股
- 关注板块代表性股票

---

### 2.3 方法三：板块轮动回测

**逻辑：**
```
1. 计算各板块动量/强度指标
2. 选择最强的 N 个板块
3. 买入选中板块的 ETF 或龙头股
4. 定期调仓（周/月）
```

**实现示例：**
```python
class SectorRotationBacktester:
    def __init__(self, lookback=20, top_k=3, rebalance_days=5):
        self.lookback = lookback  # 动量计算周期
        self.top_k = top_k        # 选择板块数量
        self.rebalance_days = rebalance_days  # 调仓周期
    
    def backtest(self, sector_data_dict):
        """
        sector_data_dict: {
            '电子': {stock_data},
            '医药': {stock_data},
            '金融': {stock_data},
            ...
        }
        """
        positions = {}  # 当前持仓板块
        daily_values = []
        
        for day in range(len(dates)):
            # 调仓日
            if day % self.rebalance_days == 0:
                # 计算各板块动量
                sector_momentum = {}
                for sector_name, stocks in sector_data_dict.items():
                    momentum = self.calculate_sector_momentum(stocks, day)
                    sector_momentum[sector_name] = momentum
                
                # 选择最强的板块
                top_sectors = sorted(
                    sector_momentum.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:self.top_k]
                
                positions = {name: 1.0/len(top_sectors) for name, _ in top_sectors}
            
            # 计算当日收益
            daily_return = 0
            for sector_name, weight in positions.items():
                sector_return = self.calculate_sector_return(
                    sector_data_dict[sector_name], day
                )
                daily_return += weight * sector_return
            
            daily_values.append(daily_return)
        
        return self.calculate_metrics(daily_values)
```

**适用场景：**
- 板块轮动策略
- 宏观配置策略
- 资金量大需要分散

---

### 2.4 方法四：信号聚合回测

**逻辑：**
```
1. 每只股票独立产生交易信号
2. 聚合所有信号（投票/加权）
3. 根据聚合信号交易板块 ETF 或一篮子股票
```

**实现示例：**
```python
def aggregate_signals(stock_signals):
    """
    信号聚合
    
    stock_signals: {
        '000001.SZ': Signal(BUY),
        '000002.SZ': Signal(HOLD),
        '000003.SZ': Signal(BUY),
        ...
    }
    """
    buy_count = sum(1 for s in stock_signals.values() if s == SignalType.BUY)
    sell_count = sum(1 for s in stock_signals.values() if s == SignalType.SELL)
    total = len(stock_signals)
    
    # 简单多数投票
    if buy_count > total * 0.6:  # 60% 以上股票买入
        return SignalType.BUY
    elif sell_count > total * 0.6:
        return SignalType.SELL
    else:
        return SignalType.HOLD

# 或者加权聚合
def weighted_aggregate_signals(stock_signals, weights):
    """按市值加权"""
    buy_score = sum(weights[ts] for ts, s in stock_signals.items() if s == SignalType.BUY)
    sell_score = sum(weights[ts] for ts, s in stock_signals.items() if s == SignalType.SELL)
    
    if buy_score > 0.6:
        return SignalType.BUY
    elif sell_score > 0.6:
        return SignalType.SELL
    else:
        return SignalType.HOLD
```

**适用场景：**
- 板块情绪判断
- 板块 ETF 交易
- 一篮子股票配置

---

## 三、方法对比

| 方法 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **当前：逐个回测** | 简单直接，可发现强势股 | 忽略相关性，资金分散 | 选股策略，板块内对比 |
| **等权组合** | 分散风险，代表板块 | 稀释龙头股收益 | 板块配置，分散投资 |
| **龙头股** | 聚焦核心，资金集中 | 可能错过补涨股 | 龙头策略，资金有限 |
| **板块轮动** | 捕捉板块机会，宏观配置 | 需要多板块数据 | 轮动策略，大类资产配置 |
| **信号聚合** | 反映板块整体情绪 | 个股差异被平均 | 板块 ETF 交易 |

---

## 四、改进建议

### 4.1 短期改进（1-2 天）

**添加组合回测模式：**
```python
# CLI 新增参数
python -m quant_strategy.cli sector-backtest \
    --strategy kdj \
    --sector_type concept \
    --sector_name 人工智能 \
    --mode portfolio  # 新增：individual(默认) | portfolio | leaders

# portfolio 模式：计算等权组合收益
# leaders 模式：只回测前 5 大龙头股
```

### 4.2 中期改进（1 周）

**实现板块轮动回测：**
```python
# 新增命令
python -m quant_strategy.cli sector-rotation \
    --strategy sector_momentum \
    --sectors 电子 医药 金融 消费 \
    --top_k 3 \
    --rebalance_days 5
```

### 4.3 长期改进（1 月）

**完整的组合管理框架：**
- 支持多板块配置
- 支持板块间资金分配
- 支持动态调仓
- 支持板块 ETF 回测

---

## 五、使用建议

### 5.1 当前系统的最佳实践

```bash
# 1. 了解板块内股票表现分布
python -m quant_strategy.cli sector-backtest \
    --strategy kdj \
    --sector_type industry \
    --sector_name 电子

# 2. 找出板块内表现最好的股票
# 查看输出结果中收益率排名前 5 的股票

# 3. 对选中的股票单独回测
python -m quant_strategy.cli backtest \
    --strategy kdj \
    --ts_code <选中的股票代码>
```

### 5.2 结合多种方法

```python
# 伪代码示例
def comprehensive_sector_analysis(sector_name):
    # 1. 获取板块成分股
    stocks = get_sector_stocks(sector_name)
    
    # 2. 逐个回测（当前实现）
    individual_results = backtest_individual(stocks)
    
    # 3. 计算等权组合收益
    portfolio_return = calculate_portfolio_return(individual_results)
    
    # 4. 找出龙头股
    leaders = select_leaders(stocks, top_n=5)
    leader_results = backtest_individual(leaders)
    
    # 5. 综合判断
    if portfolio_return > threshold and leader_results > threshold:
        return "板块值得配置"
    elif leader_results > portfolio_return:
        return "只配置龙头股"
    else:
        return "板块表现不佳"
```

---

## 六、总结

**当前实现：** 逐个股票回测，适合发现板块内强势股

**业界做法：**
1. **等权组合** - 分散风险，获取板块平均收益
2. **龙头股** - 聚焦核心，资金集中
3. **板块轮动** - 捕捉板块间机会
4. **信号聚合** - 反映板块整体情绪

**建议：** 根据投资策略选择合适的方法
- 选股策略 → 当前实现已足够
- 板块配置 → 需要等权组合或龙头股模式
- 轮动策略 → 需要板块轮动框架
