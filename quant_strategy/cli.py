#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
量化策略系统 - 统一入口

支持：
- AI 交互模式
- 模块直接调用
- 命令行回测
- 数据管理

使用方法:
    # AI 交互模式
    python -m quant_strategy.cli ai
    
    # 模块调用
    python -m quant_strategy.cli module data:list-stocks
    
    # 回测
    python -m quant_strategy.cli backtest --strategy dual_ma --ts_code 000001.SZ
    
    # 数据管理
    python -m quant_strategy.cli data download --ts_codes 000001.SZ
"""
import sys
import argparse
from pathlib import Path


def main():
    """主函数"""
    import sys as _sys
    
    parser = argparse.ArgumentParser(
        description='量化策略系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # AI 交互模式
  python -m quant_strategy.cli ai
  
  # 查看股票列表
  python -m quant_strategy.cli module data:list-stocks
  
  # 查看策略详情
  python -m quant_strategy.cli module strategy:info name=dual_ma
  
  # 运行回测
  python -m quant_strategy.cli backtest --strategy dual_ma --ts_code 000001.SZ
        """
    )
    
    subparsers = parser.add_subparsers(dest='cmd', help='可用命令')

    # ========== AI 交互模式 ==========
    ai_parser = subparsers.add_parser('ai', help='AI 交互模式')
    ai_parser.add_argument('--token', type=str, help='Tushare Token')
    ai_parser.add_argument('-c', '--command', type=str, help='单次执行的命令')

    # ========== 模块调用 ==========
    module_parser = subparsers.add_parser('module', help='模块直接调用')
    module_parser.add_argument('call', type=str, help='模块调用 (格式：module:action key=value)')

    # ========== 回测 ==========
    backtest_parser = subparsers.add_parser('backtest', help='运行回测')
    backtest_parser.add_argument('--strategy', type=str, required=True, help='策略名称')
    backtest_parser.add_argument('--ts_code', type=str, required=True, help='股票代码')
    backtest_parser.add_argument('--start-date', type=str, help='开始日期')
    backtest_parser.add_argument('--end-date', type=str, help='结束日期')
    backtest_parser.add_argument('--workers', type=int, default=1, help='并发数')

    # ========== 数据管理 ==========
    data_parser = subparsers.add_parser('data', help='数据管理')
    data_subparsers = data_parser.add_subparsers(dest='data_command')

    # 下载数据
    download_parser = data_subparsers.add_parser('download', help='下载数据')
    download_parser.add_argument('--ts_codes', nargs='+', help='股票代码列表')
    download_parser.add_argument('--start_date', type=str, help='开始日期')
    download_parser.add_argument('--end_date', type=str, help='结束日期')
    download_parser.add_argument('--workers', type=int, default=4, help='并发线程数')

    # 查看缓存
    cache_parser = data_subparsers.add_parser('cache', help='缓存管理')
    cache_parser.add_argument('action', choices=['status', 'stats', 'clear'], help='操作')
    
    # ========== 版本信息 ==========
    parser.add_argument('--version', '-v', action='version', version='%(prog)s 2.0.0')
    
    args = parser.parse_args()
    
    if args.cmd == 'ai':
        # AI 交互模式
        from quant_strategy.tools.ai_assistant_pro import main as ai_main
        
        # 构建新的 sys.argv
        new_argv = ['ai_assistant_pro']
        if args.token:
            new_argv.extend(['--token', args.token])
        if args.command:  # 只有指定了命令才传递
            new_argv.extend(['--command', args.command])
        
        # 保存原 argv
        old_argv = _sys.argv
        _sys.argv = new_argv
        
        try:
            ai_main()
        finally:
            _sys.argv = old_argv
        
    elif args.cmd == 'module':
        # 模块调用
        from quant_strategy.modules.base import get_module_registry
        from quant_strategy.data.tushare_provider import TushareDataProvider
        from quant_strategy.data.data_cache import DataCache
        from quant_strategy.modules import data_module  # 注册数据模块
        from quant_strategy.modules import strategy_module  # 注册策略模块
        import os
        
        # 初始化模块注册表
        registry = get_module_registry()
        
        # 初始化数据源
        token = os.getenv('TUSHARE_TOKEN', '')
        if token:
            provider = TushareDataProvider(token=token, use_cache=True)
            registry.set_context('provider', provider)
            registry.set_context('cache', provider.cache)
        
        # 解析模块调用
        call = args.call
        parts = call.split(':')
        if len(parts) < 2:
            print(f"错误：无效的模块调用格式 '{call}'")
            print("格式：module:action key=value ...")
            sys.exit(1)
        
        module_name = parts[0]
        action = parts[1]
        
        # 解析参数
        params = {}
        for part in parts[2:]:
            if '=' in part:
                k, v = part.split('=', 1)
                params[k] = v
        
        # 执行模块
        module = registry.get(module_name)
        if not module:
            print(f"错误：未找到模块 '{module_name}'")
            print(f"可用模块：{registry.list_modules()}")
            sys.exit(1)
        
        result = module.execute(action, **params)
        print(result)
        
        if result.data and isinstance(result.data, dict):
            print("\n数据:")
            for k, v in result.data.items():
                print(f"  {k}: {v}")
        
        sys.exit(0 if result.success else 1)
        
    elif args.cmd == 'backtest':
        # 运行回测
        from quant_strategy.main import run_backtest
        
        config = {
            'strategy': args.strategy,
            'ts_code': args.ts_code,
            'start_date': args.start_date,
            'end_date': args.end_date,
        }
        
        result = run_backtest(config)
        print(f"\n回测完成!")
        print(f"总收益：{result.get('total_return', 0):.2f}%")
        
    elif args.cmd == 'data':
        # 数据管理
        from quant_strategy.data.tushare_provider import TushareDataProvider
        from quant_strategy.data.data_cache import DataCache
        from quant_strategy.tools.fetch_all_stocks import fetch_and_cache_stocks, get_all_stocks
        import os
        
        token = os.getenv('TUSHARE_TOKEN', '')
        if not token:
            print("错误：请设置 TUSHARE_TOKEN 环境变量")
            sys.exit(1)
        
        provider = TushareDataProvider(token=token, use_cache=True)
        
        if args.data_command == 'download':
            ts_codes = args.ts_codes or get_all_stocks(provider)
            fetch_and_cache_stocks(
                provider=provider,
                ts_codes=ts_codes,
                start_date=args.start_date,
                end_date=args.end_date,
                workers=args.workers
            )
            
        elif args.data_command == 'cache':
            cache = provider.cache
            if args.action == 'status':
                stats = cache.get_cache_report()
                print(f"缓存状态:")
                print(f"  总文件数：{stats['total_files']}")
                print(f"  缓存大小：{stats['total_size_mb']:.2f} MB")
                print(f"  股票数量：{stats['stock_count']}")
            elif args.action == 'stats':
                stats = cache.get_stats()
                print(f"缓存统计:")
                for k, v in stats.items():
                    print(f"  {k}: {v}")
            elif args.action == 'clear':
                cache.clear(older_than_days=30)
                print("缓存清理完成")
        
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
