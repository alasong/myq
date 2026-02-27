"""
AI 交互界面 - 专业版 v2.0

基于模块系统的统一 AI 交互界面
支持：
- 自然语言命令
- 模块直接调用
- 工作流执行
- 上下文管理
"""
import sys
import os
import re
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from loguru import logger

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 尝试导入彩色输出库
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
    USE_COLOR = True
except ImportError:
    USE_COLOR = False
    class Fore:
        RESET = ''
        GREEN = ''
        RED = ''
        YELLOW = ''
        BLUE = ''
        CYAN = ''
        WHITE = ''
        MAGENTA = ''
    class Style:
        RESET = ''
        BRIGHT = ''

from quant_strategy.data.tushare_provider import TushareDataProvider
from quant_strategy.data.data_cache import DataCache
from quant_strategy.tools.fetch_all_stocks import fetch_and_cache_stocks, get_all_stocks
from quant_strategy.modules.base import get_module_registry, ModuleRegistry
from quant_strategy.modules.data_module import DataModule
from quant_strategy.modules.strategy_module import StrategyModule


# ============== 样式定义 ==============

class Colors:
    """颜色方案"""
    if USE_COLOR:
        PRIMARY = Fore.CYAN
        SUCCESS = Fore.GREEN
        ERROR = Fore.RED
        WARNING = Fore.YELLOW
        INFO = Fore.BLUE
        RESET = Style.RESET_ALL
        BRIGHT = Style.BRIGHT
    else:
        PRIMARY = SUCCESS = ERROR = WARNING = INFO = RESET = BRIGHT = ''


def print_banner():
    """打印欢迎横幅"""
    banner = f"""
{Colors.PRIMARY}{Colors.BRIGHT}╔══════════════════════════════════════════════════════════╗
║                                                      ║
║           AI 股票数据助手 专业版 v2.0                 ║
║           AI Stock Data Assistant Pro                ║
║                                                      ║
║  支持：自然语言 | 模块调用 | 工作流 | 上下文管理      ║
╚══════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    print(banner)


def print_status(message: str, status: str = 'info'):
    """打印状态消息"""
    icons = {
        'info': '[*]',
        'success': '[+]',
        'error': '[-]',
        'warning': '[!]',
        'loading': '[...]'
    }
    
    colors = {
        'info': Colors.INFO,
        'success': Colors.SUCCESS,
        'error': Colors.ERROR,
        'warning': Colors.WARNING,
        'loading': Colors.PRIMARY
    }
    
    icon = icons.get(status, '[*]')
    color = colors.get(status, '')
    
    print(f"{color}{icon} {message}{Colors.RESET}")


class CommandHistory:
    """命令历史"""
    
    def __init__(self, max_size: int = 100):
        self.history: List[str] = []
        self.max_size = max_size
        self.index = -1
    
    def add(self, command: str):
        if command and command not in self.history:
            self.history.append(command)
            if len(self.history) > self.max_size:
                self.history.pop(0)
        self.index = len(self.history)
    
    def previous(self) -> Optional[str]:
        if self.index > 0:
            self.index -= 1
            return self.history[self.index]
        return None
    
    def next(self) -> Optional[str]:
        if self.index < len(self.history) - 1:
            self.index += 1
            return self.history[self.index]
        return None


class AIAssistantPro:
    """专业版 AI 助手"""
    
    def __init__(self, token: str = None):
        """初始化 AI 助手"""
        self.token = token or os.getenv('TUSHARE_TOKEN', '')
        self.provider = None
        self.cache = None
        self.command_history = CommandHistory()
        self.registry = get_module_registry()
        self.stats = {
            'commands_executed': 0,
            'commands_succeeded': 0,
            'commands_failed': 0,
            'start_time': datetime.now()
        }
        
        print_status("正在初始化...", 'loading')
        self._init_data_source()
        self._init_modules()
        print_status("初始化完成", 'success')
    
    def _init_data_source(self):
        """初始化数据源"""
        if self.token:
            try:
                self.provider = TushareDataProvider(token=self.token, use_cache=True)
                self.cache = self.provider.cache
                # 设置到模块注册表
                self.registry.set_context('provider', self.provider)
                self.registry.set_context('cache', self.cache)
                logger.info("数据源初始化成功")
            except Exception as e:
                logger.warning(f"数据源初始化失败：{e}")
                print_status(f"数据源初始化失败：{e}", 'error')
        else:
            print_status("未设置 TUSHARE_TOKEN，部分功能不可用", 'warning')
    
    def _init_modules(self):
        """初始化模块"""
        # 模块会在导入时自动注册
        # 这里可以动态加载更多模块
        pass
    
    def parse_command(self, command: str) -> dict:
        """解析命令"""
        command = command.strip()
        
        result = {
            'type': 'unknown',  # module, ai, system
            'action': None,
            'module': None,
            'params': {},
            'raw': command
        }
        
        # 1. 系统命令
        if command.lower() in ['quit', 'exit', 'q', '退出']:
            result['type'] = 'system'
            result['action'] = 'quit'
            return result
        
        if command.lower() in ['help', 'h', '?', '帮助']:
            result['type'] = 'system'
            result['action'] = 'help'
            return result
        
        if command.lower() in ['modules', 'mods', '模块列表']:
            result['type'] = 'system'
            result['action'] = 'list_modules'
            return result
        
        if command.lower() in ['status', '状态']:
            result['type'] = 'system'
            result['action'] = 'status'
            return result
        
        # 2. 模块调用 (module:action 格式)
        module_match = re.match(r'^(\w+):(\w+)(?:\s+(.*))?$', command)
        if module_match:
            result['type'] = 'module'
            result['module'] = module_match.group(1)
            result['action'] = module_match.group(2)
            params_str = module_match.group(3)
            if params_str:
                # 解析参数 key=value 格式
                for param in params_str.split():
                    if '=' in param:
                        k, v = param.split('=', 1)
                        result['params'][k] = v
            return result
        
        # 3. AI 自然语言命令
        result['type'] = 'ai'
        
        # 识别动作
        if any(word in command for word in ['下载', '获取', 'get', 'download', 'fetch']):
            result['action'] = 'download'
        elif any(word in command for word in ['查看', '状态', 'status', 'check', 'list', '缓存']):
            result['action'] = 'status'
        elif any(word in command for word in ['清理', '清除', 'clean', 'clear', 'delete']):
            result['action'] = 'cleanup'
        elif any(word in command for word in ['帮助', 'help', 'usage']):
            result['action'] = 'help'
        elif any(word in command for word in ['更新', 'update', 'refresh']):
            result['action'] = 'update'
        elif any(word in command for word in ['策略', 'strategy']):
            result['action'] = 'strategy'
        elif any(word in command for word in ['数据', 'data', '股票']):
            result['action'] = 'data'
        else:
            result['action'] = 'unknown'
        
        # 识别日期
        year_match = re.search(r'(20\d{2})\s*年', command)
        if year_match:
            year = year_match.group(1)
            result['params']['start_date'] = year + '0101'
            result['params']['end_date'] = year + '1231'
        
        if '今年' in command:
            year = str(datetime.now().year)
            result['params']['start_date'] = year + '0101'
            result['params']['end_date'] = year + '1231'
        
        if '去年' in command:
            year = str(datetime.now().year - 1)
            result['params']['start_date'] = year + '0101'
            result['params']['end_date'] = year + '1231'
        
        # 识别线程数
        workers_match = re.search(r'(\d+)\s*线程', command)
        if workers_match:
            result['params']['workers'] = min(max(int(workers_match.group(1)), 1), 8)
        
        # 识别股票代码
        code_match = re.search(r'(\d{6}\.(SZ|SH|BJ))', command, re.IGNORECASE)
        if code_match:
            result['params']['ts_code'] = code_match.group(1).upper()
        
        return result
    
    def execute(self, command: str) -> bool:
        """执行命令"""
        self.stats['commands_executed'] += 1
        self.command_history.add(command)
        
        print(f"\n{Colors.PRIMARY}[>>]{Colors.RESET} {command}")
        print(f"{Colors.INFO}{'─' * 60}{Colors.RESET}")
        
        parsed = self.parse_command(command)
        
        try:
            if parsed['type'] == 'system':
                success = self._execute_system(parsed)
            elif parsed['type'] == 'module':
                success = self._execute_module(parsed)
            elif parsed['type'] == 'ai':
                success = self._execute_ai(parsed)
            else:
                print_status(f"未知命令类型", 'error')
                success = False
            
            if success:
                self.stats['commands_succeeded'] += 1
            else:
                self.stats['commands_failed'] += 1
            
            return success
            
        except KeyboardInterrupt:
            print(f"\n{Colors.WARNING}[!] 操作已取消{Colors.RESET}")
            return False
        except Exception as e:
            print_status(f"执行失败：{e}", 'error')
            self.stats['commands_failed'] += 1
            return False
    
    def _execute_system(self, parsed: dict) -> bool:
        """执行系统命令"""
        action = parsed['action']
        
        if action == 'quit':
            return False
        
        elif action == 'help':
            self._show_help()
            return True
        
        elif action == 'list_modules':
            modules = self.registry.list_modules()
            print(f"\n{Colors.BRIGHT}已注册模块:{Colors.RESET}")
            for name in modules:
                module = self.registry.get(name)
                if module:
                    print(f"  {Colors.SUCCESS}{name}{Colors.RESET} - {module.info.description}")
            return True
        
        elif action == 'status':
            runtime = datetime.now() - self.stats['start_time']
            print(f"\n{Colors.BRIGHT}会话状态:{Colors.RESET}")
            print(f"  运行时间：{runtime}")
            print(f"  已执行命令：{self.stats['commands_executed']}")
            print(f"  成功：{Colors.SUCCESS}{self.stats['commands_succeeded']}{Colors.RESET}")
            print(f"  失败：{Colors.ERROR}{self.stats['commands_failed']}{Colors.RESET}")
            print(f"  已注册模块：{len(self.registry.list_modules())}")
            return True
        
        return False
    
    def _execute_module(self, parsed: dict) -> bool:
        """执行模块命令"""
        module_name = parsed['module']
        action = parsed['action']
        params = parsed['params']
        
        module = self.registry.get(module_name)
        if not module:
            print_status(f"未找到模块：{module_name}", 'error')
            print_status("输入 'modules' 查看已注册模块", 'info')
            return False
        
        print_status(f"调用模块：{module_name}:{action}", 'loading')
        
        result = module.execute(action, **params)
        
        if result.success:
            print_status(result.message, 'success')
            if result.data:
                self._print_data(result.data)
            return True
        else:
            print_status(result.message, 'error')
            if result.error:
                print(f"{Colors.WARNING}错误：{result.error}{Colors.RESET}")
            return False
    
    def _execute_ai(self, parsed: dict) -> bool:
        """执行 AI 自然语言命令"""
        action = parsed['action']
        params = parsed['params']
        
        if action == 'download':
            return self._execute_download(params)
        elif action == 'status':
            return self._execute_status()
        elif action == 'cleanup':
            return self._execute_cleanup()
        elif action == 'update':
            return self._execute_update(params)
        elif action in ['strategy', 'data']:
            # 推荐用户使用模块
            print_status("建议使用模块命令:", 'info')
            if action == 'strategy':
                print("  策略列表：strategy:list")
                print("  策略详情：strategy:info name=dual_ma")
                print("  回测历史：strategy:history")
            else:
                print("  股票列表：data:list-stocks")
                print("  股票详情：data:stock-info ts_code=000001.SZ")
                print("  缓存状态：data:cache-status")
            return True
        elif action == 'help':
            self._show_help()
            return True
        else:
            print_status(f"未知命令，输入 'help' 查看帮助", 'error')
            return False
    
    def _execute_download(self, params: dict) -> bool:
        """执行下载"""
        if not params.get('start_date') or not params.get('end_date'):
            print_status("请指定日期范围", 'error')
            print_status("示例：下载 2025 年数据", 'info')
            return False
        
        if not self.provider:
            print_status("数据源未初始化，请设置 TUSHARE_TOKEN", 'error')
            return False
        
        print_status(f"日期范围：{params['start_date']} - {params['end_date']}", 'info')
        print_status(f"并发线程：{params.get('workers', 4)}", 'info')
        
        try:
            # 获取股票列表
            if params.get('ts_codes'):
                ts_codes = [params['ts_code']]
            elif params.get('ts_code'):
                ts_codes = [params['ts_code']]
            else:
                print_status("获取全部股票列表...", 'loading')
                ts_codes = get_all_stocks(self.provider)
                print_status(f"全部股票：{len(ts_codes)} 只", 'success')
            
            # 执行下载
            print_status("开始下载...", 'loading')
            
            fetch_and_cache_stocks(
                provider=self.provider,
                ts_codes=ts_codes,
                start_date=params['start_date'],
                end_date=params['end_date'],
                batch_size=50,
                force=False,
                workers=params.get('workers', 4)
            )
            
            print_status("下载完成！", 'success')
            return True
            
        except Exception as e:
            print_status(f"下载失败：{e}", 'error')
            return False
    
    def _execute_status(self) -> bool:
        """执行状态查询"""
        module = self.registry.get('data')
        if module:
            result = module.execute('cache-status')
            if result.success:
                print_status(result.message, 'success')
                if result.data:
                    self._print_data(result.data)
                return True
        return False
    
    def _execute_cleanup(self) -> bool:
        """执行清理"""
        if not self.cache:
            print_status("缓存未初始化", 'error')
            return False
        
        try:
            print_status("正在分析缓存...", 'loading')
            stats_before = self.cache.get_cache_stats()
            
            print_status(f"清理前：{stats_before['total_files']} 个文件，{stats_before['total_size_mb']:.2f} MB", 'info')
            print_status("正在清理过期缓存（30 天）...", 'loading')
            
            self.cache.clear(older_than_days=30)
            
            stats_after = self.cache.get_cache_stats()
            saved = stats_before['total_size_mb'] - stats_after['total_size_mb']
            
            print_status(f"清理后：{stats_after['total_files']} 个文件，{stats_after['total_size_mb']:.2f} MB", 'success')
            print_status(f"释放空间：{saved:.2f} MB", 'success')
            return True
            
        except Exception as e:
            print_status(f"清理失败：{e}", 'error')
            return False
    
    def _execute_update(self, params: dict) -> bool:
        """执行更新"""
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        
        params['start_date'] = start_date
        params['end_date'] = end_date
        
        print_status(f"更新最近 30 天数据：{start_date} - {end_date}", 'info')
        return self._execute_download(params)
    
    def _show_help(self):
        """显示帮助"""
        help_text = f"""
{Colors.PRIMARY}{Colors.BRIGHT}=== AI 助手使用指南 ==={Colors.RESET}
{Colors.INFO}{'=' * 60}{Colors.RESET}

{Colors.BRIGHT}一、自然语言命令:{Colors.RESET}
  {Colors.SUCCESS}下载 2025 年数据{Colors.RESET}              下载指定年份数据
  {Colors.SUCCESS}下载 20240101-20241231 的股票{Colors.RESET}   下载指定日期范围
  {Colors.SUCCESS}下载今年数据{Colors.RESET}                下载今年数据
  {Colors.SUCCESS}下载全部股票 8 线程{Colors.RESET}           指定线程数下载
  
  {Colors.SUCCESS}查看缓存状态{Colors.RESET}                查看缓存统计
  {Colors.SUCCESS}清理缓存{Colors.RESET}                    清理过期缓存
  {Colors.SUCCESS}更新数据{Colors.RESET}                    更新最近 30 天数据

{Colors.BRIGHT}二、模块命令 (module:action):{Colors.RESET}
  {Colors.SUCCESS}data:list-stocks{Colors.RESET}            列出股票
  {Colors.SUCCESS}data:stock-info ts_code=000001.SZ{Colors.RESET}  股票详情
  {Colors.SUCCESS}data:cache-status{Colors.RESET}            缓存状态
  {Colors.SUCCESS}strategy:list{Colors.RESET}                策略列表
  {Colors.SUCCESS}strategy:info name=dual_ma{Colors.RESET}   策略详情
  {Colors.SUCCESS}strategy:history{Colors.RESET}             回测历史

{Colors.BRIGHT}三、系统命令:{Colors.RESET}
  {Colors.SUCCESS}help / ?{Colors.RESET}                     显示帮助
  {Colors.SUCCESS}modules{Colors.RESET}                      列出模块
  {Colors.SUCCESS}status{Colors.RESET}                       会话状态
  {Colors.SUCCESS}quit / exit{Colors.RESET}                  退出程序

{Colors.BRIGHT}统计信息:{Colors.RESET}
  已执行命令：{self.stats['commands_executed']}
  成功：{self.stats['commands_succeeded']}
  失败：{self.stats['commands_failed']}

{Colors.INFO}{'=' * 60}{Colors.RESET}
"""
        print(help_text)
    
    def _print_data(self, data: Any):
        """打印数据"""
        if isinstance(data, dict):
            print(f"\n{Colors.BRIGHT}数据:{Colors.RESET}")
            for key, value in data.items():
                if isinstance(value, (int, float, str)):
                    print(f"  {key}: {value}")
                elif isinstance(value, list):
                    print(f"  {key}: [{len(value)} 项]")
        elif isinstance(data, list):
            print(f"\n{Colors.BRIGHT}数据 ({len(data)} 条):{Colors.RESET}")
            for i, item in enumerate(data[:5]):  # 只显示前 5 条
                if isinstance(item, dict):
                    print(f"  [{i+1}] {item}")
            if len(data) > 5:
                print(f"  ... 还有 {len(data) - 5} 条")
    
    def show_stats(self):
        """显示统计信息"""
        runtime = datetime.now() - self.stats['start_time']
        print(f"\n{Colors.PRIMARY}{Colors.BRIGHT}=== 会话统计 ==={Colors.RESET}")
        print(f"  运行时间：{runtime}")
        print(f"  已执行命令：{self.stats['commands_executed']}")
        print(f"  成功：{Colors.SUCCESS}{self.stats['commands_succeeded']}{Colors.RESET}")
        print(f"  失败：{Colors.ERROR}{self.stats['commands_failed']}{Colors.RESET}")


def get_input(prompt: str = "> ") -> str:
    """获取用户输入"""
    try:
        return input(f"{Colors.PRIMARY}{prompt}{Colors.RESET}").strip()
    except EOFError:
        return ""
    except KeyboardInterrupt:
        print()
        return "quit"


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='AI 股票数据助手 专业版')
    parser.add_argument('--token', type=str, help='Tushare Token')
    parser.add_argument('--command', '-c', type=str, help='单次执行的命令')
    
    args = parser.parse_args()
    
    # 打印横幅
    print_banner()
    
    # 创建 AI 助手
    try:
        assistant = AIAssistantPro(token=args.token)
    except Exception as e:
        print_status(f"初始化失败：{e}", 'error')
        return 1
    
    # 单次命令模式
    if args.command:
        assistant.execute(args.command)
        return 0
    
    # 显示欢迎信息
    print(f"\n{Colors.INFO}{'─' * 60}{Colors.RESET}")
    print_status("输入 'help' 查看帮助，'quit' 退出", 'info')
    print(f"{Colors.INFO}{'─' * 60}{Colors.RESET}\n")
    
    # 交互式模式
    while True:
        command = get_input()
        
        if not command:
            continue
        
        if command.lower() in ['quit', 'exit', 'q', '退出']:
            assistant.show_stats()
            print_status("再见！", 'success')
            break
        
        assistant.execute(command)


if __name__ == "__main__":
    sys.exit(main())
