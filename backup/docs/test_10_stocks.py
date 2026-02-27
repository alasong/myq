"""
测试获取 10 只股票数据
"""
from quant_strategy.data.tushare_provider import TushareDataProvider

p = TushareDataProvider()

# 测试 10 只不同类型的股票
test_stocks = [
    ('000001.SZ', '平安银行'),
    ('000002.SZ', '万科 A'),
    ('600519.SH', '贵州茅台'),
    ('601398.SH', '工商银行'),
    ('300750.SZ', '宁德时代'),
    ('002594.SZ', '比亚迪'),
    ('600036.SH', '招商银行'),
    ('000858.SZ', '五粮液'),
    ('300059.SZ', '东方财富'),
    ('601127.SH', '赛力斯'),
]

print("=" * 60)
print("测试获取 10 只股票 2025 年数据")
print("=" * 60)

success_count = 0
fail_count = 0

for ts_code, name in test_stocks:
    print(f'\n测试：{ts_code} - {name}')
    try:
        df = p.get_daily_data(ts_code, '20250101', '20251231', 'qfq')
        if not df.empty:
            print(f'  [OK] 获取成功：{len(df)} 天')
            success_count += 1
        else:
            print(f'  [FAIL] 获取失败：空数据')
            fail_count += 1
    except Exception as e:
        print(f'  [FAIL] 异常：{e}')
        fail_count += 1

print("\n" + "=" * 60)
print(f"测试结果：成功 {success_count} 只，失败 {fail_count} 只")
print("=" * 60)

if success_count == 10:
    print("\n[OK] 所有测试通过！可以开始批量下载")
    print("\n运行命令:")
    print("  python -m quant_strategy.tools.fetch_all_stocks --start 20250101 --end 20251231 --batch 50")
else:
    print(f"\n[WARN] 有 {fail_count} 只股票失败，请检查问题")
