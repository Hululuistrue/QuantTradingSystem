#!/usr/bin/env python3
"""
图表生成模块 - 为量化交易策略生成可视化图表
支持：价格走势图、技术指标图、策略信号图、回测结果图
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
from io import BytesIO
import base64
import json
from datetime import datetime, timedelta
import yfinance as yf

# 使用默认字体，避免中文字体问题
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

class TradingChartGenerator:
    """交易图表生成器"""
    
    def __init__(self):
        self.figsize = (12, 8)
        self.dpi = 100
        
    def generate_price_chart(self, symbol, period='1mo', interval='1d'):
        """
        生成价格走势图
        """
        try:
            # 获取股票数据
            stock = yf.Ticker(symbol)
            df = stock.history(period=period, interval=interval)
            
            if df.empty:
                return None
            
            # 创建图表
            fig, axes = plt.subplots(2, 1, figsize=self.figsize, 
                                    gridspec_kw={'height_ratios': [3, 1]})
            
            # 价格图表
            ax1 = axes[0]
            ax1.plot(df.index, df['Close'], label='Close Price', linewidth=2, color='blue')
            ax1.fill_between(df.index, df['Low'], df['High'], 
                           alpha=0.2, color='gray', label='Price Range')
            ax1.set_title(f'{symbol} Price Chart ({period})', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Price (USD)', fontsize=12)
            ax1.legend(loc='upper left')
            ax1.grid(True, alpha=0.3)
            
            # 成交量图表
            ax2 = axes[1]
            colors = ['green' if close >= open_ else 'red' 
                     for close, open_ in zip(df['Close'], df['Open'])]
            ax2.bar(df.index, df['Volume'], color=colors, alpha=0.7)
            ax2.set_ylabel('Volume', fontsize=12)
            ax2.set_xlabel('Date', fontsize=12)
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # 转换为base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=self.dpi, bbox_inches='tight')
            buffer.seek(0)
            img_str = base64.b64encode(buffer.read()).decode()
            plt.close(fig)
            
            return {
                'symbol': symbol,
                'period': period,
                'chart_type': 'price_volume',
                'image_base64': img_str,
                'data_points': len(df),
                'date_range': {
                    'start': df.index[0].strftime('%Y-%m-%d'),
                    'end': df.index[-1].strftime('%Y-%m-%d')
                }
            }
            
        except Exception as e:
            print(f"生成价格图表错误: {e}")
            return None
    
    def generate_strategy_chart(self, symbol, fast_period=10, slow_period=30, period='3mo'):
        """
        生成策略图表（双均线交叉策略）
        """
        try:
            # 获取股票数据
            stock = yf.Ticker(symbol)
            df = stock.history(period=period, interval='1d')
            
            if df.empty or len(df) < slow_period:
                return None
            
            # 计算技术指标
            df['MA_Fast'] = df['Close'].rolling(window=fast_period).mean()
            df['MA_Slow'] = df['Close'].rolling(window=slow_period).mean()
            
            # 生成交易信号
            df['Signal'] = 0
            df.loc[df['MA_Fast'] > df['MA_Slow'], 'Signal'] = 1  # 买入信号
            df.loc[df['MA_Fast'] < df['MA_Slow'], 'Signal'] = -1  # 卖出信号
            
            # 创建图表
            fig, axes = plt.subplots(3, 1, figsize=(self.figsize[0], 10),
                                    gridspec_kw={'height_ratios': [3, 1, 1]})
            
            # 价格和均线图表
            ax1 = axes[0]
            ax1.plot(df.index, df['Close'], label='Close Price', linewidth=2, color='blue', alpha=0.7)
            ax1.plot(df.index, df['MA_Fast'], label=f'{fast_period}-Day Fast MA', 
                    linewidth=2, color='orange')
            ax1.plot(df.index, df['MA_Slow'], label=f'{slow_period}-Day Slow MA', 
                    linewidth=2, color='red')
            
            # 标记交易信号
            buy_signals = df[df['Signal'] == 1]
            sell_signals = df[df['Signal'] == -1]
            
            if not buy_signals.empty:
                ax1.scatter(buy_signals.index, buy_signals['Close'], 
                          color='green', marker='^', s=100, label='Buy Signal', zorder=5)
            if not sell_signals.empty:
                ax1.scatter(sell_signals.index, sell_signals['Close'], 
                          color='red', marker='v', s=100, label='Sell Signal', zorder=5)
            
            ax1.set_title(f'{symbol} Moving Average Crossover ({fast_period}/{slow_period} Days)', 
                         fontsize=14, fontweight='bold')
            ax1.set_ylabel('Price (USD)', fontsize=12)
            ax1.legend(loc='upper left')
            ax1.grid(True, alpha=0.3)
            
            # 均线差值图表
            ax2 = axes[1]
            df['MA_Diff'] = df['MA_Fast'] - df['MA_Slow']
            ax2.fill_between(df.index, 0, df['MA_Diff'], 
                           where=df['MA_Diff'] >= 0, color='green', alpha=0.5, label='Fast > Slow')
            ax2.fill_between(df.index, 0, df['MA_Diff'], 
                           where=df['MA_Diff'] < 0, color='red', alpha=0.5, label='Fast < Slow')
            ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax2.set_ylabel('MA Difference', fontsize=12)
            ax2.legend(loc='upper left')
            ax2.grid(True, alpha=0.3)
            
            # 成交量图表
            ax3 = axes[2]
            colors = ['green' if close >= open_ else 'red' 
                     for close, open_ in zip(df['Close'], df['Open'])]
            ax3.bar(df.index, df['Volume'], color=colors, alpha=0.7)
            ax3.set_ylabel('Volume', fontsize=12)
            ax3.set_xlabel('Date', fontsize=12)
            ax3.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # 转换为base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=self.dpi, bbox_inches='tight')
            buffer.seek(0)
            img_str = base64.b64encode(buffer.read()).decode()
            plt.close(fig)
            
            # 计算策略统计
            signals = df['Signal'].dropna()
            buy_count = (signals == 1).sum()
            sell_count = (signals == -1).sum()
            
            return {
                'symbol': symbol,
                'strategy': 'moving_average_crossover',
                'parameters': {
                    'fast_period': fast_period,
                    'slow_period': slow_period
                },
                'chart_type': 'strategy',
                'image_base64': img_str,
                'signals': {
                    'buy_count': int(buy_count),
                    'sell_count': int(sell_count),
                    'total_signals': int(buy_count + sell_count)
                },
                'data_points': len(df),
                'date_range': {
                    'start': df.index[0].strftime('%Y-%m-%d'),
                    'end': df.index[-1].strftime('%Y-%m-%d')
                }
            }
            
        except Exception as e:
            print(f"生成策略图表错误: {e}")
            return None
    
    def generate_backtest_chart(self, symbol, initial_capital=10000, period='6mo'):
        """
        生成回测结果图表
        """
        try:
            # 获取股票数据
            stock = yf.Ticker(symbol)
            df = stock.history(period=period, interval='1d')
            
            if df.empty or len(df) < 60:  # 至少需要60天数据
                return None
            
            # 简单回测逻辑
            df['MA_Fast'] = df['Close'].rolling(window=10).mean()
            df['MA_Slow'] = df['Close'].rolling(window=30).mean()
            df['Signal'] = 0
            df.loc[df['MA_Fast'] > df['MA_Slow'], 'Signal'] = 1
            df.loc[df['MA_Fast'] < df['MA_Slow'], 'Signal'] = -1
            
            # 计算持仓和收益
            df['Position'] = df['Signal'].shift(1)
            df['Returns'] = df['Close'].pct_change()
            df['Strategy_Returns'] = df['Position'] * df['Returns']
            
            # 计算累计收益
            df['Cumulative_Market'] = (1 + df['Returns']).cumprod()
            df['Cumulative_Strategy'] = (1 + df['Strategy_Returns']).cumprod()
            
            # 创建图表
            fig, axes = plt.subplots(2, 1, figsize=(self.figsize[0], 10),
                                    gridspec_kw={'height_ratios': [2, 1]})
            
            # 累计收益对比
            ax1 = axes[0]
            ax1.plot(df.index, df['Cumulative_Market'], 
                    label='Market Return (Buy & Hold)', linewidth=2, color='blue')
            ax1.plot(df.index, df['Cumulative_Strategy'], 
                    label='Strategy Return (MA Crossover)', linewidth=2, color='green')
            ax1.set_title(f'{symbol} Backtest Results', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Cumulative Return Multiple', fontsize=12)
            ax1.legend(loc='upper left')
            ax1.grid(True, alpha=0.3)
            
            # 月度收益热力图
            ax2 = axes[1]
            # 计算月度收益
            monthly_returns = df['Strategy_Returns'].resample('M').apply(
                lambda x: (1 + x).prod() - 1
            )
            
            # 创建月度收益矩阵
            monthly_matrix = []
            years = sorted(set(monthly_returns.index.year))
            months = range(1, 13)
            
            for year in years:
                year_returns = []
                for month in months:
                    try:
                        ret = monthly_returns.loc[f'{year}-{month:02d}']
                        year_returns.append(ret)
                    except:
                        year_returns.append(np.nan)
                monthly_matrix.append(year_returns)
            
            monthly_matrix = np.array(monthly_matrix)
            
            # 绘制热力图
            im = ax2.imshow(monthly_matrix, cmap='RdYlGn', aspect='auto', 
                          vmin=-0.2, vmax=0.2)
            
            # 设置坐标轴
            ax2.set_xticks(range(12))
            ax2.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
            ax2.set_yticks(range(len(years)))
            ax2.set_yticklabels(years)
            ax2.set_title('Monthly Returns Heatmap', fontsize=12)
            
            # 添加颜色条
            plt.colorbar(im, ax=ax2, label='Return Rate')
            
            # 在单元格中添加文本
            for i in range(len(years)):
                for j in range(12):
                    if not np.isnan(monthly_matrix[i, j]):
                        text = ax2.text(j, i, f'{monthly_matrix[i, j]:.1%}',
                                       ha="center", va="center", 
                                       color="black", fontsize=8)
            
            plt.tight_layout()
            
            # 转换为base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=self.dpi, bbox_inches='tight')
            buffer.seek(0)
            img_str = base64.b64encode(buffer.read()).decode()
            plt.close(fig)
            
            # 计算回测统计
            total_return_market = df['Cumulative_Market'].iloc[-1] - 1
            total_return_strategy = df['Cumulative_Strategy'].iloc[-1] - 1
            
            return {
                'symbol': symbol,
                'chart_type': 'backtest',
                'image_base64': img_str,
                'performance': {
                    'market_return': float(total_return_market),
                    'strategy_return': float(total_return_strategy),
                    'outperformance': float(total_return_strategy - total_return_market)
                },
                'data_points': len(df),
                'date_range': {
                    'start': df.index[0].strftime('%Y-%m-%d'),
                    'end': df.index[-1].strftime('%Y-%m-%d')
                }
            }
            
        except Exception as e:
            print(f"生成回测图表错误: {e}")
            return None

# 全局实例
chart_generator = TradingChartGenerator()

if __name__ == "__main__":
    # 测试图表生成
    print("Testing chart generation...")
    
    # 测试价格图表
    result = chart_generator.generate_price_chart('AAPL', period='1mo')
    if result:
        print(f"Price chart generated: {result['symbol']}, {result['data_points']} data points")
    
    # 测试策略图表
    result = chart_generator.generate_strategy_chart('SPY', fast_period=10, slow_period=30)
    if result:
        print(f"Strategy chart generated: {result['symbol']}, {result['signals']['total_signals']} signals")
    
    # 测试回测图表
    result = chart_generator.generate_backtest_chart('AAPL')
    if result:
        print(f"Backtest chart generated: {result['symbol']}, Strategy return: {result['performance']['strategy_return']:.2%}")