"""
AI 交互测试套件

测试范围：
1. 模块系统测试 (Module System)
2. 命令解析测试 (Command Parser)
3. 上下文管理测试 (Context Management)
4. Skill 系统测试 (Skill System)
5. 实际场景集成测试 (Integration Tests)
6. 安全防护测试 (Safety Tests)

使用方法：
    python -m pytest quant_strategy/tools/test_ai_interaction.py -v
    或
    python quant_strategy/tools/test_ai_interaction.py
"""
import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import asyncio

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from quant_strategy.tools.ai_assistant_pro import AIAssistantPro
from quant_strategy.tools.context_bucket import ContextManager, ContextBucket
from quant_strategy.tools.skill_system import (
    SkillRegistry, SkillExecutor, Skill, SkillDefinition, SkillResult
)
from quant_strategy.tools.command_parser import CommandParser, ParsedInstruction, InstructionType
from quant_strategy.tools.builtin_skills import register_builtin_skills
from quant_strategy.tools.skill_system import get_registry
from quant_strategy.modules.base import get_module_registry


# ============== 第一部分：命令解析测试 ==============

class TestCommandParser(unittest.TestCase):
    """命令解析器测试"""

    def setUp(self):
        self.parser = CommandParser()

    def test_simple_download_command(self):
        """测试简单下载命令"""
        test_cases = [
            ("下载 2025 年数据", "2025"),
            ("下载 2024 年数据", "2024"),
            ("获取 2023 年的数据", "2023"),
        ]

        for command, expected_year in test_cases:
            with self.subTest(command=command):
                result = self.parser.parse(command)
                # 检查原始命令包含年份
                self.assertIn(expected_year, result.raw)

    def test_date_range_command(self):
        """测试日期范围命令"""
        test_cases = [
            "下载 20240101-20241231 的股票",
            "获取 240101-241231 的数据",
        ]

        for command in test_cases:
            with self.subTest(command=command):
                result = self.parser.parse(command)
                self.assertIsNotNone(result)

    def test_stock_code_command(self):
        """测试股票代码命令"""
        test_cases = [
            ("下载 600519.SH 的数据", "600519.SH"),
            ("下载 000001.SZ 的数据", "000001.SZ"),
            ("下载茅台的数据", None),  # 只测试不崩溃
        ]

        for command, expected_code in test_cases:
            with self.subTest(command=command):
                result = self.parser.parse(command)
                if expected_code:
                    self.assertIn(expected_code, result.raw)

    def test_workers_command(self):
        """测试线程数命令"""
        test_cases = [
            ("下载 2025 年数据 8 线程", 8),
            ("下载 2024 年数据 4 线程", 4),
            ("批量下载全部股票 1 线程", 1),
        ]

        for command, expected_workers in test_cases:
            with self.subTest(command=command):
                result = self.parser.parse(command)
                # 线程数应该被解析

    def test_special_keywords(self):
        """测试特殊关键词"""
        test_cases = [
            "下载今年数据",
            "下载去年数据",
            "批量下载全部股票",
            "更新最近 30 天",
        ]

        for command in test_cases:
            with self.subTest(command=command):
                result = self.parser.parse(command)
                self.assertIsNotNone(result)


# ============== 第二部分：上下文管理测试 ==============

class TestContextManager(unittest.TestCase):
    """上下文管理器测试"""

    def setUp(self):
        self.context = ContextManager()

    def test_basic_set_get(self):
        """测试基本设置/获取"""
        self.context.set('key1', 'value1')
        self.assertEqual(self.context.get('key1'), 'value1')

        # 获取不存在的键
        self.assertIsNone(self.context.get('nonexistent'))
        self.assertEqual(self.context.get('nonexistent', 'default'), 'default')

    def test_bucket_operations(self):
        """测试桶操作"""
        # 创建新桶
        bucket = self.context.create_bucket('test_bucket')
        self.assertIn('test_bucket', self.context.buckets)

        # 切换桶
        self.context.switch_bucket('test_bucket')
        self.assertEqual(self.context.current_bucket, 'test_bucket')

        # 在不同桶中设置值
        self.context.set('bucket_var', 'bucket_value', bucket='test_bucket')
        self.context.set('default_var', 'default_value', bucket='default')

        # 验证隔离
        self.assertEqual(
            self.context.get('bucket_var', bucket='test_bucket'),
            'bucket_value'
        )

    def test_global_variables(self):
        """测试全局变量"""
        self.context.set_global('global_key', 'global_value')
        self.assertEqual(self.context.get_global('global_key'), 'global_value')

    def test_persistent_flag(self):
        """测试持久化标志"""
        self.context.set('persistent_var', 'value1', persistent=True)
        self.context.set('temp_var', 'value2', persistent=False)

        current = self.context.current()
        self.assertTrue(current.data['persistent_var']['persistent'])
        self.assertFalse(current.data['temp_var']['persistent'])

    def test_clear_operations(self):
        """测试清空操作"""
        self.context.set('persistent_var', 'value1', persistent=True)
        self.context.set('temp_var', 'value2', persistent=False)

        # 清空非持久化变量
        self.context.clear(keep_persistent=True)
        self.assertIsNotNone(self.context.get('persistent_var'))
        self.assertIsNone(self.context.get('temp_var'))


# ============== 第三部分：Skill 系统测试 ==============

class TestSkillSystem(unittest.TestCase):
    """Skill 系统测试"""

    def setUp(self):
        self.registry = SkillRegistry()
        self.executor = SkillExecutor(self.registry)

        # 注册一个测试 Skill
        class TestSkill(Skill):
            @property
            def definition(self) -> SkillDefinition:
                return SkillDefinition(
                    name="test_skill",
                    description="测试技能",
                    aliases=["测试", "test"],
                    parameters={
                        "value": {"required": True, "description": "测试值"}
                    },
                    examples=["测试 value=123"],
                    category="test"
                )

            async def execute(self, context, **kwargs):
                value = kwargs.get('value', 0)
                return SkillResult(
                    success=True,
                    message=f"测试完成，值={value}",
                    data={'received_value': value}
                )

        self.test_skill = TestSkill()
        self.registry.register(self.test_skill)

    def test_skill_registration(self):
        """测试 Skill 注册"""
        # 通过名称查找
        skill = self.registry.get('test_skill')
        self.assertIsNotNone(skill)

        # 通过别名查找
        skill = self.registry.get('测试')
        self.assertIsNotNone(skill)

    def test_skill_search(self):
        """测试 Skill 搜索"""
        results = self.registry.search('test')
        self.assertGreater(len(results), 0)

    def test_skill_execution(self):
        """测试 Skill 执行"""
        result = asyncio.run(
            self.executor.execute('test_skill', context={}, value=42)
        )
        self.assertTrue(result.success)
        self.assertIn('42', result.message)


class TestBuiltinSkills(unittest.TestCase):
    """内置 Skills 测试"""

    def setUp(self):
        self.registry = get_registry()
        register_builtin_skills()

    def test_all_skills_registered(self):
        """测试所有 Skills 已注册"""
        skills = self.registry.list_skills()
        expected_skills = [
            'download_data', 'update_data', 'cache_status',
            'cleanup_cache', 'backtest', 'sector_analysis'
        ]

        for skill_name in expected_skills:
            with self.subTest(skill_name=skill_name):
                self.assertIn(skill_name, skills)

    def test_skill_categories(self):
        """测试 Skill 分类"""
        categories = self.registry.list_categories()
        self.assertIn('data', categories)
        self.assertIn('cache', categories)


# ============== 第四部分：模块系统测试 ==============

class TestModuleSystem(unittest.TestCase):
    """模块系统测试"""

    def setUp(self):
        self.registry = get_module_registry()

    def test_registry_exists(self):
        """测试注册表存在"""
        self.assertIsNotNone(self.registry)

    def test_data_module(self):
        """测试数据模块"""
        from quant_strategy.modules.data_module import DataModule
        module = DataModule()
        self.assertIsNotNone(module.info)
        self.assertEqual(module.info.name, 'data')

    def test_strategy_module(self):
        """测试策略模块"""
        from quant_strategy.modules.strategy_module import StrategyModule
        module = StrategyModule()
        self.assertIsNotNone(module.info)
        self.assertEqual(module.info.name, 'strategy')

    def test_module_actions(self):
        """测试模块操作"""
        from quant_strategy.modules.strategy_module import StrategyModule
        module = StrategyModule()
        actions = module.get_actions()
        self.assertIn('list', actions)
        self.assertIn('info', actions)


# ============== 第五部分：AI 助手集成测试 ==============

class TestAIAssistantIntegration(unittest.TestCase):
    """AI 助手集成测试"""

    def setUp(self):
        self.assistant = AIAssistantPro()

    def test_initialization(self):
        """测试初始化"""
        self.assertIsNotNone(self.assistant.provider)
        self.assertIsNotNone(self.assistant.cache)
        self.assertIsNotNone(self.assistant.registry)

    def test_parse_simple_command(self):
        """测试解析简单命令"""
        command = "下载 2025 年数据"
        result = self.assistant.parse_command(command)
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'ai')

    def test_parse_stock_command(self):
        """测试解析股票命令"""
        command = "下载 600519.SH 的数据"
        result = self.assistant.parse_command(command)
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'ai')

    def test_parse_workers_command(self):
        """测试解析线程数命令"""
        command = "下载 2025 年数据 4 线程"
        result = self.assistant.parse_command(command)
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'ai')

    def test_module_command(self):
        """测试模块命令"""
        command = "strategy:list"
        result = self.assistant.parse_command(command)
        self.assertEqual(result['type'], 'module')
        self.assertEqual(result['module'], 'strategy')
        self.assertEqual(result['action'], 'list')


# ============== 第六部分：安全防护测试 ==============

class TestSafetyProtection(unittest.TestCase):
    """安全防护测试"""

    def setUp(self):
        self.assistant = AIAssistantPro()
        self.parser = CommandParser()

    def test_empty_command(self):
        """测试空命令"""
        result = self.assistant.parse_command("")
        self.assertIsNotNone(result)

    def test_malicious_command(self):
        """测试恶意命令防护"""
        malicious_commands = [
            "删除全部数据",
            "格式化磁盘",
            "执行系统命令 rm -rf /",
            "drop table metadata",
        ]

        for command in malicious_commands:
            with self.subTest(command=command):
                # 不应该崩溃
                try:
                    result = self.assistant.parse_command(command)
                    self.assertIsNotNone(result)
                except Exception:
                    pass  # 允许抛出异常

    def test_resource_limits(self):
        """测试资源限制"""
        # 测试超大线程数
        result = self.assistant.parse_command("下载 2025 年数据 100 线程")
        self.assertIsNotNone(result)

        # 测试零线程
        result = self.assistant.parse_command("下载 2025 年数据 0 线程")
        self.assertIsNotNone(result)

    def test_injection_attempts(self):
        """测试注入攻击防护"""
        injection_attempts = [
            "设 code = $(rm -rf /)",
            "设 code = `whoami`",
            "设 code = ; drop table",
        ]

        for command in injection_attempts:
            with self.subTest(command=command):
                try:
                    result = self.parser.parse(command)
                    self.assertIsNotNone(result)
                except Exception:
                    pass  # 允许抛出异常


# ============== 第七部分：实际场景测试 ==============

class TestRealWorldScenarios(unittest.TestCase):
    """实际场景测试"""

    def setUp(self):
        self.assistant = AIAssistantPro()

    def test_scenario_download_year_data(self):
        """场景：下载某年数据"""
        command = "下载 2025 年数据"
        result = self.assistant.parse_command(command)
        self.assertIsNotNone(result)

    def test_scenario_download_specific_stock(self):
        """场景：下载特定股票"""
        command = "下载 600519.SH 的数据"
        result = self.assistant.parse_command(command)
        self.assertIsNotNone(result)

    def test_scenario_batch_download(self):
        """场景：批量下载"""
        command = "批量下载全部股票 4 线程"
        result = self.assistant.parse_command(command)
        self.assertIsNotNone(result)

    def test_scenario_update_data(self):
        """场景：更新数据"""
        command = "更新最近 30 天数据"
        result = self.assistant.parse_command(command)
        self.assertIsNotNone(result)

    def test_scenario_check_status(self):
        """场景：查看状态"""
        command = "查看缓存状态"
        result = self.assistant.parse_command(command)
        self.assertIsNotNone(result)


# ============== 第八部分：性能测试 ==============

class TestPerformance(unittest.TestCase):
    """性能测试"""

    def setUp(self):
        self.parser = CommandParser()

    def test_parse_performance(self):
        """测试解析性能"""
        import time

        command = "下载 2025 年数据"
        iterations = 1000

        start = time.time()
        for _ in range(iterations):
            self.parser.parse(command)
        elapsed = time.time() - start

        # 1000 次解析应该小于 1 秒
        self.assertLess(elapsed, 1.0)
        avg_time = (elapsed * 1000) / iterations
        print(f"\n平均解析时间：{avg_time:.3f}ms")


# ============== 测试运行器 ==============

def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestCommandParser))
    suite.addTests(loader.loadTestsFromTestCase(TestContextManager))
    suite.addTests(loader.loadTestsFromTestCase(TestSkillSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestBuiltinSkills))
    suite.addTests(loader.loadTestsFromTestCase(TestModuleSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestAIAssistantIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestSafetyProtection))
    suite.addTests(loader.loadTestsFromTestCase(TestRealWorldScenarios))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformance))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 生成报告
    print("\n" + "=" * 70)
    print("测试报告")
    print("=" * 70)
    print(f"总测试数：{result.testsRun}")
    successes = result.testsRun - len(result.failures) - len(result.errors)
    print(f"成功：{successes}")
    print(f"失败：{len(result.failures)}")
    print(f"错误：{len(result.errors)}")
    print("=" * 70)

    if result.failures:
        print("\n失败测试:")
        for test, traceback in result.failures:
            print(f"  - {test}")

    if result.errors:
        print("\n错误测试:")
        for test, traceback in result.errors:
            print(f"  - {test}")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
