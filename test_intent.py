"""测试当前系统的意图识别能力"""
from quant_strategy.tools.ai_assistant_pro import AIAssistantPro

ai = AIAssistantPro()

test_cases = [
    # 常见用户表达
    ("下载茅台 2024 年数据", "download"),
    ("帮我拿下茅台 2024 年的数据", "download"),
    ("我想看看茅台去年走势", "download"),
    ("把 2024 年的数据更新一下", "update"),
    ("查查缓存多大", "status"),
    ("删掉那些旧数据", "cleanup"),
    ("回测一下双均线策略", "backtest"),
    ("茅台和平安银行，下完做个回测", "workflow"),
    ("最近数据可能不准，刷新下", "update"),
    ("清理一下空间", "cleanup"),
    ("看看现在有多少股票", "status"),
    ("帮我获取宁德时代的全部数据", "download"),
]

print("\n" + "=" * 70)
print("AI 意图识别测试")
print("=" * 70)

correct = 0
for cmd, expected in test_cases:
    result = ai.parse_command(cmd)
    actual = result['action']
    match = "OK " if actual == expected else "FAIL"
    if actual == expected:
        correct += 1
    print(f"{match} {cmd:25} -> 识别：{actual:12} (期望：{expected})")

print("=" * 70)
print(f"通过率：{correct}/{len(test_cases)} = {correct/len(test_cases)*100:.1f}%")
print("=" * 70 + "\n")
