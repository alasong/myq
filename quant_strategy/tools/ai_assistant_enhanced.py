"""
AI 交互接口 - 增强版

支持：
- 多桶上下文机制
- Skill 插件系统
- 复杂指令解析（工作流/条件/循环/并行）
- 自然语言命令

使用方法：
    python -m quant_strategy.tools.ai_assistant_enhanced
"""
import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from loguru import logger

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入模块
from quant_strategy.data.tushare_provider import TushareDataProvider
from quant_strategy.data.data_cache import DataCache
from quant_strategy.data.sector_provider import SectorDataProvider
from quant_strategy.tools.fetch_all_stocks import get_all_stocks

from .context_bucket import ContextManager, get_context_manager
from .skill_system import SkillRegistry, SkillExecutor, get_registry, get_executor, SkillResult
from .builtin_skills import register_builtin_skills
from .command_parser import CommandParser, WorkflowExecutor, get_parser, get_workflow_executor, ParsedInstruction


class EnhancedAIAssistant:
    """增强版 AI 助手"""
    
    def __init__(self, token: str = None, context_save_path: str = None):
        """
        初始化 AI 助手
        
        Args:
            token: Tushare Token
            context_save_path: 上下文持久化路径
        """
        self.token = token or Path.home().joinpath('.tushare_token').exists() and Path.home().joinpath('.tushare_token').read_text().strip() or None
        
        # 初始化上下文管理器
        self.context_manager = ContextManager(
            save_path=Path(context_save_path) if context_save_path else None
        )
        
        # 初始化数据源
        self._init_data_source()
        
        # 注册 Skills
        register_builtin_skills()
        
        # 初始化解析器和执行器
        self.parser = get_parser()
        self.workflow_executor = get_workflow_executor()
        
        # 设置上下文
        self._setup_context()
        
        # 对话历史
        self.conversation_history: List[Dict] = []
        
        # 当前桶
        self.current_bucket = 'default'
    
    def _init_data_source(self):
        """初始化数据源"""
        import os
        token = self.token or os.getenv('TUSHARE_TOKEN', '')
        
        if token:
            try:
                self.provider = TushareDataProvider(token=token, use_cache=True)
                self.cache = self.provider.cache
                self.sector_provider = SectorDataProvider(token=token)
                logger.info("数据源初始化成功")
            except Exception as e:
                logger.warning(f"数据源初始化失败：{e}")
                self.provider = None
                self.cache = None
                self.sector_provider = None
        else:
            logger.warning("未设置 TUSHARE_TOKEN，部分功能不可用")
            self.provider = None
            self.cache = None
            self.sector_provider = None
    
    def _setup_context(self):
        """设置上下文"""
        # 数据源上下文
        self.context_manager.set_global('provider', self.provider)
        self.context_manager.set_global('cache', self.cache)
        self.context_manager.set_global('sector_provider', self.sector_provider)
        
        # 助手信息
        self.context_manager.set('assistant_name', 'Enhanced AI Assistant')
        self.context_manager.set('started_at', datetime.now().isoformat())
    
    def switch_bucket(self, name: str):
        """切换上下文桶"""
        self.context_manager.switch_bucket(name)
        self.current_bucket = name
        logger.info(f"已切换上下文桶：{name}")
    
    def get_context(self, bucket: str = None) -> Dict:
        """获取上下文"""
        if bucket:
            return self.context_manager.get_all(bucket)
        return self.context_manager.get_all(self.current_bucket)
    
    def set_context(self, key: str, value: Any, bucket: str = None, persistent: bool = True):
        """设置上下文"""
        self.context_manager.set(key, value, bucket, persistent)
    
    async def execute(self, command: str) -> List[SkillResult]:
        """
        执行命令
        
        Args:
            command: 自然语言命令
            
        Returns:
            SkillResult 列表
        """
        # 记录对话历史
        self.conversation_history.append({
            'role': 'user',
            'content': command,
            'timestamp': datetime.now().isoformat()
        })
        
        print(f"\n收到命令：{command}")
        print("-" * 60)
        
        # 1. 解析命令
        instruction = self.parser.parse(command)
        
        print(f"指令类型：{instruction.type.value}")
        print(f"解析步骤：{len(instruction.steps)}")
        if instruction.variables:
            print(f"变量：{instruction.variables}")
        print("-" * 60)
        
        # 2. 准备执行上下文
        exec_context = {
            **self.context_manager.get_all_buckets(),
            'conversation_history': self.conversation_history[-10:],  # 最近 10 条
        }
        
        # 3. 执行指令
        try:
            results = await self.workflow_executor.execute(instruction, exec_context)
            
            # 记录结果
            for result in results:
                self.conversation_history.append({
                    'role': 'assistant',
                    'content': result.message,
                    'timestamp': datetime.now().isoformat(),
                    'success': result.success
                })
            
            # 打印结果
            self._print_results(results)
            
            # 保存上下文
            self.context_manager.save()
            
            return results
            
        except Exception as e:
            logger.exception("执行失败")
            error_result = SkillResult(
                success=False,
                message=f"执行失败：{str(e)}",
                error=str(e)
            )
            self.conversation_history.append({
                'role': 'assistant',
                'content': error_result.message,
                'timestamp': datetime.now().isoformat(),
                'success': False
            })
            return [error_result]
    
    def _print_results(self, results: List[SkillResult]):
        """打印执行结果"""
        print("\n执行结果:")
        print("=" * 60)
        
        for i, result in enumerate(results):
            if len(results) > 1:
                print(f"\n[步骤 {i+1}/{len(results)}]")
            
            status = "[OK]" if result.success else "[FAIL]"
            print(f"{status} {result.message}")
            
            # 打印数据摘要
            if result.data:
                if isinstance(result.data, dict):
                    print("\n返回数据:")
                    for key, value in result.data.items():
                        if isinstance(value, (int, float, str)):
                            print(f"  {key}: {value}")
                        elif isinstance(value, list):
                            print(f"  {key}: [{len(value)} 项]")
        
        print("=" * 60)
    
    def run(self, command: str):
        """同步运行命令"""
        return asyncio.run(self.execute(command))
    
    def list_skills(self) -> List[str]:
        """列出所有 Skills"""
        return get_registry().list_skills()
    
    def get_skill_help(self, name: str) -> str:
        """获取 Skill 帮助"""
        return get_registry().get_help(name)
    
    def show_help(self):
        """显示帮助信息"""
        help_text = """
Enhanced AI 助手使用指南
============================================================

支持的命令类型:

1. 简单命令:
   - 下载 2025 年数据
   - 查看缓存状态
   - 清理缓存
   - 更新数据

2. 工作流命令 (多步骤):
   - 下载 2024 年数据，然后清理缓存
   - 先更新数据，再查看状态
   - 下载 2025 年数据 && 查看缓存

3. 条件命令:
   - 如果缓存大于 500MB，清理缓存
   - 如果股票数量超过 1000，分批下载

4. 变量定义:
   - 设 code = 000001.SZ，回测 code
   - set start = 20240101，下载 start 到 20241231 的数据

5. 上下文桶:
   - switch bucket backtest  (切换到回测上下文)
   - switch bucket data      (切换到数据上下文)

可用 Skills:
"""
        registry = get_registry()
        for category in registry.list_categories():
            help_text += f"\n  [{category}]\n"
            for skill_name in registry.list_by_category(category):
                skill = registry.get(skill_name)
                if skill:
                    help_text += f"    - {skill_name}: {skill.definition.description}\n"
        
        help_text += """
============================================================
输入 'help <skill>' 查看具体 Skill 的帮助
输入 'skills' 列出所有 Skills
输入 'context' 查看当前上下文
输入 'quit' 退出
============================================================
"""
        print(help_text)
    
    def show_context(self):
        """显示当前上下文"""
        context = self.context_manager.get_all()
        print("\n当前上下文:")
        print("=" * 60)
        print(f"桶名称：{context.get('name', 'default')}")
        print(f"变量数：{len(context.get('data', {}))}")
        
        if context.get('data'):
            print("\n变量列表:")
            for key, value in context['data'].items():
                if isinstance(value, (dict, list)):
                    print(f"  {key}: {type(value).__name__}")
                else:
                    print(f"  {key}: {value}")
        
        print("=" * 60)
    
    def show_skills(self):
        """显示 Skills 列表"""
        registry = get_registry()
        print("\n已注册 Skills:")
        print("=" * 60)
        
        for category in registry.list_categories():
            print(f"\n[{category}]")
            for skill_name in registry.list_by_category(category):
                skill = registry.get(skill_name)
                if skill:
                    aliases = ', '.join(skill.definition.aliases) if skill.definition.aliases else ''
                    print(f"  {skill_name}")
                    if aliases:
                        print(f"    别名：{aliases}")
        
        print("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Enhanced AI 股票数据助手')
    parser.add_argument('--token', type=str, help='Tushare Token')
    parser.add_argument('--context', type=str, help='上下文保存路径', default='~/.qwen/ai_context.json')
    parser.add_argument('command', nargs='?', help='自然语言命令')
    
    args = parser.parse_args()
    
    # 创建 AI 助手
    assistant = EnhancedAIAssistant(
        token=args.token,
        context_save_path=Path(args.context).expanduser() if args.context else None
    )
    
    # 显示欢迎信息
    print("\n" + "=" * 60)
    print("  Enhanced AI 股票数据助手")
    print("  支持：多桶上下文 | Skill 插件 | 复杂指令")
    print("=" * 60)
    print("输入 'help' 查看帮助，'quit' 退出")
    print("=" * 60)
    
    # 交互式模式
    if not args.command:
        while True:
            try:
                command = input("\n> ").strip()
                
                if command.lower() in ['quit', 'exit', 'q']:
                    # 保存上下文
                    assistant.context_manager.save()
                    print("再见！")
                    break
                
                if command.lower() == 'help':
                    assistant.show_help()
                elif command.lower() == 'skills':
                    assistant.show_skills()
                elif command.lower() == 'context':
                    assistant.show_context()
                elif command.lower().startswith('help '):
                    skill_name = command[5:].strip()
                    print(assistant.get_skill_help(skill_name))
                elif command.lower().startswith('switch bucket '):
                    bucket_name = command[14:].strip()
                    assistant.switch_bucket(bucket_name)
                elif command:
                    assistant.run(command)
                
            except KeyboardInterrupt:
                assistant.context_manager.save()
                print("\n再见！")
                break
            except Exception as e:
                print(f"❌ 错误：{e}")
    
    # 单次命令模式
    else:
        assistant.run(args.command)


if __name__ == "__main__":
    main()
