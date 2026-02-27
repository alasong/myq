# 量化策略系统使用指南

> 系统架构：AI 交互界面 + 模块化设计

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 设置 Token

```bash
# Windows
set TUSHARE_TOKEN=your_token_here

# Linux/Mac
export TUSHARE_TOKEN=your_token_here
```

### 3. 启动 AI 助手

```bash
python -m quant_strategy.cli ai
```

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    统一入口 (cli.py)                         │
│  ai | module | backtest | data                               │
├─────────────────────────────────────────────────────────────┤
│                    AI 交互界面                                │
│  ai_assistant_pro.py                                        │
│  - 自然语言解析                                              │
│  - 模块调用路由                                              │
│  - 上下文管理                                                │
├─────────────────────────────────────────────────────────────┤
│                    模块系统                                   │
│  modules/                                                   │
│  ├── base.py           # 模块基类                            │
│  ├── data_module.py    # 数据查看模块                        │
│  └── strategy_module.py # 策略查看模块                       │
├─────────────────────────────────────────────────────────────┤
│                    工具系统                                   │
│  tools/                                                     │
│  ├── skill_system.py     # Skill 插件框架                    │
│  ├── command_parser.py   # 命令解析器                        │
│  └── context_bucket.py   # 上下文管理                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 使用方式

### 方式 1：AI 交互模式（推荐）

最自然的使用方式，支持中文命令。

```bash
# 启动交互模式
python -m quant_strategy.cli ai

# 单次命令
python -m quant_strategy.cli ai -c "下载 2025 年数据"
```

**支持的命令：**

| 类型 | 命令示例 | 说明 |
|------|----------|------|
| 自然语言 | `下载 2025 年数据` | 下载指定年份数据 |
| 自然语言 | `查看缓存状态` | 查看缓存统计 |
| 模块调用 | `data:list-stocks` | 列出股票 |
| 模块调用 | `strategy:info name=dual_ma` | 查看策略详情 |
| 系统命令 | `help` | 显示帮助 |
| 系统命令 | `modules` | 列出模块 |
| 系统命令 | `quit` | 退出 |

### 方式 2：模块直接调用

适合脚本和自动化任务。

```bash
# 查看股票列表
python -m quant_strategy.cli module data:list-stocks

# 查看股票详情
python -m quant_strategy.cli module data:stock-info ts_code=000001.SZ

# 查看策略列表
python -m quant_strategy.cli module strategy:list

# 查看策略配置
python -m quant_strategy.cli module strategy:config name=dual_ma

# 查看回测历史
python -m quant_strategy.cli module strategy:history
```

### 方式 3：命令行回测

```bash
# 运行回测
python -m quant_strategy.cli backtest --strategy dual_ma --ts_code 000001.SZ

# 指定日期范围
python -m quant_strategy.cli backtest --strategy kdj --ts_code 000001.SZ \
    --start-date 20240101 --end-date 20241231
```

### 方式 4：数据管理

```bash
# 下载数据
python -m quant_strategy.cli data download --ts_codes 000001.SZ \
    --start_date 20240101 --end_date 20241231

# 查看缓存状态
python -m quant_strategy.cli data cache status

# 清理缓存
python -m quant_strategy.cli data cache clear
```

---

## 模块系统

### 内置模块

#### 1. data - 数据查看模块

| 操作 | 命令 | 说明 |
|------|------|------|
| `list-stocks` | `data:list-stocks limit=50` | 列出股票 |
| `stock-info` | `data:stock-info ts_code=000001.SZ` | 股票详情 |
| `list-sectors` | `data:list-sectors sector_type=industry` | 列出板块 |
| `sector-stocks` | `data:sector-stocks sector_name=银行` | 板块成分 |
| `cache-status` | `data:cache-status` | 缓存状态 |
| `cache-stats` | `data:cache-stats` | 缓存统计 |

#### 2. strategy - 策略查看模块

| 操作 | 命令 | 说明 |
|------|------|------|
| `list` | `strategy:list` | 列出策略 |
| `info` | `strategy:info name=dual_ma` | 策略详情 |
| `config` | `strategy:config name=dual_ma` | 策略配置 |
| `history` | `strategy:history ts_code=000001.SZ` | 回测历史 |
| `backtest-info` | `strategy:backtest-info backtest_id=xxx` | 回测详情 |
| `compare` | `strategy:compare strategies=['dual_ma','kdj']` | 策略对比 |

### 自定义模块

创建新模块：

```python
# my_module.py
from quant_strategy.modules import BaseModule, ModuleInfo, ModuleType, ModuleResult, register_module

@register_module("my_module")
class MyModule(BaseModule):
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="my_module",
            module_type=ModuleType.CUSTOM,
            description="我的自定义模块",
            tags=["自定义"]
        )
    
    def get_actions(self) -> List[str]:
        return ["action1", "action2"]
    
    def execute(self, action: str, **kwargs) -> ModuleResult:
        if action == "action1":
            return ModuleResult(success=True, message="执行成功")
        return ModuleResult(success=False, message="未知操作")
```

---

## AI 助手界面

### 界面元素

```
╔══════════════════════════════════════════════════════════╗
║           AI 股票数据助手 专业版 v2.0                     ║
╚══════════════════════════════════════════════════════════╝

[*] 正在初始化...
[+] 初始化完成

[>>] 下载 2025 年数据
────────────────────────────────────────────────────────────
[*] 日期范围：20250101 - 20251231
[*] 并发线程：4
[*] 获取全部股票列表...
[+] 全部股票：5485 只
[*] 开始下载...
[+] 下载完成！
```

### 状态指示器

| 图标 | 含义 |
|------|------|
| `[*]` | 信息 |
| `[+]` | 成功 |
| `[-]` | 错误 |
| `[!]` | 警告 |
| `[...]` | 加载中 |

---

## 配置管理

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TUSHARE_TOKEN` | Tushare API Token | 无 |
| `PYTHONIOENCODING` | 输出编码 | utf-8 |

### 策略配置

策略配置文件保存在 `configs/strategies/` 目录：

```yaml
# configs/strategies/dual_ma.yaml
short_window: 5
long_window: 20
```

---

## 开发指南

### 添加新模块

1. 在 `quant_strategy/modules/` 创建模块文件
2. 使用 `@register_module` 装饰器
3. 继承 `BaseModule` 基类
4. 实现 `info` 属性和 `execute` 方法

### 添加新 Skill

1. 继承 `Skill` 基类
2. 实现 `definition` 属性和 `execute` 方法
3. 在 `builtin_skills.py` 中注册

### 测试

```bash
# 运行测试
python quant_strategy/tools/test_ai_assistant.py

# 使用 pytest
pytest quant_strategy/tools/test_ai_assistant.py -v
```

---

## 故障排除

### 问题：TUSHARE_TOKEN 未设置

**解决：**
```bash
set TUSHARE_TOKEN=your_token_here
```

### 问题：模块未找到

**解决：**
```bash
# 查看已注册模块
python -m quant_strategy.cli module data:list
# 或
modules
```

### 问题：缓存为空

**解决：**
```bash
# 下载数据
python -m quant_strategy.cli ai -c "下载 2024 年数据"
```

---

## 性能优化

1. **启用缓存**：减少 API 调用
2. **多线程下载**：`--workers 8`
3. **批量操作**：使用模块命令而非多次调用

---

**版本**: 2.0.0  
**更新日期**: 2026-02-27
