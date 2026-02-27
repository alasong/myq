"""
AI 交互接口 - 股票数据下载助手

支持自然语言命令：
- "下载 2025 年数据"
- "下载 250101-251231 的股票"
- "获取茅台的数据"
- "更新缓存"
- "查看缓存状态"
- "清理缓存"

使用方法：
    python -m quant_strategy.tools.ai_assistant
"""
import sys
import os
import re
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from quant_strategy.data.tushare_provider import TushareDataProvider
from quant_strategy.data.data_cache import DataCache
from quant_strategy.tools.fetch_all_stocks import fetch_and_cache_stocks, get_all_stocks


class AIAssistant:
    """AI 助手"""
    
    def __init__(self, token: str = None):
        """初始化 AI 助手"""
        self.token = token or os.getenv('TUSHARE_TOKEN', '')
        self.provider = None
        self.cache = None
        self._init_data_source()
    
    def _init_data_source(self):
        """初始化数据源"""
        import os
        token = self.token or os.getenv('TUSHARE_TOKEN', '')
        if token:
            try:
                self.provider = TushareDataProvider(token=token, use_cache=True)
                self.cache = self.provider.cache
                logger.info("数据源初始化成功")
            except Exception as e:
                logger.warning(f"数据源初始化失败：{e}")
        else:
            logger.warning("未设置 TUSHARE_TOKEN，部分功能不可用")
    
    def parse_command(self, command: str) -> dict:
        """
        解析自然语言命令
        
        Args:
            command: 自然语言命令
        
        Returns:
            解析后的命令字典
        """
        command = command.lower().strip()
        
        result = {
            'action': None,
            'start_date': None,
            'end_date': None,
            'ts_codes': [],
            'workers': 4,
        }
        
        # 1. 识别动作
        if any(word in command for word in ['下载', '获取', 'get', 'download', 'fetch']):
            result['action'] = 'download'
        elif any(word in command for word in ['查看', '状态', 'status', 'check', 'list']):
            result['action'] = 'status'
        elif any(word in command for word in ['清理', '清除', 'clean', 'clear', 'delete']):
            result['action'] = 'cleanup'
        elif any(word in command for word in ['帮助', 'help', 'usage']):
            result['action'] = 'help'
        elif any(word in command for word in ['更新', 'update', 'refresh']):
            result['action'] = 'update'
        # 支持疑问句式
        elif any(word in command for word in ['哪年', '哪些年', '有什么', '支持什么', '可以']):
            result['action'] = 'help'
        elif '?' in command or '？' in command:
            result['action'] = 'help'
        else:
            result['action'] = 'unknown'
        
        # 2. 识别日期范围（在转小写前先提取）
        # 格式 1: 20250101-20251231
        date_pattern1 = r'(\d{8})[\s\-~到至](\d{8})'
        match = re.search(date_pattern1, command)
        if match:
            result['start_date'] = match.group(1)
            result['end_date'] = match.group(2)

        # 格式 2: 250101-251231 (6 位年份)
        date_pattern2 = r'(\d{6})[\s\-~到至](\d{6})'
        match = re.search(date_pattern2, command)
        if match and not result['start_date']:
            start = match.group(1)
            end = match.group(2)
            # 转换为 8 位
            result['start_date'] = '20' + start if len(start) == 6 else start
            result['end_date'] = '20' + end if len(end) == 6 else end

        # 格式 3: 2025 年 (注意：command 已经转小写，但中文不变)
        year_pattern = r'(20\d{2})\s*年'
        match = re.search(year_pattern, command)
        if match and not result['start_date']:
            year = match.group(1)
            result['start_date'] = year + '0101'
            result['end_date'] = year + '1231'
        
        # 格式 4: 今年
        if '今年' in command or 'this year' in command or 'current year' in command:
            year = str(datetime.now().year)
            result['start_date'] = year + '0101'
            result['end_date'] = year + '1231'
        
        # 格式 5: 去年
        if '去年' in command or 'last year' in command:
            year = str(datetime.now().year - 1)
            result['start_date'] = year + '0101'
            result['end_date'] = year + '1231'
        
        # 3. 识别股票代码
        # 识别具体股票名（简化版）
        stock_names = {
            '茅台': '600519.SH',
            '平安银行': '000001.SZ',
            '万科': '000002.SZ',
            '宁德': '300750.SZ',
            '比亚迪': '002594.SZ',
        }
        
        for name, code in stock_names.items():
            if name in command:
                result['ts_codes'].append(code)
        
        # 识别股票代码格式
        code_pattern = r'(\d{6}\.(SZ|SH|BJ))'
        matches = re.findall(code_pattern, command, re.IGNORECASE)
        for match in matches:
            result['ts_codes'].append(match[0].upper())
        
        # 4. 识别线程数
        workers_pattern = r'(\d+)\s*[个线程]?线程|workers?\s*[:=]?\s*(\d+)'
        match = re.search(workers_pattern, command)
        if match:
            workers = int(match.group(1) or match.group(2))
            result['workers'] = min(max(workers, 1), 8)  # 限制 1-8 线程
        
        # 5. 识别"全部股票"
        if any(word in command for word in ['全部', '所有', 'all', '批量']):
            result['ts_codes'] = []  # 空列表表示全部
        
        return result
    
    def execute(self, command: str) -> bool:
        """
        执行命令
        
        Args:
            command: 自然语言命令
        
        Returns:
            是否成功
        """
        print(f"\n收到命令：{command}")
        print("-" * 60)
        
        # 解析命令
        parsed = self.parse_command(command)
        action = parsed['action']
        
        print(f"解析结果：{parsed}")
        print("-" * 60)
        
        # 执行动作
        if action == 'download':
            return self._execute_download(parsed)
        elif action == 'status':
            return self._execute_status()
        elif action == 'cleanup':
            return self._execute_cleanup()
        elif action == 'update':
            return self._execute_update(parsed)
        elif action == 'help':
            return self._execute_help()
        else:
            print(f"❌ 未知命令：{command}")
            return False
    
    def _execute_download(self, parsed: dict) -> bool:
        """执行下载命令"""
        if not parsed['start_date'] or not parsed['end_date']:
            print("❌ 请指定日期范围，例如：下载 2025 年数据")
            return False
        
        print(f"开始下载：{parsed['start_date']} - {parsed['end_date']}")
        print(f"并发线程：{parsed['workers']}")
        
        if not self.provider:
            print("❌ 数据源未初始化，请设置 TUSHARE_TOKEN")
            return False
        
        try:
            # 获取股票列表
            if parsed['ts_codes']:
                ts_codes = parsed['ts_codes']
                print(f"指定股票：{len(ts_codes)} 只")
            else:
                print("获取全部股票列表...")
                ts_codes = get_all_stocks(self.provider)
                print(f"全部股票：{len(ts_codes)} 只")
            
            # 执行下载
            fetch_and_cache_stocks(
                provider=self.provider,
                ts_codes=ts_codes,
                start_date=parsed['start_date'],
                end_date=parsed['end_date'],
                batch_size=50,
                force=False,
                workers=parsed['workers']
            )
            
            print("\n✅ 下载完成！")
            return True
            
        except Exception as e:
            print(f"❌ 下载失败：{e}")
            return False
    
    def _execute_status(self) -> bool:
        """执行状态查询"""
        if not self.cache:
            print("❌ 缓存未初始化")
            return False
        
        try:
            stats = self.cache.get_cache_report()
            
            print("\n📊 缓存状态")
            print("=" * 60)
            print(f"总文件数：{stats['total_files']}")
            print(f"缓存大小：{stats['total_size_mb']:.2f} MB")
            print(f"股票数量：{stats['stock_count']}")
            print(f"完整数据：{stats['complete_count']}")
            print(f"不完整：{stats['incomplete_count']}")
            
            if stats['by_type']:
                print("\n按类型:")
                for data_type, count in stats['by_type'].items():
                    print(f"  {data_type}: {count} 个")
            
            print("=" * 60)
            return True
            
        except Exception as e:
            print(f"❌ 查询失败：{e}")
            return False
    
    def _execute_cleanup(self) -> bool:
        """执行清理命令"""
        if not self.cache:
            print("❌ 缓存未初始化")
            return False
        
        try:
            print("\n🧹 清理缓存...")
            print("=" * 60)
            
            # 显示清理前统计
            stats_before = self.cache.get_cache_stats()
            print(f"清理前：{stats_before['total_files']} 个文件，{stats_before['total_size_mb']:.2f} MB")
            
            # 清理过期缓存（30 天）
            self.cache.clear(older_than_days=30)
            
            # 显示清理后统计
            stats_after = self.cache.get_cache_stats()
            print(f"清理后：{stats_after['total_files']} 个文件，{stats_after['total_size_mb']:.2f} MB")
            
            saved = stats_before['total_size_mb'] - stats_after['total_size_mb']
            print(f"节省空间：{saved:.2f} MB")
            print("=" * 60)
            print("✅ 清理完成！")
            return True
            
        except Exception as e:
            print(f"❌ 清理失败：{e}")
            return False
    
    def _execute_update(self, parsed: dict) -> bool:
        """执行更新命令"""
        # 更新最近 30 天的数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        
        parsed['start_date'] = start_date
        parsed['end_date'] = end_date
        
        print(f"更新最近 30 天数据：{start_date} - {end_date}")
        return self._execute_download(parsed)
    
    def _execute_help(self) -> bool:
        """显示帮助信息"""
        print("\n📖 AI 助手使用指南")
        print("=" * 60)
        print("\n支持的命令:")
        print("  1. 下载数据:")
        print("     - 下载 2025 年数据")
        print("     - 下载 250101-251231 的股票")
        print("     - 获取 20240101 到 20241231 的数据")
        print("     - 下载茅台的数据（2025 年）")
        print("     - 批量下载全部股票（4 线程）")
        print("")
        print("  2. 查看状态:")
        print("     - 查看缓存状态")
        print("     - 状态")
        print("")
        print("  3. 清理缓存:")
        print("     - 清理缓存")
        print("     - 清除 30 天前的数据")
        print("")
        print("  4. 更新数据:")
        print("     - 更新数据")
        print("     - 更新最近 30 天")
        print("")
        print("  5. 帮助:")
        print("     - 帮助")
        print("     - help")
        print("")
        print("=" * 60)
        return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='AI 股票数据助手')
    parser.add_argument('--token', type=str, help='Tushare Token')
    parser.add_argument('command', nargs='?', help='自然语言命令')
    
    args = parser.parse_args()
    
    # 创建 AI 助手
    assistant = AIAssistant(token=args.token)
    
    # 显示欢迎信息
    print("\n" + "=" * 60)
    print("  AI 股票数据助手")
    print("=" * 60)
    print("输入命令（或输入 'help' 查看帮助，'quit' 退出）")
    print("=" * 60)
    
    # 交互式模式
    if not args.command:
        while True:
            try:
                command = input("\n> ").strip()
                
                if command.lower() in ['quit', 'exit', 'q']:
                    print("再见！")
                    break
                
                if command:
                    assistant.execute(command)
                    
            except KeyboardInterrupt:
                print("\n再见！")
                break
            except Exception as e:
                print(f"❌ 错误：{e}")
    
    # 单次命令模式
    else:
        assistant.execute(args.command)


if __name__ == "__main__":
    import os
    from datetime import timedelta
    main()
