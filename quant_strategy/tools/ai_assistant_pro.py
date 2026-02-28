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

# 尝试导入 LLM 意图识别器
try:
    from quant_strategy.tools.llm_intent import LLMIntentRecognizer, get_llm_recognizer
    LLM_AVAILABLE = True
except (ImportError, Exception):
    LLM_AVAILABLE = False
    logger.info("LLM 意图识别器不可用，将使用规则引擎")


# ============== 意图识别配置 ==============

INTENT_KEYWORDS = {
    'download': {
        'high': ['下载', '获取', 'fetch', 'download', 'get', '抓取', '拉取', '采集'],
        'medium': ['拿', '取', '抓', '拉', '收', '同步', '导入'],
        'low': ['看', '查', '查看', '需要', '要', '帮我', '给我'],
        'objects': ['数据', '股票', '行情', 'K 线', '走势', '历史'],
    },
    'update': {
        'high': ['更新', '刷新', '同步', 'update', 'refresh', '补充'],
        'medium': ['补', '新', '最新的', '最近的', '最新'],
        'low': ['不准', '过时', '旧', '缺少'],
        'objects': ['数据', '股票', '行情'],
    },
    'status': {
        'high': ['状态', '缓存', 'status', '统计', '多少', '多大'],
        'medium': ['看看', '查查', '检查', '查看', '查询', '显示'],
        'low': ['有', '多少', '大小', '空间'],
        'objects': ['缓存', '数据', '股票', '文件'],
    },
    'cleanup': {
        'high': ['清理', '清除', '删除', 'clean', 'delete', '清空', '丢掉'],
        'medium': ['删', '丢', '扔', '清', '移除', '擦除'],
        'low': ['旧', '过期', '不要', '没用', '垃圾'],
        'objects': ['缓存', '数据', '空间', '文件'],
    },
    'backtest': {
        'high': ['回测', '回溯', 'backtest', '历史测试'],
        'medium': ['测试', '验证', '试试', '跑一下', '执行'],
        'low': ['策略', '效果', '表现', '收益', '胜率'],
        'objects': ['策略', '双均线', '动量', 'KDJ', 'RSI'],
    },
    'workflow': {
        'high': ['然后', '接着', '再', '之后', 'and then', '&&'],
        'medium': ['并', '且', '同时', '一起'],
        'low': ['先', '后'],
        'objects': [],
    },
}

# 意图同义词映射
INTENT_SYNONYMS = {
    # 下载相关
    '帮我拿下': 'download',
    '帮我获取': 'download',
    '帮我下载': 'download',
    '给我下': 'download',
    '我要下': 'download',
    '我想要': 'download',
    '需要': 'download',
    '下载': 'download',
    '获取': 'download',
    
    # 查看相关（但如果有"走势/数据"等词，应该是下载）
    '看看': 'status',
    '查查': 'status',
    '看一下': 'status',
    '瞅一眼': 'status',
    '显示': 'status',
    '展示': 'status',
    
    # 更新相关
    '刷新下': 'update',
    '更新下': 'update',
    '同步下': 'update',
    '补一下': 'update',
    '补齐': 'update',
    '刷新': 'update',
    '更新': 'update',
    
    # 清理相关
    '清一下': 'cleanup',
    '删一下': 'cleanup',
    '清一清': 'cleanup',
    '删掉': 'cleanup',
    '丢掉': 'cleanup',
    '清理': 'cleanup',
    '清除': 'cleanup',
    
    # 回测相关
    '测一下': 'backtest',
    '跑一下': 'backtest',
    '回测下': 'backtest',
    '回测': 'backtest',
}

# 工作流动词序列
WORKFLOW_PATTERNS = [
    r'(.+?)\s*，\s*然后\s*(.+?)',
    r'(.+?)\s*，\s*接着\s*(.+?)',
    r'(.+?)\s*，\s*再\s*(.+?)',
    r'(.+?)\s*，\s*之后\s*(.+?)',
    r'(.+?)\s*；\s*(.+?)',
    r'(.+?)\s*;\s*(.+?)',
    r'(.+?)\s*，\s*并\s*(.+?)',
    r'(.+?)\s*并\s*(.+?)',
    r'先\s*(.+?)\s*，\s*再\s*(.+?)',
    r'(.+?)\s*，\s*后\s*(.+?)',  # "下完做个回测"
    r'(.+?)\s*完\s*(.+?)',       # "下完做个回测"
]


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

        # 初始化 LLM 意图识别器
        self.llm_recognizer = None
        if LLM_AVAILABLE:
            try:
                self.llm_recognizer = get_llm_recognizer()
                if self.llm_recognizer.available:
                    logger.info("LLM 意图识别器已启用")
                else:
                    logger.info("LLM 意图识别器不可用（API 密钥未设置）")
            except Exception as e:
                logger.warning(f"LLM 意图识别器初始化失败：{e}")

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
    
    def _recognize_intent(self, command: str) -> tuple:
        """
        识别用户意图（混合路由）
        返回：(action, confidence)
        """
        # 1. 优先尝试 LLM（如果可用且命令复杂）
        if LLM_AVAILABLE and self.llm_recognizer and self.llm_recognizer.available:
            # 简单命令直接用规则引擎（快速路径）
            if not self._is_complex_command(command):
                pass  # 跳过 LLM，用规则引擎
            else:
                llm_result = self.llm_recognizer.recognize(command)
                if llm_result['action'] != 'unknown' and llm_result['confidence'] >= 0.6:
                    return llm_result['action'], llm_result['confidence']
        
        # 2. 规则引擎（兜底）
        return self._rule_based_recognize(command)
    
    def _is_complex_command(self, command: str) -> bool:
        """判断是否是复杂命令（需要 LLM 处理）"""
        # 包含多个动作
        action_count = sum(1 for w in ['下载', '更新', '清理', '回测', '分析'] if w in command)
        if action_count >= 2:
            return True
        
        # 长命令（超过 15 个字）
        if len(command) > 25:
            return True
        
        # 包含模糊表达
        fuzzy_words = ['可能', '应该', '好像', '大概', '说不定', '帮我', '给我', '想要']
        if any(w in command for w in fuzzy_words):
            return True
        
        # 包含口语化表达
        colloquial_words = ['看一下', '瞅一眼', '弄一下', '搞一下', '试试看']
        if any(w in command for w in colloquial_words):
            return True
        
        return False
    
    def _rule_based_recognize(self, command: str) -> tuple:
        """基于规则的意图识别（兜底）"""
        command_lower = command.lower()
        
        # 1. 检查同义词映射
        for synonym, intent in INTENT_SYNONYMS.items():
            if synonym in command_lower:
                # 上下文修正：如果有"走势/数据/行情/K 线"等词，"看看"应该是下载
                if intent == 'status' and any(w in command for w in ['走势', '数据', '行情', 'K 线']):
                    return 'download', 0.7
                # 特殊修正："看看有多少/多大/多少"是查询状态
                if intent == 'status' and any(w in command for w in ['多少', '多大', '有', '状态']):
                    return 'status', 0.9
                # 特殊修正："看看股票"（没有"走势/数据"）是查询状态
                if intent == 'status' and '股票' in command and '走势' not in command and '数据' not in command:
                    return 'status', 0.8
                return intent, 0.8
        
        # 2. 检查工作流模式（优先于其他意图）
        for pattern in WORKFLOW_PATTERNS:
            match = re.search(pattern, command)
            if match:
                # 检查工作流是否包含"回测"等动作
                second_part = match.group(2) if match.lastindex >= 2 else ''
                if '回测' in second_part or '测' in second_part:
                    return 'workflow', 0.95
                return 'workflow', 0.9
        
        # 3. 基于关键词的意图识别（带置信度）
        intent_scores = {}
        
        for intent, keywords in INTENT_KEYWORDS.items():
            score = 0.0
            
            # 高置信度关键词匹配
            for word in keywords['high']:
                if word in command_lower:
                    score = max(score, 0.9)
                    break
            
            # 中置信度关键词匹配
            if score < 0.9:
                for word in keywords['medium']:
                    if word in command_lower:
                        score = max(score, 0.7)
                        break
            
            # 低置信度关键词匹配（需要上下文）
            if score < 0.7:
                for word in keywords['low']:
                    if word in command_lower:
                        # 检查是否有相关对象
                        has_object = any(obj in command for obj in keywords.get('objects', []))
                        if has_object:
                            score = max(score, 0.6)
                        else:
                            score = max(score, 0.3)
                        break
            
            if score > 0:
                intent_scores[intent] = score
        
        # 返回最高分数的意图
        if intent_scores:
            best_intent = max(intent_scores, key=intent_scores.get)
            return best_intent, intent_scores[best_intent]
        
        return 'unknown', 0.0

    def parse_command(self, command: str) -> dict:
        """解析命令"""
        command = command.strip()

        result = {
            'type': 'unknown',  # module, ai, system
            'action': None,
            'module': None,
            'params': {},
            'raw': command,
            'confidence': 0.0  # 添加置信度
        }

        # 1. 系统命令
        if command.lower() in ['quit', 'exit', 'q', '退出']:
            result['type'] = 'system'
            result['action'] = 'quit'
            result['confidence'] = 1.0
            return result

        if command.lower() in ['help', 'h', '?', '帮助']:
            result['type'] = 'system'
            result['action'] = 'help'
            result['confidence'] = 1.0
            return result

        if command.lower() in ['modules', 'mods', '模块列表']:
            result['type'] = 'system'
            result['action'] = 'list_modules'
            result['confidence'] = 1.0
            return result

        if command.lower() in ['status', '状态']:
            result['type'] = 'system'
            result['action'] = 'status'
            result['confidence'] = 1.0
            return result

        # 2. 模块调用 (module:action 格式)
        module_match = re.match(r'^(\w+):(\w+)(?:\s+(.*))?$', command)
        if module_match:
            result['type'] = 'module'
            result['module'] = module_match.group(1)
            result['action'] = module_match.group(2)
            result['confidence'] = 1.0
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

        # 使用增强的意图识别
        action, confidence = self._recognize_intent(command)
        result['action'] = action
        result['confidence'] = confidence
        
        # 识别日期范围 - 支持多种格式
        # 格式 1: 20240101-20241231 (8 位日期)
        date_range_match = re.search(r'(\d{8})[\s\-~到至](\d{8})', command)
        if date_range_match:
            result['params']['start_date'] = date_range_match.group(1)
            result['params']['end_date'] = date_range_match.group(2)

        # 格式 2: 240101-241231 (6 位日期，年份简写)
        elif re.search(r'\b(\d{6})[\s\-~到至](\d{6})\b', command):
            short_match = re.search(r'\b(\d{6})[\s\-~到至](\d{6})\b', command)
            if short_match:
                start = short_match.group(1)
                end = short_match.group(2)
                # 年份推断：前 2 位 < 50 则为 20xx，否则为 19xx
                start_yy = int(start[:2])
                end_yy = int(end[:2])
                start_century = '20' if start_yy < 50 else '19'
                end_century = '20' if end_yy < 50 else '19'
                result['params']['start_date'] = f"{start_century}{start}"
                result['params']['end_date'] = f"{end_century}{end}"

        # 识别年份
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

        # 股票名映射
        stock_names = {
            '茅台': '600519.SH',
            '平安银行': '000001.SZ',
            '万科': '000002.SZ',
            '宁德': '300750.SZ',
            '比亚迪': '002594.SZ',
        }
        for name, code in stock_names.items():
            if name in command:
                result['params']['ts_code'] = code
                break

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
