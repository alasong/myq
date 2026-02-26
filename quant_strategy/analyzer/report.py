"""
报告导出模块
支持 HTML、PDF、Markdown 等格式的报告导出
"""
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd

from loguru import logger


class ReportExporter:
    """报告导出器"""
    
    def __init__(self, output_dir: str = "./output/reports"):
        """
        初始化报告导出器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_html(self, result: Any, save_path: str = None) -> str:
        """
        导出 HTML 格式报告
        
        Args:
            result: BacktestResult 对象
            save_path: 保存路径
            
        Returns:
            保存的文件路径
        """
        if save_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = self.output_dir / f"report_{result.ts_code}_{timestamp}.html"
        else:
            save_path = Path(save_path)
        
        html_content = self._generate_html(result)
        
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML 报告已保存到：{save_path}")
        return str(save_path)
    
    def export_markdown(self, result: Any, save_path: str = None) -> str:
        """
        导出 Markdown 格式报告
        
        Args:
            result: BacktestResult 对象
            save_path: 保存路径
            
        Returns:
            保存的文件路径
        """
        if save_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = self.output_dir / f"report_{result.ts_code}_{timestamp}.md"
        else:
            save_path = Path(save_path)
        
        md_content = self._generate_markdown(result)
        
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(f"Markdown 报告已保存到：{save_path}")
        return str(save_path)
    
    def _generate_html(self, result: Any) -> str:
        """生成 HTML 报告内容"""
        from quant_strategy.analyzer import PerformanceAnalyzer
        
        # 计算额外指标
        analyzer = PerformanceAnalyzer()
        metrics = analyzer.analyze(result.daily_values, None)
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>量化策略回测报告 - {result.ts_code}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-card.positive {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }}
        .metric-card.negative {{
            background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
        }}
        .metric-label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #3498db;
            color: white;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .info-box {{
            background: #e8f4f8;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 20px 0;
        }}
        .trade-list {{
            max-height: 400px;
            overflow-y: auto;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>量化策略回测报告</h1>
        
        <div class="info-box">
            <strong>股票代码:</strong> {result.ts_code}<br>
            <strong>策略名称:</strong> {result.strategy_name}<br>
            <strong>回测区间:</strong> {result.start_date} 至 {result.end_date}<br>
            <strong>报告生成时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        
        <h2>核心指标</h2>
        <div class="metrics-grid">
            <div class="metric-card {'positive' if result.total_return > 0 else 'negative'}">
                <div class="metric-value">{result.total_return:.2%}</div>
                <div class="metric-label">总收益率</div>
            </div>
            <div class="metric-card {'positive' if result.annual_return > 0 else 'negative'}">
                <div class="metric-value">{result.annual_return:.2%}</div>
                <div class="metric-label">年化收益</div>
            </div>
            <div class="metric-card {'positive' if result.sharpe_ratio > 0 else 'negative'}">
                <div class="metric-value">{result.sharpe_ratio:.2f}</div>
                <div class="metric-label">夏普比率</div>
            </div>
            <div class="metric-card negative">
                <div class="metric-value">{result.max_drawdown:.2%}</div>
                <div class="metric-label">最大回撤</div>
            </div>
        </div>
        
        <h2>详细指标</h2>
        <table>
            <tr><th>指标</th><th>数值</th></tr>
            <tr><td>初始资金</td><td>{result.initial_cash:,.2f}</td></tr>
            <tr><td>最终资产</td><td>{result.final_value:,.2f}</td></tr>
            <tr><td>总收益率</td><td>{result.total_return:.2%}</td></tr>
            <tr><td>年化收益率</td><td>{result.annual_return:.2%}</td></tr>
            <tr><td>基准收益率</td><td>{result.benchmark_return:.2%}</td></tr>
            <tr><td>Alpha</td><td>{result.alpha:.2%}</td></tr>
            <tr><td>Beta</td><td>{result.beta:.2f}</td></tr>
            <tr><td>夏普比率</td><td>{result.sharpe_ratio:.2f}</td></tr>
            <tr><td>最大回撤</td><td>{result.max_drawdown:.2%}</td></tr>
            <tr><td>胜率</td><td>{result.win_rate:.2%}</td></tr>
            <tr><td>盈亏比</td><td>{result.profit_factor:.2f}</td></tr>
            <tr><td>总交易次数</td><td>{result.total_trades}</td></tr>
        </table>
        
        <h2>交易记录</h2>
        <div class="trade-list">
            <table>
                <tr>
                    <th>日期</th>
                    <th>方向</th>
                    <th>股数</th>
                    <th>成交价</th>
                    <th>手续费</th>
                    <th>滑点</th>
                </tr>
"""
        
        # 添加交易记录
        if hasattr(result, 'trades') and result.trades:
            for trade in result.trades[:100]:  # 限制显示 100 条
                html += f"""
                <tr>
                    <td>{trade.get('timestamp', 'N/A')}</td>
                    <td>{trade.get('direction', 'N/A')}</td>
                    <td>{trade.get('shares', 0)}</td>
                    <td>{trade.get('filled_price', 0):.2f}</td>
                    <td>{trade.get('commission', 0):.2f}</td>
                    <td>{trade.get('slippage', 0):.2f}</td>
                </tr>
                """
        
        html += """
            </table>
        </div>
        
        <h2>每日资产变化（前 20 条）</h2>
        <table>
            <tr>
                <th>日期</th>
                <th>总资产</th>
                <th>现金</th>
                <th>日收益率</th>
                <th>累计收益率</th>
            </tr>
"""
        
        # 添加每日资产变化
        if hasattr(result, 'daily_values') and result.daily_values is not None:
            df = result.daily_values.head(20)
            for idx, row in df.iterrows():
                date_val = row.get('date', idx)
                if hasattr(date_val, 'strftime'):
                    date_str = date_val.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_val)
                
                html += f"""
            <tr>
                <td>{date_str}</td>
                <td>{row.get('total_value', 0):,.2f}</td>
                <td>{row.get('cash', 0):,.2f}</td>
                <td>{row.get('daily_return', 0):.2%}</td>
                <td>{row.get('cum_return', 0):.2%}</td>
            </tr>
            """
        
        html += """
        </table>
        
        <footer style="margin-top: 40px; text-align: center; color: #7f8c8d; font-size: 0.9em;">
            <p>Generated by 量化策略回测系统</p>
        </footer>
    </div>
</body>
</html>
"""
        
        return html
    
    def _generate_markdown(self, result: Any) -> str:
        """生成 Markdown 报告内容"""
        md = f"""# 量化策略回测报告

## 基本信息

| 项目 | 值 |
|------|-----|
| 股票代码 | {result.ts_code} |
| 策略名称 | {result.strategy_name} |
| 回测区间 | {result.start_date} 至 {result.end_date} |
| 报告生成时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |

## 核心指标

| 指标 | 数值 |
|------|------|
| 总收益率 | {result.total_return:.2%} |
| 年化收益率 | {result.annual_return:.2%} |
| 夏普比率 | {result.sharpe_ratio:.2f} |
| 最大回撤 | {result.max_drawdown:.2%} |
| 胜率 | {result.win_rate:.2%} |
| 盈亏比 | {result.profit_factor:.2f} |

## 详细指标

| 指标 | 数值 |
|------|------|
| 初始资金 | {result.initial_cash:,.2f} |
| 最终资产 | {result.final_value:,.2f} |
| 基准收益率 | {result.benchmark_return:.2%} |
| Alpha | {result.alpha:.2%} |
| Beta | {result.beta:.2f} |
| 总交易次数 | {result.total_trades} |

## 交易记录

"""
        
        if hasattr(result, 'trades') and result.trades:
            md += "| 日期 | 方向 | 股数 | 成交价 | 手续费 | 滑点 |\n"
            md += "|------|------|------|--------|--------|------|\n"
            
            for trade in result.trades[:50]:
                md += f"| {trade.get('timestamp', 'N/A')} | {trade.get('direction', 'N/A')} | {trade.get('shares', 0)} | {trade.get('filled_price', 0):.2f} | {trade.get('commission', 0):.2f} | {trade.get('slippage', 0):.2f} |\n"
        
        md += "\n---\n*Generated by 量化策略回测系统*\n"
        
        return md
