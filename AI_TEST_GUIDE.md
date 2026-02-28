# AI 交互测试指南

## 概述

本测试套件覆盖 AI 交互界面的核心功能，包括命令解析、上下文管理、Skill 系统、模块系统和安全防护。

## 运行测试

### 方式 1：直接运行（推荐）
```bash
python quant_strategy/tools/test_ai_interaction.py
```

### 方式 2：使用 pytest
```bash
pytest quant_strategy/tools/test_ai_interaction.py -v
```

### 方式 3：运行特定测试类
```bash
python -m unittest quant_strategy.tools.test_ai_interaction.TestCommandParser -v
```

## 测试覆盖范围

### 1. 命令解析测试 (`TestCommandParser`)

测试 `CommandParser` 的解析能力：

| 测试项 | 描述 | 示例命令 |
|--------|------|----------|
| `test_simple_download_command` | 简单下载命令 | `下载 2025 年数据` |
| `test_date_range_command` | 日期范围命令 | `下载 20240101-20241231 的股票` |
| `test_stock_code_command` | 股票代码命令 | `下载 600519.SH 的数据` |
| `test_workers_command` | 线程数命令 | `下载 2025 年数据 8 线程` |
| `test_special_keywords` | 特殊关键词 | `今年`、`去年`、`全部股票` |

### 2. 上下文管理测试 (`TestContextManager`)

测试 `ContextManager` 的多桶上下文：

| 测试项 | 描述 |
|--------|------|
| `test_basic_set_get` | 基本设置/获取操作 |
| `test_bucket_operations` | 桶创建/切换操作 |
| `test_global_variables` | 全局变量操作 |
| `test_persistent_flag` | 持久化标志 |
| `test_clear_operations` | 清空操作（保留持久化变量） |

### 3. Skill 系统测试 (`TestSkillSystem`)

测试 `SkillRegistry` 和 `SkillExecutor`：

| 测试项 | 描述 |
|--------|------|
| `test_skill_registration` | Skill 注册和查找 |
| `test_skill_search` | Skill 搜索功能 |
| `test_skill_execution` | Skill 异步执行 |

### 4. 内置 Skills 测试 (`TestBuiltinSkills`)

测试内置 Skills 是否正确注册：

| 测试项 | 描述 |
|--------|------|
| `test_all_skills_registered` | 所有 Skills 已注册 |
| `test_skill_categories` | Skill 分类正确 |

### 5. 模块系统测试 (`TestModuleSystem`)

测试模块注册和功能：

| 测试项 | 描述 |
|--------|------|
| `test_registry_exists` | 注册表存在 |
| `test_data_module` | 数据模块 |
| `test_strategy_module` | 策略模块 |
| `test_module_actions` | 模块操作 |

### 6. AI 助手集成测试 (`TestAIAssistantIntegration`)

测试 `AIAssistantPro` 的功能：

| 测试项 | 描述 |
|--------|------|
| `test_initialization` | 初始化检查 |
| `test_parse_simple_command` | 解析简单命令 |
| `test_parse_stock_command` | 解析股票命令 |
| `test_parse_workers_command` | 解析线程数命令 |
| `test_module_command` | 模块命令解析 |

### 7. 安全防护测试 (`TestSafetyProtection`)

测试系统的安全防护能力：

| 测试项 | 描述 | 防护内容 |
|--------|------|----------|
| `test_empty_command` | 空命令处理 | 不崩溃 |
| `test_malicious_command` | 恶意命令防护 | 拒绝危险操作 |
| `test_resource_limits` | 资源限制 | 线程数限制 |
| `test_injection_attempts` | 注入攻击防护 | 特殊字符处理 |

### 8. 实际场景测试 (`TestRealWorldScenarios`)

测试实际使用场景：

| 测试项 | 描述 |
|--------|------|
| `test_scenario_download_year_data` | 下载某年数据 |
| `test_scenario_download_specific_stock` | 下载特定股票 |
| `test_scenario_batch_download` | 批量下载 |
| `test_scenario_update_data` | 更新数据 |
| `test_scenario_check_status` | 查看状态 |

### 9. 性能测试 (`TestPerformance`)

测试命令解析性能：

| 测试项 | 描述 | 目标 |
|--------|------|------|
| `test_parse_performance` | 1000 次解析 | < 1 秒 |

## 测试结果

当前测试状态：**34/34 通过 (100%)**

```
======================================================================
测试报告
======================================================================
总测试数：34
成功：34
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
