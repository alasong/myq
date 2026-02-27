# 增强版 AI 助手使用指南

## 概述

增强版 AI 助手支持：
- **多桶上下文机制**：独立的上下文空间，支持切换和持久化
- **Skill 插件系统**：可扩展的技能系统，支持自定义 Skill
- **复杂指令解析**：支持工作流、条件判断、循环、并行执行

## 启动方式

```bash
# 交互式模式
python -m quant_strategy.tools.ai_assistant_enhanced

# 单次命令模式
python -m quant_strategy.tools.ai_assistant_enhanced "下载 2025 年数据"

# 指定 Token
python -m quant_strategy.tools.ai_assistant_enhanced --token your_token_here

# 指定上下文保存路径
python -m quant_strategy.tools.ai_assistant_enhanced --context ~/.my_context.json
```

## 核心功能

### 1. 简单命令

直接执行单个任务：

```
> 下载 2025 年数据
> 查看缓存状态
> 清理缓存
> 更新数据
```

### 2. 工作流命令（多步骤）

使用分隔符连接多个步骤，顺序执行：

```
# 使用中文分隔符
> 下载 2024 年数据，然后清理缓存

# 使用符号分隔符
> 下载 2025 年数据 && 查看缓存

# 使用隐含分隔
> 先更新数据 再查看状态
```

**示例输出：**
```
收到命令：下载 2024 年数据，然后清理缓存
------------------------------------------------------------
指令类型：workflow
解析步骤：2
------------------------------------------------------------

执行结果:
============================================================
[步骤 1/2]
[OK] 成功下载 5012 只股票的数据

[步骤 2/2]
[OK] 清理完成！释放 128.45 MB 空间
============================================================
```

### 3. 条件命令

根据条件执行不同操作：

```
# 如果缓存大于 500MB，清理缓存
> 如果缓存大于 500MB，清理缓存

# 如果股票数量超过 1000，分批下载
> 如果股票数量超过 1000，分批下载
```

### 4. 变量定义

定义和使用变量：

```
# 定义股票代码
> 设 code = 000001.SZ，回测 code

# 定义日期范围
> set start = 20240101，下载 start 到 20241231 的数据

# 多个变量
> 设 code = 600519.SH，设 year = 2025，下载 year 年 code 的数据
```

### 5. 上下文桶

切换不同的上下文空间：

```
# 切换到回测上下文
> switch bucket backtest

# 切换到数据上下文
> switch bucket data

# 查看当前上下文
> context
```

## 内置 Skills

### 数据类 (data)

| Skill | 别名 | 描述 |
|-------|------|------|
| `download_data` | 下载数据，download, fetch | 下载股票数据 |
| `update_data` | 更新数据，update, refresh | 更新最近 N 天数据 |

**示例：**
```
> 下载 2025 年数据
> 下载 20240101-20241231 的股票 8 线程
> 批量下载全部股票
> 更新最近 30 天
```

### 缓存类 (cache)

| Skill | 别名 | 描述 |
|-------|------|------|
| `cache_status` | 查看缓存，状态，status | 查看缓存状态 |
| `cleanup_cache` | 清理缓存，cleanup, clean | 清理缓存 |

**示例：**
```
> 查看缓存状态
> 清理缓存
> 清理 7 天前的数据
```

### 回测类 (backtest)

| Skill | 别名 | 描述 |
|-------|------|------|
| `backtest` | 回测，策略回测 | 执行策略回测 |

**示例：**
```
> 回测双均线策略 000001.SZ 20240101-20241231
> 运行 KDJ 策略 茅台
```

### 分析类 (analysis)

| Skill | 别名 | 描述 |
|-------|------|------|
| `sector_analysis` | 板块分析，板块回测 | 板块回测分析 |

**示例：**
```
> 板块回测 银行 dual_ma
> 分析人工智能概念板块
```

## 高级用法

### 复杂工作流

```
# 下载数据 -> 查看状态 -> 清理旧数据
> 下载 2025 年数据，然后查看缓存状态，再清理 30 天前的缓存

# 条件工作流
> 如果缓存大于 1GB，清理缓存，否则查看状态
```

### 并行执行

```
# 同时下载多个年份
> 下载 2024 年数据 & 下载 2025 年数据
```

### 自定义 Skill

创建自定义 Skill：

```python
from quant_strategy.tools.skill_system import Skill, SkillDefinition, SkillResult

class MyCustomSkill(Skill):
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="my_custom_skill",
            description="我的自定义技能",
            aliases=["自定义", "my skill"],
            parameters={
                "param1": {"required": True, "description": "参数 1"},
            },
            examples=["使用自定义技能"],
            category="custom"
        )
    
    async def execute(self, context: Dict[str, Any], **kwargs) -> SkillResult:
        # 实现你的逻辑
        return SkillResult(success=True, message="执行完成")

# 注册 Skill
from quant_strategy.tools.skill_system import get_registry
registry = get_registry()
registry.register(MyCustomSkill())
```

## 命令参考

### 系统命令

| 命令 | 描述 |
|------|------|
| `help` | 显示帮助信息 |
| `help <skill>` | 显示指定 Skill 的帮助 |
| `skills` | 列出所有 Skills |
| `context` | 查看当前上下文 |
| `switch bucket <name>` | 切换上下文桶 |
| `quit` / `exit` / `q` | 退出 |

### 环境变量

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `TUSHARE_TOKEN` | Tushare API Token | 无 |

## 上下文持久化

上下文会自动保存到 `~/.qwen/ai_context.json`，可以通过 `--context` 参数指定其他路径。

```bash
# 使用自定义上下文路径
python -m quant_strategy.tools.ai_assistant_enhanced --context ./my_context.json
```

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                   AI Assistant                          │
├─────────────────────────────────────────────────────────┤
│  Command Parser  │  Context Manager  │  Skill Executor  │
├─────────────────────────────────────────────────────────┤
│                    Skill Registry                       │
├───────────┬───────────┬───────────┬─────────────────────┤
│  Data     │  Cache    │  Backtest │  Analysis Skills    │
│  Skills   │  Skills   │  Skills   │                     │
└───────────┴───────────┴───────────┴─────────────────────┘
```

## 故障排除

### 问题：命令无法识别

**解决：**
1. 检查是否输入正确的命令格式
2. 使用 `help` 查看支持的命令
3. 使用 `skills` 查看已注册的 Skills

### 问题：数据源未初始化

**解决：**
1. 设置 `TUSHARE_TOKEN` 环境变量
2. 或使用 `--token` 参数指定 Token

### 问题：上下文丢失

**解决：**
1. 检查上下文保存路径是否正确
2. 使用 `context` 命令查看当前上下文
3. 确保正常退出（输入 `quit`）

## 性能提示

1. **批量下载**：使用 `--workers` 参数增加并发数
2. **缓存利用**：启用缓存减少 API 调用
3. **上下文桶**：使用不同的桶隔离不同任务的上下文

---

**版本**: 2.0
**更新日期**: 2026-02-27
