"""
布林带策略
价格突破上轨：卖出信号
价格突破下轨：买入信号
价格在中轨附近：持有
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import logging
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class BollingerBandsStrategy(BaseStrategy):
    """布林带策略"""
    
    def __init__(self, period: int = 20, std_dev: float = 2.0):
        """
        初始化布林带策略
        
        Args:
            period: 移动平均周期（默认20）
            std_dev: 标准差倍数（默认2.0）
        """
        super().__init__(name="Bollinger Bands Strategy")
        self.period = period
        self.std_dev = std_dev
        
        # 策略参数
        self.params = {
            "period": period,
            "std_dev": std_dev
        }
        
        logger.info(f"初始化布林带策略: period={period}, std_dev={std_dev}")
    
    def calculate_bollinger_bands(self, prices: pd.Series) -> pd.DataFrame:
        """
        计算布林带
        
        Args:
            prices: 价格序列（通常是收盘价）
        
        Returns:
            包含中轨、上轨、下轨的DataFrame
        """
        # 计算中轨（移动平均）
        middle_band = prices.rolling(window=self.period).mean()
        
        # 计算标准差
        std = prices.rolling(window=self.period).std()
        
        # 计算上轨和下轨
        upper_band = middle_band + (std * self.std_dev)
        lower_band = middle_band - (std * self.std_dev)
        
        # 计算带宽和百分比
        bandwidth = (upper_band - lower_band) / middle_band
        percent_b = (prices - lower_band) / (upper_band - lower_band)
        
        bands_df = pd.DataFrame({
            'middle_band': middle_band,
            'upper_band': upper_band,
            'lower_band': lower_band,
            'bandwidth': bandwidth,
            'percent_b': percent_b
        })
        
        return bands_df
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        Args:
            data: 包含价格数据的DataFrame，必须有'close'列
        
        Returns:
            包含信号的DataFrame
        """
        if 'close' not in data.columns:
            logger.error("数据必须包含'close'列")
            return pd.DataFrame()
        
        # 复制数据以避免修改原始数据
        signals_df = data.copy()
        
        # 计算布林带
        bands_df = self.calculate_bollinger_bands(signals_df['close'])
        signals_df = pd.concat([signals_df, bands_df], axis=1)
        
        # 初始化信号列
        signals_df['signal'] = 'hold'
        signals_df['signal_strength'] = 0.0
        
        # 生成信号
        for i in range(len(signals_df)):
            if pd.isna(signals_df['middle_band'].iloc[i]):
                continue
            
            price = signals_df['close'].iloc[i]
            upper = signals_df['upper_band'].iloc[i]
            lower = signals_df['lower_band'].iloc[i]
            middle = signals_df['middle_band'].iloc[i]
            percent_b = signals_df['percent_b'].iloc[i]
            
            # 检查是否突破布林带
            if price > upper:
                # 突破上轨，卖出信号
                signals_df.loc[signals_df.index[i], 'signal'] = 'sell'
                # 信号强度：突破越多，信号越强
                signal_strength = (price - upper) / (upper - middle) if (upper - middle) > 0 else 1.0
                signals_df.loc[signals_df.index[i], 'signal_strength'] = min(signal_strength, 1.0)
                
            elif price < lower:
                # 突破下轨，买入信号
                signals_df.loc[signals_df.index[i], 'signal'] = 'buy'
                # 信号强度：突破越多，信号越强
                signal_strength = (lower - price) / (middle - lower) if (middle - lower) > 0 else 1.0
                signals_df.loc[signals_df.index[i], 'signal_strength'] = min(signal_strength, 1.0)
            
            # 如果价格在中轨附近，考虑趋势
            elif 0.4 < percent_b < 0.6:
                # 价格在中轨附近，根据趋势判断
                if i > 0 and 'close' in signals_df.columns:
                    prev_price = signals_df['close'].iloc[i-1]
                    if price > prev_price and percent_b > 0.5:
                        # 向上突破中轨，轻微买入信号
                        signals_df.loc[signals_df.index[i], 'signal'] = 'weak_buy'
                        signals_df.loc[signals_df.index[i], 'signal_strength'] = 0.3
                    elif price < prev_price and percent_b < 0.5:
                        # 向下跌破中轨，轻微卖出信号
                        signals_df.loc[signals_df.index[i], 'signal'] = 'weak_sell'
                        signals_df.loc[signals_df.index[i], 'signal_strength'] = 0.3
        
        # 添加信号描述
        signals_df['signal_description'] = signals_df.apply(
            lambda row: self._get_signal_description(row), axis=1
        )
        
        logger.info(f"布林带策略生成信号完成: 买入={sum(signals_df['signal'] == 'buy')}, "
                   f"卖出={sum(signals_df['signal'] == 'sell')}, "
                   f"弱买入={sum(signals_df['signal'] == 'weak_buy')}, "
                   f"弱卖出={sum(signals_df['signal'] == 'weak_sell')}, "
                   f"持有={sum(signals_df['signal'] == 'hold')}")
        
        return signals_df
    
    def _get_signal_description(self, row: pd.Series) -> str:
        """获取信号描述"""
        if pd.isna(row.get('percent_b')):
            return "数据不足"
        
        price = row['close']
        upper = row['upper_band']
        lower = row['lower_band']
        middle = row['middle_band']
        percent_b = row['percent_b']
        
        if row['signal'] == 'buy':
            return f"价格({price:.2f}) < 下轨({lower:.2f}), %B={percent_b:.2f}"
        elif row['signal'] == 'sell':
            return f"价格({price:.2f}) > 上轨({upper:.2f}), %B={percent_b:.2f}"
        elif row['signal'] == 'weak_buy':
            return f"价格({price:.2f})在中轨({middle:.2f})附近向上, %B={percent_b:.2f}"
        elif row['signal'] == 'weak_sell':
            return f"价格({price:.2f})在中轨({middle:.2f})附近向下, %B={percent_b:.2f}"
        else:
            return f"价格({price:.2f})在布林带内, %B={percent_b:.2f}"
    
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
        if data.empty:
            return {"error": "数据为空"}
        
        # 生成信号
        signals_df = self.generate_signals(data)
        if signals_df.empty:
            return {"error": "生成信号失败"}
        
        # 初始化回测变量
        capital = initial_capital
        position = 0  # 持仓数量
        trades = []
        portfolio_values = []
        
        for i in range(len(signals_df)):
            current_price = signals_df['close'].iloc[i]
            signal = signals_df['signal'].iloc[i]
            signal_strength = signals_df['signal_strength'].iloc[i]
            date = signals_df.index[i] if hasattr(signals_df.index[i], 'strftime') else i
            
            # 记录当前投资组合价值
            portfolio_value = capital + position * current_price
            portfolio_values.append({
                'date': date,
                'portfolio_value': portfolio_value,
                'price': current_price,
                'position': position,
                'capital': capital,
                'signal': signal,
                'signal_strength': signal_strength
            })
            
            # 执行交易（考虑信号强度）
            if signal in ['buy', 'weak_buy'] and position == 0:
                # 买入
                # 根据信号强度调整仓位：强信号用20%资金，弱信号用10%资金
                position_ratio = 0.2 if signal == 'buy' else 0.1
                shares_to_buy = capital * position_ratio / current_price
                cost = shares_to_buy * current_price * (1 + commission)
                
                if cost <= capital:
                    position = shares_to_buy
                    capital -= cost
                    
                    trades.append({
                        'date': date,
                        'type': 'buy',
                        'price': current_price,
                        'shares': shares_to_buy,
                        'cost': cost,
                        'commission': cost * commission,
                        'signal_strength': signal_strength,
                        'signal_type': signal
                    })
                    
            elif signal in ['sell', 'weak_sell'] and position > 0:
                # 卖出
                revenue = position * current_price * (1 - commission)
                capital += revenue
                
                trades.append({
                    'date': date,
                    'type': 'sell',
                    'price': current_price,
                    'shares': position,
                    'revenue': revenue,
                    'commission': revenue * commission,
                    'signal_strength': signal_strength,
                    'signal_type': signal
                })
                
                position = 0
        
        # 计算最终投资组合价值
        final_price = signals_df['close'].iloc[-1]
        final_portfolio_value = capital + position * final_price
        
        # 计算绩效指标
        returns = pd.Series([p['portfolio_value'] for p in portfolio_values])
        returns_pct = returns.pct_change().dropna()
        
        if len(returns_pct) > 0:
            total_return = (final_portfolio_value - initial_capital) / initial_capital
            annualized_return = (1 + total_return) ** (252 / len(returns)) - 1 if len(returns) > 1 else 0
            
            # 计算夏普比率（假设无风险利率为0）
            sharpe_ratio = returns_pct.mean() / returns_pct.std() * np.sqrt(252) if returns_pct.std() > 0 else 0
            
            # 计算最大回撤
            cumulative_returns = (1 + returns_pct).cumprod()
            running_max = cumulative_returns.expanding().max()
            drawdown = (cumulative_returns - running_max) / running_max
            max_drawdown = drawdown.min()
            
            # 计算胜率（只考虑完整交易）
            if trades:
                buy_trades = [t for t in trades if t['type'] == 'buy']
                sell_trades = [t for t in trades if t['type'] == 'sell']
                
                if len(buy_trades) == len(sell_trades):
                    winning_trades = 0
                    for buy, sell in zip(buy_trades, sell_trades):
                        if sell['revenue'] > buy['cost']:
                            winning_trades += 1
                    win_rate = winning_trades / len(sell_trades) if sell_trades else 0
                else:
                    win_rate = 0
            else:
                win_rate = 0
        else:
            total_return = 0
            annualized_return = 0
            sharpe_ratio = 0
            max_drawdown = 0
            win_rate = 0
        
        # 按信号类型统计
        signal_stats = {
            'buy': sum(signals_df['signal'] == 'buy'),
            'sell': sum(signals_df['signal'] == 'sell'),
            'weak_buy': sum(signals_df['signal'] == 'weak_buy'),
            'weak_sell': sum(signals_df['signal'] == 'weak_sell'),
            'hold': sum(signals_df['signal'] == 'hold')
        }
        
        # 构建结果
        result = {
            'strategy_name': self.name,
            'initial_capital': initial_capital,
            'final_portfolio_value': final_portfolio_value,
            'total_return': total_return,
            'annualized_return': annualized_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_trades': len(trades),
            'signal_stats': signal_stats,
            'parameters': self.params,
            'trades': trades[:10],  # 只返回前10笔交易
            'portfolio_history': portfolio_values[-50:],  # 只返回最后50个点
            'bands_info': {
                'avg_upper_band': signals_df['upper_band'].mean(),
                'avg_lower_band': signals_df['lower_band'].mean(),
                'avg_bandwidth': signals_df['bandwidth'].mean(),
                'avg_percent_b': signals_df['percent_b'].mean()
            }
        }
        
        logger.info(f"布林带策略回测完成: 总收益={total_return:.2%}, 夏普比率={sharpe_ratio:.2f}, "
                   f"最大回撤={max_drawdown:.2%}, 胜率={win_rate:.2%}")
        
        return result
    
    def optimize_parameters(self, data: pd.DataFrame, 
                          param_grid: Dict[str, List] = None) -> Dict[str, Any]:
        """
        优化策略参数
        
        Args:
            data: 价格数据
            param_grid: 参数网格
        
        Returns:
            优化结果
        """
        if param_grid is None:
            param_grid = {
                'period': [10, 20, 30],
                'std_dev': [1.5, 2.0, 2.5]
            }
        
        best_params = None
        best_sharpe = -float('inf')
        results = []
        
        # 网格搜索
        from itertools import product
        
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        for values in product(*param_values):
            params = dict(zip(param_names, values))
            
            # 创建新策略实例
            strategy = BollingerBandsStrategy(**params)
            
            # 回测
            result = strategy.backtest(data)
            
            if 'sharpe_ratio' in result:
                sharpe = result['sharpe_ratio']
                results.append({
                    'params': params,
                    'sharpe_ratio': sharpe,
                    'total_return': result.get('total_return', 0),
                    'max_drawdown': result.get('max_drawdown', 0)
                })
                
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = params
        
        return {
            'best_params': best_params,
            'best_sharpe_ratio': best_sharpe,
            'all_results': results,
            'param_grid': param_grid
        }