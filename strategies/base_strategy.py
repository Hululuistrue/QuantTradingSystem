"""
策略基类 - 所有量化策略的基类
"""

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name: str):
        """
        初始化策略
        
        Args:
            name: 策略名称
        """
        self.name = name
        self.data = None
        self.signals = None
        self.params = {}
        
        logger.info(f"初始化策略: {name}")
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        Args:
            data: 包含价格数据的DataFrame
        
        Returns:
            包含信号的DataFrame
        """
        pass
    
    @abstractmethod
    def backtest(self, data: pd.DataFrame, initial_capital: float = 100000.0, 
                commission: float = 0.001) -> Dict[str, Any]:
        """
        回测策略
        
        Args:
            data: 价格数据
            initial_capital: 初始资金
            commission: 交易佣金率
        
        Returns:
            回测结果字典
        """
        pass
    
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        准备数据，确保格式正确
        
        Args:
            data: 原始股票数据
        
        Returns:
            处理后的数据
        """
        if data.empty:
            return data
        
        # 复制数据以避免修改原始数据
        data = data.copy()
        
        # 确保数据按日期排序
        if 'date' in data.columns:
            data = data.sort_values('date')
            # 设置日期为索引（如果还没有）
            if data.index.name != 'date':
                data = data.set_index('date')
        else:
            # 如果没有date列，假设索引是日期
            data = data.sort_index()
        
        # 确保有必要的列
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in data.columns:
                logger.warning(f"数据缺少列: {col}")
        
        return data
    
    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        运行策略
        
        Args:
            data: 股票数据
        
        Returns:
            包含信号的数据
        """
        try:
            # 准备数据
            self.data = self.prepare_data(data)
            
            if self.data.empty:
                logger.warning("数据为空")
                return pd.DataFrame()
            
            # 生成交易信号
            self.signals = self.generate_signals(self.data)
            
            logger.info(f"策略 {self.name} 运行完成，生成 {len(self.signals)} 行信号数据")
            return self.signals
            
        except Exception as e:
            logger.error(f"策略 {self.name} 运行失败: {e}")
            return pd.DataFrame()
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取策略摘要
        
        Returns:
            策略摘要信息
        """
        if self.signals is None or self.signals.empty:
            return {
                'strategy_name': self.name,
                'total_signals': 0,
                'buy_signals': 0,
                'sell_signals': 0,
                'hold_signals': 0,
                'parameters': self.params
            }
        
        # 统计信号
        if 'signal' in self.signals.columns:
            buy_signals = sum(self.signals['signal'] == 'buy')
            sell_signals = sum(self.signals['signal'] == 'sell')
            hold_signals = sum(self.signals['signal'] == 'hold')
            total_signals = len(self.signals)
        else:
            buy_signals = sell_signals = hold_signals = total_signals = 0
        
        return {
            'strategy_name': self.name,
            'total_signals': total_signals,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'hold_signals': hold_signals,
            'parameters': self.params,
            'data_points': len(self.data) if self.data is not None else 0
        }
    
    def calculate_performance_metrics(self, returns: pd.Series) -> Dict[str, float]:
        """
        计算绩效指标
        
        Args:
            returns: 收益率序列
        
        Returns:
            绩效指标字典
        """
        if returns.empty or len(returns) < 2:
            return {}
        
        # 总收益率
        total_return = (1 + returns).prod() - 1
        
        # 年化收益率
        annualized_return = (1 + total_return) ** (252 / len(returns)) - 1
        
        # 年化波动率
        annualized_volatility = returns.std() * np.sqrt(252)
        
        # 夏普比率（假设无风险利率为0）
        sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        # 最大回撤
        cumulative_returns = (1 + returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # 索提诺比率（只考虑下行风险）
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() if len(downside_returns) > 0 else 0
        sortino_ratio = returns.mean() / downside_std * np.sqrt(252) if downside_std > 0 else 0
        
        # 卡尔马比率
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'annualized_volatility': annualized_volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio
        }
    
    def plot_signals(self, save_path: Optional[str] = None):
        """
        绘制信号图表
        
        Args:
            save_path: 保存路径，如果为None则显示图表
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            
            if self.signals is None or self.signals.empty:
                logger.warning("没有信号数据可绘制")
                return
            
            fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
            
            # 价格和信号图
            ax1 = axes[0]
            
            # 绘制价格
            if 'close' in self.signals.columns:
                ax1.plot(self.signals.index, self.signals['close'], 
                        label='Close Price', color='blue', linewidth=1.5, alpha=0.7)
            
            # 标记买入信号
            if 'signal' in self.signals.columns:
                buy_signals = self.signals[self.signals['signal'] == 'buy']
                if not buy_signals.empty and 'close' in buy_signals.columns:
                    ax1.scatter(buy_signals.index, buy_signals['close'], 
                               color='green', marker='^', s=100, label='Buy Signal', zorder=5)
                
                # 标记卖出信号
                sell_signals = self.signals[self.signals['signal'] == 'sell']
                if not sell_signals.empty and 'close' in sell_signals.columns:
                    ax1.scatter(sell_signals.index, sell_signals['close'], 
                               color='red', marker='v', s=100, label='Sell Signal', zorder=5)
            
            ax1.set_title(f'{self.name} - 交易信号')
            ax1.set_ylabel('价格')
            ax1.legend(loc='upper left')
            ax1.grid(True, alpha=0.3)
            
            # 成交量图
            ax2 = axes[1]
            if 'volume' in self.signals.columns:
                ax2.bar(self.signals.index, self.signals['volume'], 
                       color='gray', alpha=0.5, width=0.8)
                ax2.set_ylabel('成交量')
                ax2.grid(True, alpha=0.3)
            
            # 格式化x轴
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"图表已保存到: {save_path}")
            else:
                plt.show()
                
            plt.close()
            
        except ImportError:
            logger.warning("matplotlib未安装，无法绘制图表")
        except Exception as e:
            logger.error(f"绘制图表失败: {e}")
    
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        准备数据，确保格式正确
        
        Args:
            data: 原始股票数据
        
        Returns:
            处理后的数据
        """
        # 确保数据按日期排序
        data = data.copy()
        data = data.sort_values('date')
        
        # 确保有必要的列
        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in data.columns:
                raise ValueError(f"数据缺少必需列: {col}")
        
        # 重置索引
        data = data.reset_index(drop=True)
        
        return data
    
    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        运行策略
        
        Args:
            data: 股票数据
        
        Returns:
            包含信号和指标的数据
        """
        try:
            # 准备数据
            self.data = self.prepare_data(data)
            
            # 计算技术指标
            self.data = self.calculate_indicators(self.data)
            
            # 生成交易信号
            self.data = self.generate_signals(self.data)
            
            # 提取信号
            self.signals = self.extract_signals(self.data)
            
            logger.info(f"策略 {self.name} 运行完成，生成 {len(self.signals)} 个信号")
            return self.data
            
        except Exception as e:
            logger.error(f"策略 {self.name} 运行失败: {e}")
            raise
    
    def extract_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        从数据中提取信号
        
        Args:
            data: 包含信号的数据
        
        Returns:
            信号数据
        """
        if 'signal' not in data.columns:
            return pd.DataFrame()
        
        # 提取有信号的记录
        signals = data[data['signal'] != 'hold'].copy()
        
        if signals.empty:
            return pd.DataFrame()
        
        # 添加策略信息
        signals['strategy_name'] = self.name
        signals['symbol'] = self.symbol
        
        # 选择需要的列
        signal_columns = ['date', 'symbol', 'strategy_name', 'signal', 'close']
        available_columns = [col for col in signal_columns if col in signals.columns]
        
        return signals[available_columns]
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取策略摘要
        
        Returns:
            策略摘要信息
        """
        if self.signals is None or self.signals.empty:
            return {
                'strategy_name': self.name,
                'symbol': self.symbol,
                'total_signals': 0,
                'buy_signals': 0,
                'sell_signals': 0,
                'parameters': self.parameters
            }
        
        total_signals = len(self.signals)
        buy_signals = len(self.signals[self.signals['signal'] == 'buy'])
        sell_signals = len(self.signals[self.signals['signal'] == 'sell'])
        
        return {
            'strategy_name': self.name,
            'symbol': self.symbol,
            'total_signals': total_signals,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'parameters': self.parameters,
            'first_signal_date': self.signals['date'].min() if total_signals > 0 else None,
            'last_signal_date': self.signals['date'].max() if total_signals > 0 else None
        }
    
    def plot_signals(self, save_path: Optional[str] = None):
        """
        绘制信号图表
        
        Args:
            save_path: 保存路径，如果为None则显示图表
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            
            if self.data is None:
                logger.warning("没有数据可绘制")
                return
            
            fig, axes = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
            
            # 价格和信号图
            ax1 = axes[0]
            ax1.plot(self.data['date'], self.data['close'], label='Close Price', color='blue', linewidth=1)
            
            # 标记买入信号
            buy_signals = self.data[self.data['signal'] == 'buy']
            if not buy_signals.empty:
                ax1.scatter(buy_signals['date'], buy_signals['close'], 
                           color='green', marker='^', s=100, label='Buy Signal', zorder=5)
            
            # 标记卖出信号
            sell_signals = self.data[self.data['signal'] == 'sell']
            if not sell_signals.empty:
                ax1.scatter(sell_signals['date'], sell_signals['close'], 
                           color='red', marker='v', s=100, label='Sell Signal', zorder=5)
            
            ax1.set_title(f'{self.name} - {self.symbol}')
            ax1.set_ylabel('Price')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 成交量图
            ax2 = axes[1]
            ax2.bar(self.data['date'], self.data['volume'], color='gray', alpha=0.5)
            ax2.set_ylabel('Volume')
            ax2.grid(True, alpha=0.3)
            
            # 格式化x轴
            plt.gcf().autofmt_xdate()
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"图表已保存到: {save_path}")
            else:
                plt.show()
                
            plt.close()
            
        except ImportError:
            logger.warning("matplotlib未安装，无法绘制图表")
        except Exception as e:
            logger.error(f"绘制图表失败: {e}")