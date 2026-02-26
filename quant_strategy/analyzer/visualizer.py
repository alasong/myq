"""
可视化模块
绘制回测结果图表
"""
import pandas as pd
import numpy as np
from typing import Optional, List
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class Visualizer:
    """
    回测结果可视化
    
    支持绘制：
    - 资产曲线对比图
    - 收益分布图
    - 回撤图
    - 月度热力图
    """
    
    def __init__(self, style: str = "default"):
        """
        初始化可视化器
        
        Args:
            style: matplotlib 样式
        """
        plt.style.use(style)
        self.fig = None
    
    def plot_equity_curve(self, daily_values: pd.DataFrame,
                          benchmark_values: pd.Series = None,
                          title: str = "资产曲线",
                          save_path: str = None) -> plt.Figure:
        """
        绘制资产曲线
        
        Args:
            daily_values: 每日资产数据
            benchmark_values: 基准数据
            title: 图表标题
            save_path: 保存路径
        """
        fig, ax = plt.subplots(figsize=(14, 7))
        
        # 策略资产曲线
        ax.plot(daily_values.index, daily_values["total_value"],
                label="策略", linewidth=2, color="#2196F3")
        
        # 基准曲线
        if benchmark_values is not None and not benchmark_values.empty:
            # 归一化到相同起点
            initial_value = daily_values["total_value"].iloc[0]
            normalized_benchmark = benchmark_values / benchmark_values.iloc[0] * initial_value
            ax.plot(normalized_benchmark.index, normalized_benchmark.values,
                    label="基准", linewidth=2, color="#FF5722", alpha=0.8)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel("日期")
        ax.set_ylabel("资产价值")
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)
        
        # 格式化 x 轴日期
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
        
        self.fig = fig
        return fig
    
    def plot_drawdown(self, daily_values: pd.DataFrame,
                      title: str = "回撤曲线",
                      save_path: str = None) -> plt.Figure:
        """
        绘制回撤曲线
        
        Args:
            daily_values: 每日资产数据
            title: 图表标题
            save_path: 保存路径
        """
        fig, ax = plt.subplots(figsize=(14, 5))
        
        values = daily_values["total_value"]
        cum_returns = (1 + values.pct_change()).cumprod()
        running_max = cum_returns.cummax()
        drawdown = (cum_returns - running_max) / running_max * 100
        
        ax.fill_between(drawdown.index, drawdown.values, 0,
                        color="#FF5722", alpha=0.5)
        ax.plot(drawdown.index, drawdown.values, color="#FF5722", linewidth=1)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel("日期")
        ax.set_ylabel("回撤 (%)")
        ax.grid(True, alpha=0.3)
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
        
        return fig
    
    def plot_returns_distribution(self, daily_values: pd.DataFrame,
                                   title: str = "收益分布",
                                   save_path: str = None) -> plt.Figure:
        """
        绘制收益分布图
        
        Args:
            daily_values: 每日资产数据
            title: 图表标题
            save_path: 保存路径
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        returns = daily_values["total_value"].pct_change().dropna() * 100
        
        # 直方图
        axes[0].hist(returns, bins=50, color="#4CAF50", alpha=0.7, edgecolor='black')
        axes[0].axvline(returns.mean(), color='red', linestyle='--',
                        label=f'均值：{returns.mean():.2f}%')
        axes[0].set_title("日收益分布")
        axes[0].set_xlabel("收益率 (%)")
        axes[0].set_ylabel("频数")
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # QQ 图
        from scipy import stats
        stats.probplot(returns, dist="norm", plot=axes[1])
        axes[1].set_title("QQ 图")
        axes[1].grid(True, alpha=0.3)
        
        plt.suptitle(title, fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
        
        return fig
    
    def plot_monthly_returns(self, daily_values: pd.DataFrame,
                             title: str = "月度收益热力图",
                             save_path: str = None) -> plt.Figure:
        """
        绘制月度收益热力图
        
        Args:
            daily_values: 每日资产数据
            title: 图表标题
            save_path: 保存路径
        """
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # 计算月度收益
        values = daily_values["total_value"]
        monthly = values.resample('M').last().pct_change() * 100
        monthly = monthly.dropna()
        
        # 组织成年月矩阵
        years = monthly.index.year.unique()
        months = list(range(1, 13))
        month_names = ['1 月', '2 月', '3 月', '4 月', '5 月', '6 月',
                       '7 月', '8 月', '9 月', '10 月', '11 月', '12 月']
        
        data = np.full((len(years), 12), np.nan)
        
        for i, year in enumerate(years):
            for j, month in enumerate(months):
                mask = (monthly.index.year == year) & (monthly.index.month == month)
                if mask.any():
                    data[i, j] = monthly[mask].values[0]
        
        # 绘制热力图
        im = ax.imshow(data, cmap='RdYlGn', aspect='auto', vmin=-20, vmax=20)
        
        # 设置刻度和标签
        ax.set_xticks(range(12))
        ax.set_xticklabels(month_names)
        ax.set_yticks(range(len(years)))
        ax.set_yticklabels(years)
        
        # 添加数值标签
        for i in range(len(years)):
            for j in range(12):
                if not np.isnan(data[i, j]):
                    text = ax.text(j, i, f'{data[i, j]:.1f}%',
                                   ha='center', va='center',
                                   color='black' if abs(data[i, j]) < 10 else 'white',
                                   fontsize=9)
        
        # 颜色条
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('收益率 (%)')
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
        
        return fig
    
    def plot_comprehensive(self, daily_values: pd.DataFrame,
                           benchmark_values: pd.Series = None,
                           trades: List[dict] = None,
                           title: str = "回测结果综合分析",
                           save_path: str = None) -> plt.Figure:
        """
        绘制综合图表
        
        Args:
            daily_values: 每日资产数据
            benchmark_values: 基准数据
            trades: 交易记录
            title: 图表标题
            save_path: 保存路径
        """
        fig = plt.figure(figsize=(16, 12))
        gs = GridSpec(3, 2, figure=fig, height_ratios=[2, 1, 1])
        
        # 1. 资产曲线
        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(daily_values.index, daily_values["total_value"],
                 label="策略", linewidth=2, color="#2196F3")
        
        if benchmark_values is not None and not benchmark_values.empty:
            initial_value = daily_values["total_value"].iloc[0]
            normalized_benchmark = benchmark_values / benchmark_values.iloc[0] * initial_value
            ax1.plot(normalized_benchmark.index, normalized_benchmark.values,
                     label="基准", linewidth=2, color="#FF5722", alpha=0.8)
        
        ax1.set_title(title, fontsize=14, fontweight='bold')
        ax1.set_ylabel("资产价值")
        ax1.legend(loc="upper left")
        ax1.grid(True, alpha=0.3)
        
        # 2. 回撤
        ax2 = fig.add_subplot(gs[1, :])
        values = daily_values["total_value"]
        cum_returns = (1 + values.pct_change()).cumprod()
        running_max = cum_returns.cummax()
        drawdown = (cum_returns - running_max) / running_max * 100

        ax2.fill_between(drawdown.index, drawdown.values, 0,
                         color="#FF5722", alpha=0.5)
        ax2.set_ylabel("回撤 (%)")
        ax2.grid(True, alpha=0.3)

        # 3. 收益分布
        ax3 = fig.add_subplot(gs[2, 0])
        returns = daily_values["total_value"].pct_change().dropna() * 100
        ax3.hist(returns, bins=40, color="#4CAF50", alpha=0.7, edgecolor='black')
        ax3.axvline(returns.mean(), color='red', linestyle='--')
        ax3.set_title(f"日收益分布 (均值：{returns.mean():.2f}%)")
        ax3.set_xlabel("收益率 (%)")
        ax3.set_ylabel("频数")
        ax3.grid(True, alpha=0.3)

        # 4. 月度收益
        ax4 = fig.add_subplot(gs[2, 1])
        # 将 date 列设置为索引以便 resample
        values_with_date = values.copy()
        values_with_date.index = pd.to_datetime(daily_values["date"])
        monthly = values_with_date.resample('ME').last().pct_change() * 100
        monthly = monthly.dropna()
        colors = ['green' if r > 0 else 'red' for r in monthly.values]
        ax4.bar(range(len(monthly)), monthly.values, color=colors, alpha=0.7)
        ax4.set_title("月度收益")
        ax4.set_xlabel("月份")
        ax4.set_ylabel("收益率 (%)")
        ax4.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
        
        return fig
    
    def show(self):
        """显示图表"""
        if self.fig:
            plt.show()
    
    def close(self):
        """关闭图表"""
        plt.close('all')
