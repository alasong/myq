# 量化策略系统架构 Review 与策略分析

## 一、当前架构总览

### 1.1 系统分层架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    用户接口层 (CLI)                              │
│  cli.py - 12 个主要命令                                           │
├─────────────────────────────────────────────────────────────────┤
│                    应用层 (Application)                          │
│  main.py - 回测流程编排                                           │
├─────────────────────────────────────────────────────────────────┤
│                    数据层 (Data Layer)                           │
│  Tushare / AKShare / MultiSourceProvider / DataCache            │
├─────────────────────────────────────────────────────────────────┤
│                    策略层 (Strategy Layer)                       │
│  12 种策略实现 + 向量化支持 + 策略管理                             │
├─────────────────────────────────────────────────────────────────┤
│                    回测引擎层 (Backtest Engine)                  │
│  Backtester / VectorizedBacktester / ParallelBacktester        │
│  SimulatedBroker                                                │
├─────────────────────────────────────────────────────────────────┤
│                    分析层 (Analysis Layer)                       │
│  PerformanceAnalyzer / Visualizer / ReportExporter              │
├─────────────────────────────────────────────────────────────────┤
│                    优化层 (Optimizer Layer)                      │
│  ParamOptimizer (网格/随机/贝叶斯优化)                            │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 策略清单

| 策略代码 | 策略名称 | 类型 | 核心指标 | 状态 |
|---------|---------|------|---------|------|
| `dual_ma` | 双均线策略 | 趋势跟踪 | MA | ✅ 向量化 |
| `momentum` | 动量策略 | 动量 | RSI, Momentum | ⏳ 待优化 |
| `kdj` | KDJ 短线策略 | 超买超卖 | KDJ | ⏳ 待优化 |
| `rsi` | RSI 短线策略 | 超买超卖 | RSI | ⏳ 待优化 |
| `boll` | 布林线策略 | 均值回归 | Bollinger | ⏳ 待优化 |
| `dmi` | DMI 趋势策略 | 趋势强度 | DMI, ADX | ⏳ 待优化 |
| `cci` | CCI 顺势策略 | 超买超卖 | CCI | ⏳ 待优化 |
| `macd` | MACD 策略 | 趋势跟踪 | MACD | ⏳ 待优化 |
| `volume_price` | 量价策略 | 量价分析 | Volume, MA | ⏳ 待优化 |
| `market_breadth` | 市场广度策略 | 情绪 | ADR | ⏳ 待优化 |
| `limit_up` | 涨停情绪策略 | 情绪 | 涨停家数 | ⏳ 待优化 |
| `volume_sentiment` | 成交量情绪策略 | 情绪 | 成交量 | ⏳ 待优化 |
| `fear_greed` | 恐惧贪婪策略 | 情绪 | 综合情绪 | ⏳ 待优化 |
| `open_interest` | 开盘情绪策略 | 情绪 | 跳空缺口 | ⏳ 待优化 |

**策略状态图例：**
- ✅ 已向量化优化
- ⏳ 待向量化优化

---

## 二、板块轮动策略分析

### 2.1 当前支持情况

**现有功能：**
- ✅ 板块数据获取（行业/概念/地区）
- ✅ 板块成分股查询
- ✅ 板块回测命令 (`sector-backtest`)
- ✅ 多股票并行回测

**缺失功能：**
- ❌ 板块强度计算
- ❌ 板块资金流向
- ❌ 板块轮动信号生成
- ❌ 板块切换逻辑

### 2.2 成熟的板块轮动策略方案

#### 方案 1：动量轮动策略

```python
class SectorRotationStrategy(BaseStrategy):
    """
    板块动量轮动策略
    
    核心逻辑：
    1. 计算各板块 N 日动量
    2. 选择动量最强的 TopK 板块
    3. 买入板块内龙头股
    4. 定期调仓（周/月）
    """
    
    def __init__(self, lookback=20, top_k=3, rebalance_days=5):
        self.lookback = lookback      # 动量计算周期
        self.top_k = top_k            # 选择前 K 个板块
        self.rebalance_days = rebalance_days  # 调仓周期
    
    def calculate_sector_momentum(self, sector_data):
        """计算板块动量"""
        momentum = {}
        for sector_name, stocks in sector_data.items():
            # 计算板块等权收益
            returns = []
            for stock_df in stocks.values():
                ret = stock_df['close'].pct_change(self.lookback).iloc[-1]
                returns.append(ret)
            momentum[sector_name] = np.mean(returns)
        return momentum
    
    def generate_signal(self, data, idx):
        # 实现板块选择和个股买入逻辑
        pass
```

#### 方案 2：资金流向轮动

```python
class SectorFlowStrategy(BaseStrategy):
    """
    板块资金流向策略
    
    核心逻辑：
    1. 监控主力资金净流入
    2. 识别资金持续流入的板块
    3. 跟随主力资金布局
    """
    
    def calculate_net_inflow(self, stock_data):
        """计算主力资金净流入"""
        # 基于成交量和价格变化估算
        pass
```

#### 方案 3：RSRS 板块轮动

```python
class SectorRSRSStrategy(BaseStrategy):
    """
    基于 RSRS 指标的板块轮动
    
    RSRS (阻力支撑相对强度) 指标：
    - 计算板块指数相对于大盘的 RSRS
    - RSRS 上升时超配该板块
    """
```

### 2.3 建议实施的板块轮动策略

**优先级 1：动量轮动（1-2 天实施）**

```python
# quant_strategy/strategy/sector_rotation.py

class SectorMomentumRotationStrategy(VectorizedStrategy):
    """
    板块动量轮动策略（向量化版本）
    
    特征：
    - 计算板块动量排名
    - 自动选择强势板块
    - 板块内选股逻辑
    """
    
    def __init__(self, 
                 lookback=20,      # 动量周期
                 top_k=3,          # 选择板块数
                 hold_period=5,    # 持有期
                 sector_type='industry'):  # 板块类型
        super().__init__()
        self.lookback = lookback
        self.top_k = top_k
        self.hold_period = hold_period
        self.sector_type = sector_type
        self.sector_data = {}
        self.current_sector = None
        self.days_held = 0
    
    def set_sector_data(self, sector_data):
        """设置板块数据"""
        self.sector_data = sector_data
    
    def generate_signals_vectorized(self, data):
        # 向量化实现板块动量计算和选股
        pass
```

**优先级 2：资金流向（3-5 天实施）**

需要数据支持：
- 主力资金流向数据（Tushare 需要积分）
- 北向资金数据
- 大单净流入数据

---

## 三、打板策略分析

### 3.1 当前支持情况

**现有功能：**
- ✅ 涨停判断逻辑（`sentiment.py` 中有限实现）
- ✅ 涨停家数统计
- ✅ 涨停情绪指标

**缺失功能：**
- ❌ 涨停板复盘
- ❌ 连板股识别
- ❌ 打板买入逻辑
- ❌ 炸板风险管理
- ❌ 龙虎板分析

### 3.2 成熟的打板策略方案

#### 方案 1：首板策略

```python
class FirstLimitUpStrategy(BaseStrategy):
    """
    首板打板策略
    
    核心逻辑：
    1. 识别首次涨停股票
    2. 分析涨停质量（封单量、封板时间）
    3. 次日高开时买入
    4. 快进快出（1-3 天）
    """
    
    def __init__(self, 
                 min_close_ratio=0.095,  # 涨停阈值
                 min_volume_ratio=1.5,   # 最小放量倍数
                 hold_days=2):           # 持有期
        self.min_close_ratio = min_close_ratio
        self.min_volume_ratio = min_volume_ratio
        self.hold_days = hold_days
    
    def is_limit_up(self, data, idx):
        """判断是否涨停"""
        close = data.iloc[idx]['close']
        prev_close = data.iloc[idx-1]['close']
        pct = (close - prev_close) / prev_close
        return pct >= self.min_close_ratio
    
    def is_first_limit_up(self, data, idx, lookback=10):
        """判断是否为首板"""
        # 检查前 lookback 天内无涨停
        for i in range(idx-lookback, idx):
            if self.is_limit_up(data, i):
                return False
        return True
    
    def generate_signal(self, data, idx):
        # 首板识别和买入逻辑
        pass
```

#### 方案 2：连板策略

```python
class ContinuousLimitUpStrategy(BaseStrategy):
    """
    连板打板策略
    
    核心逻辑：
    1. 识别 N 连板股票
    2. 在 N 板时打板买入
    3. 持有至开板或达到目标收益
    """
    
    def __init__(self, 
                 target_continuous=2,  # 目标连板数
                 max_hold_days=5):     # 最大持有期
        self.target_continuous = target_continuous
        self.max_hold_days = max_hold_days
    
    def count_continuous_limit_up(self, data, idx):
        """计算连续涨停天数"""
        count = 0
        for i in range(idx, max(0, idx-10), -1):
            if self.is_limit_up(data, i):
                count += 1
            else:
                break
        return count
```

#### 方案 3：涨停回马枪

```python
class LimitUpPullbackStrategy(BaseStrategy):
    """
    涨停回马枪策略
    
    核心逻辑：
    1. 识别近期涨停股（5-10 天内）
    2. 等待回调至支撑位
    3. 回调企稳后买入
    4. 博弈第二波拉升
    """
```

#### 方案 4：集合竞价打板

```python
class CallAuctionLimitUpStrategy(BaseStrategy):
    """
    集合竞价打板策略
    
    核心逻辑：
    1. 监控集合竞价（9:15-9:25）
    2. 识别强势股（高开 + 放量）
    3. 9:25 分前挂单
    4. 当日博弈涨停
    """
    
    def __init__(self,
                 min_open_pct=0.03,    # 最小高开幅度
                 min_volume_ratio=2.0, # 集合竞价量比
                 target_profit=0.07):  # 目标收益
        self.min_open_pct = min_open_pct
        self.min_volume_ratio = min_volume_ratio
        self.target_profit = target_profit
```

### 3.3 建议实施的打板策略

**优先级 1：首板策略（2-3 天实施）**

```python
# quant_strategy/strategy/limit_up_strategy.py

class FirstLimitUpStrategy(VectorizedStrategy):
    """
    首板打板策略（向量化版本）
    
    特征：
    - 识别首次涨停
    - 封板质量评分
    - 次日买入信号
    """
    
    def __init__(self,
                 min_close_ratio=0.095,
                 min_volume_ratio=1.5,
                 min_market_cap=50,    # 最小市值（亿）
                 exclude_st=True):     # 排除 ST
        super().__init__()
        self.min_close_ratio = min_close_ratio
        self.min_volume_ratio = min_volume_ratio
        self.min_market_cap = min_market_cap
        self.exclude_st = exclude_st
    
    def generate_signals_vectorized(self, data):
        # 向量化涨停识别
        pass
    
    def quality_score(self, data, idx):
        """涨停质量评分"""
        score = 0
        # 封单量评分
        # 封板时间评分
        # 成交量评分
        return score
```

**优先级 2：连板策略（3-5 天实施）**

需要数据支持：
- 实时涨停板数据
- 封单量数据
- 龙虎榜数据

---

## 四、架构优缺点分析

### 4.1 优点

| 方面 | 描述 |
|------|------|
| **分层清晰** | 数据层/策略层/回测层/分析层职责明确 |
| **可扩展性** | 策略模式 + 工厂模式，易于添加新策略 |
| **性能优化** | 向量化引擎 + 多数据源 + 缓存机制 |
| **策略管理** | 支持策略激活/停用管理 |
| **数据源** | 支持 Tushare/AKShare 多数据源自动切换 |
| **CLI 友好** | 丰富的命令行接口 |

### 4.2 缺点

| 问题 | 影响 | 建议 |
|------|------|------|
| **策略数量少** | 仅 12 种基础策略 | 增加板块轮动/打板策略 |
| **部分策略未向量化** | 回测速度不一致 | 继续重构剩余策略 |
| **无实时数据** | 仅支持历史回测 | 考虑接入实时行情 |
| **无组合管理** | 单股票/板块回测 | 增加组合优化功能 |
| **无风险控制** | 缺少止损/仓位管理 | 增加风控模块 |
| **无事件驱动** | 不支持事件回测 | 考虑接入事件数据 |

### 4.3 架构风险

```
┌─────────────────────────────────────────────────────────┐
│  高风险                                                  │
│  - Tushare 依赖（积分限制）→ 已解决：多数据源            │
│  - 网络依赖（API 调用）→ 已解决：本地缓存                │
├─────────────────────────────────────────────────────────┤
│  中风险                                                  │
│  - 策略同质化（技术指标为主）→ 建议：增加另类数据        │
│  - 回测过拟合风险 → 建议：增加样本外测试                 │
├─────────────────────────────────────────────────────────┤
│  低风险                                                  │
│  - 代码复杂度 → 当前架构清晰                            │
│  - 依赖管理 → 依赖较少且成熟                            │
└─────────────────────────────────────────────────────────┘
```

---

## 五、改进建议与实施计划

### 5.1 短期（1-2 周）

| 任务 | 优先级 | 工作量 | 收益 |
|------|--------|--------|------|
| 板块动量轮动策略 | P0 | 2 天 | 高 |
| 首板打板策略 | P0 | 2 天 | 高 |
| 剩余策略向量化 | P1 | 3 天 | 中 |
| 止损/止盈机制 | P1 | 1 天 | 高 |

### 5.2 中期（1-2 月）

| 任务 | 优先级 | 工作量 | 收益 |
|------|--------|--------|------|
| 连板策略 | P0 | 3 天 | 高 |
| 资金流向分析 | P1 | 5 天 | 中 |
| 组合优化模块 | P1 | 5 天 | 中 |
| 样本外测试 | P2 | 3 天 | 中 |

### 5.3 长期（3-6 月）

| 任务 | 优先级 | 工作量 | 收益 |
|------|--------|--------|------|
| 实时行情接入 | P1 | 2 周 | 高 |
| 事件驱动回测 | P2 | 3 周 | 中 |
| 机器学习策略 | P2 | 4 周 | 高 |
| 分布式回测 | P3 | 4 周 | 中 |

---

## 六、策略实施示例

### 6.1 板块动量轮动策略

```python
# quant_strategy/strategy/sector_rotation.py

import pandas as pd
import numpy as np
from typing import Dict, List

from .base_strategy import BaseStrategy, Signal, SignalType
from .vectorized_strategy import VectorizedStrategy, SignalGenerator


class SectorMomentumRotationStrategy(VectorizedStrategy):
    """
    板块动量轮动策略
    
    逻辑：
    1. 计算各板块 N 日动量
    2. 选择动量最强的 TopK 板块
    3. 买入板块内龙头股（市值最大/流动性最好）
    4. 定期调仓
    """
    
    def __init__(self,
                 lookback: int = 20,      # 动量计算周期
                 top_k: int = 3,          # 选择板块数量
                 rebalance_days: int = 5,  # 调仓周期
                 sector_type: str = 'industry'):  # 板块类型
        super().__init__()
        self.lookback = lookback
        self.top_k = top_k
        self.rebalance_days = rebalance_days
        self.sector_type = sector_type
        
        # 板块数据
        self.sector_stocks: Dict[str, List[str]] = {}
        self.stock_sector_map: Dict[str, str] = {}
        
        # 状态
        self.current_sectors = []
        self.days_since_rebalance = 0
    
    def set_sector_data(self, sector_stocks: Dict[str, List[str]]):
        """
        设置板块成分股数据
        
        Args:
            sector_stocks: {板块名：[股票代码列表]}
        """
        self.sector_stocks = sector_stocks
        # 构建股票→板块映射
        for sector, stocks in sector_stocks.items():
            for stock in stocks:
                self.stock_sector_map[stock] = sector
    
    def calculate_sector_momentum(self, 
                                   sector_data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """
        计算各板块动量
        
        Args:
            sector_data: {股票代码：DataFrame}
            
        Returns:
            {板块名：动量值}
        """
        momentum = {}
        
        for sector, stocks in self.sector_stocks.items():
            sector_returns = []
            
            for stock in stocks:
                if stock in sector_data:
                    df = sector_data[stock]
                    if len(df) >= self.lookback:
                        # 计算 N 日收益
                        ret = df['close'].pct_change(self.lookback).iloc[-1]
                        if not np.isnan(ret):
                            sector_returns.append(ret)
            
            if sector_returns:
                # 板块等权平均收益
                momentum[sector] = np.mean(sector_returns)
        
        return momentum
    
    def select_top_sectors(self, momentum: Dict[str, float]) -> List[str]:
        """选择动量最强的 TopK 板块"""
        sorted_sectors = sorted(momentum.items(), 
                                key=lambda x: x[1], 
                                reverse=True)
        return [s[0] for s in sorted_sectors[:self.top_k]]
    
    def select_stock_in_sector(self, 
                                sector: str,
                                sector_data: Dict[str, pd.DataFrame]) -> str:
        """
        选择板块内股票（简单实现：选择市值最大/流动性最好）
        
        实际使用中可结合：
        - 市值因子
        - 流动性因子
        - 个股动量
        """
        stocks = self.sector_stocks.get(sector, [])
        
        # 简单实现：选择成交量最大的
        best_stock = None
        best_volume = 0
        
        for stock in stocks:
            if stock in sector_data:
                df = sector_data[stock]
                avg_volume = df['vol'].iloc[-self.lookback:].mean()
                if avg_volume > best_volume:
                    best_volume = avg_volume
                    best_stock = stock
        
        return best_stock
    
    def generate_signals_vectorized(self, data):
        """向量化信号生成"""
        # 此策略需要多股票数据，不适合纯向量化
        # 在 backtest_sector 中特殊处理
        pass
    
    def generate_signal_bar(self, data, idx):
        """逐 bar 模式（用于板块回测）"""
        # 检查是否需要调仓
        if self.days_since_rebalance >= self.rebalance_days:
            # 重新计算动量并选择板块
            # 这里需要访问全市场数据，由回测引擎提供
            self.days_since_rebalance = 0
        else:
            self.days_since_rebalance += 1
        
        # 生成信号
        return Signal(
            signal_type=SignalType.HOLD,
            price=data.iloc[idx]['close'],
            reason="等待板块数据"
        )
```

### 6.2 首板打板策略

```python
# quant_strategy/strategy/limit_up_strategy.py

import pandas as pd
import numpy as np
from typing import Dict, List

from .base_strategy import BaseStrategy, Signal, SignalType
from .vectorized_strategy import VectorizedStrategy, SignalGenerator


class FirstLimitUpStrategy(VectorizedStrategy):
    """
    首板打板策略
    
    逻辑：
    1. 识别首次涨停股票
    2. 分析涨停质量（封单量、封板时间、成交量）
    3. 次日高开时买入
    4. 快进快出（1-3 天）
    """
    
    def __init__(self,
                 min_close_ratio: float = 0.095,  # 涨停阈值
                 min_volume_ratio: float = 1.5,   # 最小放量倍数
                 min_market_cap: float = 50,      # 最小市值（亿）
                 max_market_cap: float = 500,     # 最大市值（亿）
                 exclude_st: bool = True,         # 排除 ST
                 hold_days: int = 2,              # 持有期
                 stop_loss: float = 0.05,         # 止损线
                 take_profit: float = 0.15):      # 止盈线
        super().__init__()
        self.min_close_ratio = min_close_ratio
        self.min_volume_ratio = min_volume_ratio
        self.min_market_cap = min_market_cap
        self.max_market_cap = max_market_cap
        self.exclude_st = exclude_st
        self.hold_days = hold_days
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        
        # 状态
        self.limit_up_stocks = set()
        self.holding_days = 0
    
    def is_limit_up(self, data, idx) -> bool:
        """判断是否涨停"""
        close = data.iloc[idx]['close']
        prev_close = data.iloc[idx-1]['close'] if idx > 0 else close
        pct = (close - prev_close) / prev_close
        return pct >= self.min_close_ratio
    
    def is_first_limit_up(self, data, idx, lookback=10) -> bool:
        """判断是否为首板"""
        for i in range(idx-lookback, idx):
            if i >= 0 and self.is_limit_up(data, i):
                return False
        return True
    
    def check_volume(self, data, idx) -> bool:
        """检查成交量是否放量"""
        current_vol = data.iloc[idx]['vol']
        avg_vol = data.iloc[idx-5:idx]['vol'].mean() if idx >= 5 else current_vol
        return current_vol >= avg_vol * self.min_volume_ratio
    
    def quality_score(self, data, idx) -> float:
        """
        涨停质量评分（0-1）
        
        评分维度：
        - 封板时间（越早越好）
        - 封单量（越大越好）
        - 成交量（适度放量）
        - 市值（中小市值优先）
        """
        score = 0.5
        
        # 成交量评分
        current_vol = data.iloc[idx]['vol']
        avg_vol = data.iloc[idx-5:idx]['vol'].mean()
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1
        
        if 1.5 <= vol_ratio <= 5:
            score += 0.2
        elif vol_ratio > 5:
            score += 0.1
        
        # 涨停幅度评分（20% 优于 10%）
        close = data.iloc[idx]['close']
        prev_close = data.iloc[idx-1]['close']
        pct = (close - prev_close) / prev_close
        
        if pct >= 0.19:
            score += 0.2
        elif pct >= 0.095:
            score += 0.1
        
        return min(score, 1.0)
    
    def generate_signals_vectorized(self, data):
        """向量化信号生成"""
        n = len(data)
        signals = np.full(n, SignalType.HOLD.value, dtype=object)
        strengths = np.full(n, 0.5)
        reasons = [''] * n
        
        # 遍历识别首板
        for i in range(1, n):
            if self.is_limit_up(data, i):
                if self.is_first_limit_up(data, i):
                    if self.check_volume(data, i):
                        quality = self.quality_score(data, i)
                        
                        if quality >= 0.6:
                            # 次日买入信号
                            if i + 1 < n:
                                signals[i+1] = SignalType.BUY.value
                                strengths[i+1] = quality
                                reasons[i+1] = f"首板质量评分={quality:.2f}"
        
        from .vectorized_strategy import VectorizedSignal
        return VectorizedSignal(
            signal_types=signals,
            strengths=strengths,
            reasons=reasons
        )
    
    def generate_signal_bar(self, data, idx):
        """逐 bar 模式"""
        if idx < 2:
            return Signal(SignalType.HOLD, data.iloc[idx]['close'])
        
        # 检查昨日是否首板
        if self.is_limit_up(data, idx-1):
            if self.is_first_limit_up(data, idx-1):
                if self.check_volume(data, idx-1):
                    quality = self.quality_score(data, idx-1)
                    
                    if quality >= 0.6:
                        # 检查今日是否高开
                        open_price = data.iloc[idx]['open']
                        prev_close = data.iloc[idx-1]['close']
                        open_pct = (open_price - prev_close) / prev_close
                        
                        if open_pct >= 0.01:  # 高开 1% 以上
                            return Signal(
                                signal_type=SignalType.BUY,
                                price=open_price,
                                strength=quality,
                                reason=f"首板高开{open_pct:.2%}"
                            )
        
        # 持有期检查
        if self.holding_days > 0:
            self.holding_days += 1
            
            # 止盈止损检查
            current_price = data.iloc[idx]['close']
            cost_price = self.entry_price if hasattr(self, 'entry_price') else current_price
            pnl_pct = (current_price - cost_price) / cost_price
            
            if pnl_pct <= -self.stop_loss:
                self.holding_days = 0
                return Signal(SignalType.SELL, current_price, reason="止损")
            
            if pnl_pct >= self.take_profit:
                self.holding_days = 0
                return Signal(SignalType.SELL, current_price, reason="止盈")
            
            if self.holding_days >= self.hold_days:
                self.holding_days = 0
                return Signal(SignalType.SELL, current_price, reason="到期")
        
        return Signal(SignalType.HOLD, data.iloc[idx]['close'])
```

---

## 七、总结

### 当前架构评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构设计 | ⭐⭐⭐⭐⭐ | 分层清晰，扩展性好 |
| 策略丰富度 | ⭐⭐⭐ | 基础策略齐全，缺少特色策略 |
| 性能优化 | ⭐⭐⭐⭐⭐ | 向量化 + 多数据源 + 缓存 |
| 易用性 | ⭐⭐⭐⭐ | CLI 友好，文档完善 |
| 生产就绪 | ⭐⭐⭐ | 缺少风控/实时监控 |

### 核心建议

1. **立即实施**：板块动量轮动 + 首板打板策略
2. **短期完善**：剩余策略向量化 + 止损机制
3. **中期规划**：连板策略 + 资金流向分析
4. **长期愿景**：实时行情 + 事件驱动 + 机器学习
