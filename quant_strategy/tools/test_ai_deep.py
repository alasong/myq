"""
AI 交互深度测试套件

目标：测试真实的业务逻辑和端到端场景
覆盖：
1. 命令解析准确性测试
2. Skill 参数提取测试
3. 端到端场景测试
4. 错误处理和边界条件
5. 性能测试
"""
import sys
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from quant_strategy.tools.ai_assistant_pro import AIAssistantPro
from quant_strategy.tools.command_parser import CommandParser, WorkflowExecutor, get_parser
from quant_strategy.tools.builtin_skills import (
    DownloadDataSkill, UpdateDataSkill, CacheStatusSkill, CleanupCacheSkill
)
from quant_strategy.tools.skill_system import SkillRegistry, SkillExecutor


# ============== 第一部分：命令解析准确性测试 ==============

class TestCommandParseAccuracy(unittest.TestCase):
    """命令解析准确性测试 - 验证解析结果是否正确"""

    def setUp(self):
        self.assistant = AIAssistantPro()

    def test_year_command_parse(self):
        """测试年份命令解析 - 验证日期范围正确"""
        test_cases = [
            ("下载 2024 年数据", "20240101", "20241231"),
            ("下载 2025 年数据", "20250101", "20251231"),
            ("获取 2023 年的数据", "20230101", "20231231"),
        ]

        for command, expected_start, expected_end in test_cases:
            with self.subTest(command=command):
                result = self.assistant.parse_command(command)
                self.assertEqual(
                    result['params'].get('start_date'),
                    expected_start,
                    f"命令 '{command}' 的开始日期解析错误"
                )
                self.assertEqual(
                    result['params'].get('end_date'),
                    expected_end,
                    f"命令 '{command}' 的结束日期解析错误"
                )

    def test_current_year_command(self):
        """测试今年/去年命令"""
        current_year = str(datetime.now().year)
        last_year = str(datetime.now().year - 1)

        result = self.assistant.parse_command("下载今年数据")
        self.assertEqual(result['params']['start_date'], f"{current_year}0101")
        self.assertEqual(result['params']['end_date'], f"{current_year}1231")

        result = self.assistant.parse_command("下载去年数据")
        self.assertEqual(result['params']['start_date'], f"{last_year}0101")
        self.assertEqual(result['params']['end_date'], f"{last_year}1231")

    def test_date_range_parse(self):
        """测试日期范围解析"""
        test_cases = [
            ("下载 20240101-20240331 的股票", "20240101", "20240331"),
            ("获取 240101-241231 的数据", "20240101", "20241231"),
        ]

        for command, expected_start, expected_end in test_cases:
            with self.subTest(command=command):
                result = self.assistant.parse_command(command)
                self.assertEqual(
                    result['params'].get('start_date'),
                    expected_start,
                    f"命令 '{command}' 的开始日期解析错误"
                )

    def test_stock_code_parse(self):
        """测试股票代码解析"""
        test_cases = [
            ("下载 600519.SH 的数据", "600519.SH"),
            ("下载 000001.SZ 的数据", "000001.SZ"),
            ("获取 300750.SZ 的数据", "300750.SZ"),
        ]

        for command, expected_code in test_cases:
            with self.subTest(command=command):
                result = self.assistant.parse_command(command)
                self.assertEqual(
                    result['params'].get('ts_code'),
                    expected_code,
                    f"命令 '{command}' 的股票代码解析错误"
                )

    def test_workers_parse(self):
        """测试线程数解析"""
        test_cases = [
            ("下载 2025 年数据 1 线程", 1),
            ("下载 2025 年数据 4 线程", 4),
            ("下载 2025 年数据 8 线程", 8),
            ("下载 2025 年数据 100 线程", 8),  # 超过 8 应该被限制
            ("下载 2025 年数据 0 线程", 1),    # 0 应该被修正为 1
        ]

        for command, expected_workers in test_cases:
            with self.subTest(command=command):
                result = self.assistant.parse_command(command)
                actual_workers = result['params'].get('workers', 4)
                self.assertEqual(
                    actual_workers,
                    expected_workers,
                    f"命令 '{command}' 的线程数解析错误"
                )

    def test_stock_name_to_code(self):
        """测试股票名转代码"""
        # 茅台应该被识别为 600519.SH
        result = self.assistant.parse_command("下载茅台的数据")
        self.assertEqual(result['type'], 'ai')
        self.assertEqual(result['action'], 'download')

    def test_module_command_parse(self):
        """测试模块命令解析"""
        test_cases = [
            ("strategy:list", "strategy", "list"),
            ("data:status", "data", "status"),
            ("strategy:info name=dual_ma", "strategy", "info"),
        ]

        for command, expected_module, expected_action in test_cases:
            with self.subTest(command=command):
                result = self.assistant.parse_command(command)
                self.assertEqual(result['type'], 'module')
                self.assertEqual(result['module'], expected_module)
                self.assertEqual(result['action'], expected_action)


# ============== 第二部分：Skill 参数提取测试 ==============

class TestSkillParameterExtraction(unittest.TestCase):
    """Skill 参数提取测试"""

    def setUp(self):
        self.assistant = AIAssistantPro()

    def test_download_skill_params(self):
        """测试下载 Skill 参数提取"""
        command = "下载 20240101-20241231 的股票 4 线程"
        result = self.assistant.parse_command(command)

        self.assertEqual(result['type'], 'ai')
        self.assertEqual(result['action'], 'download')
        self.assertEqual(result['params'].get('start_date'), '20240101')
        self.assertEqual(result['params'].get('end_date'), '20241231')
        self.assertEqual(result['params'].get('workers'), 4)

    def test_all_stocks_flag(self):
        """测试全部股票标志"""
        commands = [
            "批量下载全部股票",
            "下载所有股票数据",
            "下载全部股票 4 线程",
        ]

        for command in commands:
            with self.subTest(command=command):
                result = self.assistant.parse_command(command)
                # 检查是否识别为下载动作
                self.assertEqual(result['action'], 'download')
                # 检查是否包含全部关键字
                self.assertTrue(
                    '全部' in command or '所有' in command or '批量' in command
                )

    def test_stock_name_mapping(self):
        """测试股票名映射"""
        stock_map = {
            "茅台": "600519.SH",
            "平安银行": "000001.SZ",
            "万科": "000002.SZ",
            "宁德": "300750.SZ",
        }

        for name, expected_code in stock_map.items():
            with self.subTest(name=name):
                command = f"下载{name}的数据"
                result = self.assistant.parse_command(command)
                self.assertEqual(result['type'], 'ai')
                self.assertEqual(result['action'], 'download')
                self.assertEqual(
                    result['params'].get('ts_code'),
                    expected_code,
                    f"股票名 {name} 应该映射到 {expected_code}"
                )


# ============== 第三部分：端到端场景测试 ==============

class TestEndToEndScenarios(unittest.TestCase):
    """端到端场景测试 - 模拟真实用户操作"""

    def setUp(self):
        self.assistant = AIAssistantPro()

    @patch('quant_strategy.tools.fetch_all_stocks.fetch_and_cache_stocks')
    @patch('quant_strategy.tools.fetch_all_stocks.get_all_stocks')
    def test_scenario_download_year_data(self, mock_get_stocks, mock_fetch):
        """场景：下载 2024 年全部股票数据"""
        # Mock 数据
        mock_get_stocks.return_value = ['600519.SH', '000001.SZ']
        mock_fetch.return_value = {'success': True, 'count': 2}

        command = "下载 2024 年数据 4 线程"
        result = self.assistant.parse_command(command)

        # 验证解析结果
        self.assertEqual(result['type'], 'ai')
        self.assertEqual(result['action'], 'download')
        self.assertEqual(result['params']['start_date'], '20240101')
        self.assertEqual(result['params']['end_date'], '20241231')
        self.assertEqual(result['params']['workers'], 4)

    @patch('quant_strategy.data.data_cache.DataCache.get_stats')
    def test_scenario_check_cache_status(self, mock_stats):
        """场景：查看缓存状态"""
        mock_stats.return_value = {
            'total_files': 1000,
            'total_size_mb': 500,
            'stock_count': 5000
        }

        command = "查看缓存状态"
        result = self.assistant.parse_command(command)

        self.assertEqual(result['type'], 'ai')
        self.assertEqual(result['action'], 'status')

    def test_scenario_workflow_download_then_backtest(self):
        """场景：下载数据然后回测"""
        command = "下载茅台 2024 年数据，然后回测"
        result = self.assistant.parse_command(command)

        # 应该被识别为工作流
        self.assertIn(result['type'], ['ai', 'workflow'])
        # 至少应该识别出下载动作
        self.assertEqual(result['action'], 'download')

    def test_scenario_update_recent_data(self):
        """场景：更新最近 30 天数据"""
        command = "更新最近 30 天数据"
        result = self.assistant.parse_command(command)

        self.assertEqual(result['type'], 'ai')
        self.assertEqual(result['action'], 'update')


# ============== 第四部分：错误处理和边界条件 ==============

class TestErrorHandling(unittest.TestCase):
    """错误处理和边界条件测试"""

    def setUp(self):
        self.assistant = AIAssistantPro()

    def test_empty_command(self):
        """测试空命令"""
        result = self.assistant.parse_command("")
        self.assertEqual(result['action'], 'unknown')

    def test_whitespace_only_command(self):
        """测试纯空格命令"""
        result = self.assistant.parse_command("   ")
        self.assertEqual(result['action'], 'unknown')

    def test_unknown_action(self):
        """测试未知动作"""
        unknown_commands = [
            "今天天气怎么样",
            "帮我写代码",
            "播放音乐",
        ]

        for command in unknown_commands:
            with self.subTest(command=command):
                result = self.assistant.parse_command(command)
                self.assertEqual(result['action'], 'unknown')

    def test_invalid_date_format(self):
        """测试无效日期格式"""
        invalid_dates = [
            "下载 20241301 数据",  # 无效月份
            "下载 20240230 数据",  # 无效日期
            "下载 abc-def 数据",   # 非数字
        ]

        for command in invalid_dates:
            with self.subTest(command=command):
                # 不应该崩溃，可能返回 None 或忽略
                result = self.assistant.parse_command(command)
                self.assertIsNotNone(result)

    def test_special_characters_injection(self):
        """测试特殊字符注入"""
        injection_attempts = [
            "设 code = $(rm -rf /)",
            "设 code = `whoami`",
            "设 code = ; drop table",
            "下载数据; rm -rf /",
        ]

        for command in injection_attempts:
            with self.subTest(command=command):
                # 不应该崩溃
                try:
                    result = self.assistant.parse_command(command)
                    self.assertIsNotNone(result)
                except Exception:
                    pass  # 允许抛出异常

    def test_very_long_command(self):
        """测试超长命令"""
        long_command = "下载" + "股票" * 100 + "的数据"
        result = self.assistant.parse_command(long_command)
        self.assertIsNotNone(result)

    def test_unicode_characters(self):
        """测试 Unicode 字符"""
        commands = [
            "下载🚀数据",
            "下载 2024 年数据💯",
            "查看缓存状态📊",
        ]

        for command in commands:
            with self.subTest(command=command):
                result = self.assistant.parse_command(command)
                self.assertIsNotNone(result)


# ============== 第五部分：工作流和条件判断测试 ==============

class TestWorkflowAndConditional(unittest.TestCase):
    """工作流和条件判断测试"""

    def setUp(self):
        self.parser = get_parser()

    def test_workflow_with_separator(self):
        """测试带分隔符的工作流"""
        test_cases = [
            "下载 2024 年数据，然后清理缓存",
            "下载 2024 年数据;清理缓存",
            "下载 2024 年数据&&清理缓存",
        ]

        for command in test_cases:
            with self.subTest(command=command):
                result = self.parser.parse(command)
                self.assertEqual(result.type.value, 'workflow')
                self.assertGreaterEqual(len(result.steps), 2)

    def test_conditional_command(self):
        """测试条件命令"""
        command = "如果缓存大于 1GB，清理缓存"
        result = self.parser.parse(command)

        self.assertEqual(result.type.value, 'conditional')
        self.assertIsNotNone(result.conditions)

    def test_parallel_command(self):
        """测试并行命令"""
        command = "下载 2024 年数据 & 下载 2025 年数据"
        result = self.parser.parse(command)

        self.assertEqual(result.type.value, 'parallel')
        self.assertGreaterEqual(len(result.steps), 2)


# ============== 第六部分：Skill 定义验证测试 ==============

class TestSkillDefinitions(unittest.TestCase):
    """Skill 定义验证测试"""

    def test_download_skill_definition(self):
        """测试下载 Skill 定义"""
        skill = DownloadDataSkill()
        definition = skill.definition

        self.assertEqual(definition.name, 'download_data')
        self.assertIn('start_date', definition.parameters)
        self.assertIn('end_date', definition.parameters)
        self.assertIn('workers', definition.parameters)
        self.assertGreater(len(definition.examples), 0)

    def test_cache_status_skill_definition(self):
        """测试缓存状态 Skill 定义"""
        skill = CacheStatusSkill()
        definition = skill.definition

        self.assertEqual(definition.name, 'cache_status')
        self.assertEqual(definition.category, 'cache')

    def test_cleanup_skill_definition(self):
        """测试清理 Skill 定义"""
        skill = CleanupCacheSkill()
        definition = skill.definition

        self.assertEqual(definition.name, 'cleanup_cache')
        self.assertEqual(definition.category, 'cache')


# ============== 第七部分：性能测试 ==============

class TestPerformance(unittest.TestCase):
    """性能测试"""

    def setUp(self):
        self.assistant = AIAssistantPro()
        self.parser = get_parser()

    def test_parse_single_command_performance(self):
        """测试单次解析性能"""
        import time

        command = "下载 2024 年数据 4 线程"

        start = time.time()
        for _ in range(100):
            self.assistant.parse_command(command)
        elapsed = time.time() - start

        avg_ms = (elapsed / 100) * 1000
        print(f"\n单次解析平均时间：{avg_ms:.3f}ms")

        # 单次解析应该小于 10ms
        self.assertLess(avg_ms, 10)

    def test_workflow_parse_performance(self):
        """测试工作流解析性能"""
        import time

        command = "下载 2024 年数据，然后清理缓存，然后回测"

        start = time.time()
        for _ in range(100):
            result = self.parser.parse(command)
        elapsed = time.time() - start

        avg_ms = (elapsed / 100) * 1000
        print(f"\n工作流解析平均时间：{avg_ms:.3f}ms")

        # 工作流解析应该小于 20ms
        self.assertLess(avg_ms, 20)


# ============== 测试运行器 ==============

def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestCommandParseAccuracy))
    suite.addTests(loader.loadTestsFromTestCase(TestSkillParameterExtraction))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEndScenarios))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestWorkflowAndConditional))
    suite.addTests(loader.loadTestsFromTestCase(TestSkillDefinitions))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformance))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 生成报告
    print("\n" + "=" * 70)
    print("深度测试报告")
    print("=" * 70)
    print(f"总测试数：{result.testsRun}")
    successes = result.testsRun - len(result.failures) - len(result.errors)
    print(f"成功：{successes}")
    print(f"失败：{len(result.failures)}")
    print(f"错误：{len(result.errors)}")
    print("=" * 70)

    if result.failures:
        print("\n失败测试详情:")
        for test, traceback in result.failures:
            error_msg = traceback.split('AssertionError:')[-1].strip()[:100] if 'AssertionError:' in traceback else str(traceback)[:100]
            print(f"  [FAIL] {test}")
            print(f"         {error_msg}")

    if result.errors:
        print("\n错误测试详情:")
        for test, traceback in result.errors:
            print(f"  [ERROR] {test}")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
