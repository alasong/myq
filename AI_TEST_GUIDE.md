# AI 交互界面测试指南

## 概述

本测试套件覆盖 AI 交互界面的核心功能，包括命令解析、Skill 系统、上下文管理和安全防护。

## 运行测试

### 方式 1：直接运行
```bash
python quant_strategy/tools/test_ai_assistant.py
```

### 方式 2：使用 pytest
```bash
pytest quant_strategy/tools/test_ai_assistant.py -v
```

### 方式 3：运行特定测试类
```bash
python -m unittest quant_strategy.tools.test_ai_assistant.TestCommandParser -v
```

## 测试覆盖范围

### 1. 命令解析测试 (`TestCommandParser`)

测试 `CommandParser` 的解析能力：

| 测试项 | 描述 | 示例命令 |
|--------|------|----------|
| `test_simple_command` | 简单命令解析 | `下载 2025 年数据` |
| `test_workflow_command` | 工作流命令解析 | `下载 2024 年数据，然后清理缓存` |
| `test_conditional_command` | 条件命令解析 | `如果缓存大于 500MB，清理缓存` |
| `test_variable_definition` | 变量定义解析 | `设 code = 000001.SZ，回测 code` |
| `test_parallel_command` | 并行命令解析 | `下载 2024 年数据 & 下载 2025 年数据` |

### 2. 基础 AI 助手测试 (`TestAIAssistantBasic`)

测试 `AIAssistant` 的命令解析：

| 测试项 | 描述 | 测试内容 |
|--------|------|----------|
| `test_parse_year_command` | 年份命令解析 | 2025 年、2024 年、2023 年 |
| `test_parse_date_range_command` | 日期范围解析 | 20240101-20241231 |
| `test_parse_stock_code` | 股票代码解析 | 茅台、000001.SZ |
| `test_parse_workers` | 线程数解析 | 8 线程、4 线程 |
| `test_parse_special_keywords` | 特殊关键词 | 今年、去年、全部股票 |

### 3. 上下文管理测试 (`TestContextManager`)

测试 `ContextManager` 的多桶上下文：

| 测试项 | 描述 |
|--------|------|
| `test_basic_operations` | 基本设置/获取操作 |
| `test_bucket_operations` | 桶创建/切换操作 |
| `test_global_variables` | 全局变量操作 |
| `test_persistent_flag` | 持久化标志 |
| `test_clear_operations` | 清空操作（保留持久化变量） |

### 4. Skill 系统测试 (`TestSkillSystem`)

测试 `SkillRegistry` 和 `SkillExecutor`：

| 测试项 | 描述 |
|--------|------|
| `test_skill_registration` | Skill 注册和查找 |
| `test_skill_search` | Skill 搜索功能 |
| `test_skill_execution` | Skill 异步执行 |

### 5. 内置 Skills 测试 (`TestBuiltinSkills`)

测试内置 Skills 是否正确注册：

| 测试项 | 描述 |
|--------|------|
| `test_all_skills_registered` | 所有 Skills 已注册 |
| `test_skill_categories` | Skill 分类正确 |
| `test_skill_aliases` | Skill 别名可用 |

### 6. 安全防护测试 (`TestSafetyProtection`)

测试系统的安全防护能力：

| 测试项 | 描述 | 防护内容 |
|--------|------|----------|
| `test_empty_command` | 空命令处理 | 不崩溃 |
| `test_malicious_command` | 恶意命令防护 | 拒绝危险操作 |
| `test_invalid_date_format` | 无效日期处理 | 忽略或报错 |
| `test_resource_limits` | 资源限制 | 线程数 1-8 |
| `test_context_injection` | 注入攻击防护 | 特殊字符处理 |

### 7. 增强版 AI 助手测试 (`TestEnhancedAIAssistant`)

测试 `EnhancedAIAssistant` 的功能：

| 测试项 | 描述 |
|--------|------|
| `test_initialization` | 初始化检查 |
| `test_bucket_switching` | 桶切换功能 |
| `test_context_persistence` | 上下文持久化 |

## 测试结果

当前测试状态：**29/29 通过 (100%)**

```
======================================================================
测试报告
======================================================================
总测试数：29
成功：29
失败：0
错误：0
======================================================================
```

## 添加新测试

### 测试命令解析

```python
def test_new_command(self):
    """测试新命令"""
    result = self.parser.parse("你的新命令")
    self.assertEqual(result.type, InstructionType.XXX)
    # 添加断言...
```

### 测试新 Skill

```python
def test_new_skill(self):
    """测试新 Skill"""
    registry = get_registry()
    skill = registry.get('new_skill')
    self.assertIsNotNone(skill)
    
    # 测试执行
    import asyncio
    result = asyncio.run(executor.execute('new_skill', context, param=value))
    self.assertTrue(result.success)
```

### 测试安全防护

```python
def test_new_security_feature(self):
    """测试新安全功能"""
    # 尝试攻击
    result = self.assistant.parse_command("恶意命令")
    # 验证被拒绝或安全处理
    self.assertNotEqual(result['action'], 'download')
```

## 持续集成

### GitHub Actions 示例

```yaml
name: AI Assistant Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.10+
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run tests
        run: python quant_strategy/tools/test_ai_assistant.py
```

## 故障排除

### 问题：测试失败 "Tushare token 不能为空"

**解决：** 设置环境变量
```bash
export TUSHARE_TOKEN=your_token_here
```

### 问题：异步测试失败

**解决：** 确保使用 `asyncio.run()` 包装异步方法

### 问题：导入错误

**解决：** 确保项目根目录在 Python 路径中
```bash
export PYTHONPATH=$(pwd)
```

## 测试最佳实践

1. **隔离测试**：每个测试应该独立，不依赖其他测试的状态
2. **Mock 外部依赖**：使用 `unittest.mock` 模拟 Tushare API 等外部服务
3. **测试边界条件**：测试最小值、最大值、空值等
4. **命名规范**：使用 `test_` 前缀，描述性名称
5. **断言明确**：每个测试应该有明确的断言

## 扩展测试

### 性能测试

```python
def test_command_parse_performance(self):
    """测试命令解析性能"""
    import time
    
    start = time.time()
    for _ in range(1000):
        self.parser.parse("下载 2025 年数据")
    elapsed = time.time() - start
    
    # 1000 次解析应该小于 1 秒
    self.assertLess(elapsed, 1.0)
```

### 集成测试

```python
def test_full_workflow(self):
    """测试完整工作流"""
    # 1. 解析命令
    # 2. 执行 Skill
    # 3. 更新上下文
    # 4. 验证结果
    pass
```

---

**文档版本**: 1.0
**更新日期**: 2026-02-27
