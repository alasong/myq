# 项目文档索引

## 📚 核心文档

### 入门指南
- **[README.md](README.md)** - 项目说明和快速开始

### 架构设计
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - 系统架构总览
- **[ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md)** - 架构审查报告

### 配置使用
- **[CONFIG_AND_MODE_GUIDE.md](CONFIG_AND_MODE_GUIDE.md)** - 配置和模式指南

### 数据管理
- **[DATA_FETCH_GUIDE.md](DATA_FETCH_GUIDE.md)** - 数据获取指南
- **[DATA_REVIEW_REPORT.md](DATA_REVIEW_REPORT.md)** - 数据审查报告
- **[DATA_FETCH_FIX_SUMMARY.md](DATA_FETCH_FIX_SUMMARY.md)** - 数据获取修复总结

### 存储优化
- **[STORAGE_OPTIMIZATION_COMPLETE.md](STORAGE_OPTIMIZATION_COMPLETE.md)** - 存储优化完成报告
- **[FINAL_STORAGE_STATUS.md](FINAL_STORAGE_STATUS.md)** - 最终存储状态
- **[SQLITE_UPGRADE_GUIDE.md](SQLITE_UPGRADE_GUIDE.md)** - SQLite 升级指南

### 策略实现
- **[STRATEGY_IMPLEMENTATION.md](STRATEGY_IMPLEMENTATION.md)** - 策略实现指南
- **[STRATEGY_MANAGER.md](STRATEGY_MANAGER.md)** - 策略管理器

### 板块回测
- **[SECTOR_BACKTEST_GUIDE.md](SECTOR_BACKTEST_GUIDE.md)** - 板块回测指南
- **[SECTOR_BACKTEST_LOGIC.md](SECTOR_BACKTEST_LOGIC.md)** - 板块回测逻辑

### AI 助手
- **[AI_ASSISTANT_GUIDE.md](AI_ASSISTANT_GUIDE.md)** - AI 助手使用指南

### 性能优化
- **[MULTITHREAD_GUIDE.md](MULTITHREAD_GUIDE.md)** - 多线程下载指南

### 故障排查
- **[AKSHARE_TROUBLESHOOTING.md](AKSHARE_TROUBLESHOOTING.md)** - AKShare 故障排查

---

## 🗂️ 项目结构

```
0226-myq/
├── quant_strategy/           # 核心代码
│   ├── data/                # 数据层
│   │   ├── tushare_provider.py    # Tushare 数据源
│   │   ├── akshare_provider.py    # AKShare 数据源
│   │   └── data_cache.py          # SQLite 缓存
│   ├── strategy/            # 策略层
│   ├── backtester/          # 回测引擎
│   ├── analyzer/            # 分析器
│   ├── optimizer/           # 优化器
│   ├── config/              # 配置
│   ├── tools/               # 工具
│   │   └── ai_assistant.py        # AI 助手
│   └── cli.py               # 命令行接口
├── configs/                 # 配置文件
├── data_cache/              # 数据缓存
│   ├── cache.db             # SQLite 数据库
│   ├── SSE/                 # 上交所数据
│   ├── SZSE/                 # 深交所数据
│   └── BJSE/                 # 北交所数据
├── logs/                    # 日志目录
├── output/                  # 输出目录
├── backup/                  # 备份目录
│   └── docs/                # 文档备份
└── docs/                    # 文档目录（本目录）
```

---

## 🚀 快速开始

### 1. 设置环境变量
```bash
set TUSHARE_TOKEN=your_token_here
```

### 2. 使用 AI 助手下载数据
```bash
# 交互式
python -m quant_strategy.tools.ai_assistant

# 单次命令
python -m quant_strategy.tools.ai_assistant "下载 2025 年数据"
```

### 3. 使用命令行
```bash
# 下载 2025 年数据（4 线程）
python -m quant_strategy.tools.fetch_all_stocks \
    --start 20250101 --end 20251231 \
    --workers 4
```

---

## 📊 核心功能

### 数据获取
- ✅ 支持 Tushare/AKShare 多数据源
- ✅ 本地 SQLite + Parquet 存储
- ✅ 按交易所分区（SSE/SZSE/BJSE）
- ✅ 多线程并发下载

### 回测引擎
- ✅ 向量化回测
- ✅ 并行回测
- ✅ 板块回测

### 策略管理
- ✅ 12+ 种基础策略
- ✅ 策略激活/停用
- ✅ 参数优化

### AI 助手
- ✅ 自然语言命令
- ✅ 智能日期识别
- ✅ 股票名称识别

---

## 📈 性能指标

| 指标 | 数值 |
|------|------|
| 元数据查询 | 5-10ms |
| 数据下载（4 线程） | ~25 分钟/5000 只 |
| 缓存命中率 | >95% |
| 存储大小 | ~140KB/股票 |

---

## 🔧 常用命令

### 数据下载
```bash
# AI 助手
python -m quant_strategy.tools.ai_assistant "下载 2025 年数据"

# 命令行
python -m quant_strategy.cli data fetch \
    --start 20250101 --end 20251231 \
    --workers 4
```

### 查看缓存
```bash
python -m quant_strategy.cli data list-cache
```

### 清理缓存
```bash
python -m quant_strategy.cli data clear
```

### 回测
```bash
python -m quant_strategy.cli backtest \
    --ts_code 600519.SH \
    --strategy dual_ma \
    --start 20250101 --end 20251231
```

---

## 📝 文档分类

### 必读文档 ⭐⭐⭐
- README.md
- ARCHITECTURE.md
- AI_ASSISTANT_GUIDE.md

### 参考文档 ⭐⭐
- CONFIG_AND_MODE_GUIDE.md
- DATA_FETCH_GUIDE.md
- STRATEGY_IMPLEMENTATION.md

### 高级文档 ⭐
- STORAGE_OPTIMIZATION_COMPLETE.md
- SQLITE_UPGRADE_GUIDE.md
- ARCHITECTURE_REVIEW.md

---

## 🎯 下一步

1. **阅读 README.md** - 了解项目
2. **设置 Token** - 配置 TUSHARE_TOKEN
3. **使用 AI 助手** - 下载数据
4. **运行回测** - 测试策略

---

**更新日期**: 2026-02-27  
**文档版本**: 1.0
