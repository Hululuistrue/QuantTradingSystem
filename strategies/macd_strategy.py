"""
MACD（移动平均收敛发散）策略
MACD > 信号线：买入信号
MACD < 信号线：卖出信号
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import logging
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class MACDStrategy(BaseStrategy):
    """MACD策略"""
    
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        """
        初始化MACD策略
        
        Args:
            fast_period: 快速EMA周期（默认12）
            slow_period: 慢速EMA周期（默认26）
            signal_period: 信号线周期（默认9）
        """
        super().__init__(name="MACD Strategy")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        
        # 策略参数
        self.params = {
            "fast_period": fast_period,
            "slow_period": slow_period,
            "signal_period": signal_period
        }
        
        logger.info(f"初始化MACD策略: fast={fast_period}, slow={slow_period}, signal={signal_period}")
    
    def calculate_macd(self, prices: pd.Series) -> pd.DataFrame:
        """
        计算MACD指标
        
        Args:
            prices: 价格序列（通常是收盘价）
        
        Returns:
            包含MACD、信号线、柱状图的DataFrame
        """
        # 计算快速EMA和慢速EMA
        fast_ema = prices.ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = prices.ewm(span=self.slow_period, adjust=False).mean()
        
        # 计算MACD线
        macd_line = fast_ema - slow_ema
        
        # 计算信号线
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        
        # 计算柱状图
        histogram = macd_line - signal_line
        
        macd_df = pd.DataFrame({
            'macd_line': macd_line,
            'signal_line': signal_line,
            'histogram': histogram
        })
        
        return macd_df
    
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
        
        # 计算MACD
        macd_df = self.calculate_macd(signals_df['close'])
        signals_df = pd.concat([signals_df, macd_df], axis=1)
        
        # 初始化信号列
        signals_df['signal'] = 'hold'
        signals_df['signal_strength'] = 0.0
        
        # 生成信号
        for i in range(1, len(signals_df)):
            if pd.isna(signals_df['macd_line'].iloc[i]) or pd.isna(signals_df['signal_line'].iloc[i]):
                continue
            
            macd = signals_df['macd_line'].iloc[i]
            signal = signals_df['signal_line'].iloc[i]
            histogram = signals_df['histogram'].iloc[i]
            
            prev_macd = signals_df['macd_line'].iloc[i-1]
            prev_signal = signals_df['signal_line'].iloc[i-1]
            
            # 检查MACD与信号线的交叉
            if macd > signal and prev_macd <= prev_signal:
                # MACD上穿信号线，买入信号
                signals_df.loc[signals_df.index[i], 'signal'] = 'buy'
                # 信号强度：柱状图正值越大，信号越强
                signal_strength = min(abs(histogram) / abs(macd), 1.0) if macd != 0 else 0.5
                signals_df.loc[signals_df.index[i], 'signal_strength'] = signal_strength
                
            elif macd < signal and prev_macd >= prev_signal:
                # MACD下穿信号线，卖出信号
                signals_df.loc[signals_df.index[i], 'signal'] = 'sell'
                # 信号强度：柱状图负值越大，信号越强
                signal_strength = min(abs(histogram) / abs(macd), 1.0) if macd != 0 else 0.5
                signals_df.loc[signals_df.index[i], 'signal_strength'] = signal_strength
            
            # 检查零轴交叉
            elif macd > 0 and prev_macd <= 0:
                # MACD上穿零轴，买入信号
                signals_df.loc[signals_df.index[i], 'signal'] = 'buy'
                signals_df.loc[signals_df.index[i], 'signal_strength'] = 0.7
                
            elif macd < 0 and prev_macd >= 0:
                # MACD下穿零轴，卖出信号
                signals_df.loc[signals_df.index[i], 'signal'] = 'sell'
                signals_df.loc[signals_df.index[i], 'signal_strength'] = 0.7
        
        # 添加信号描述
        signals_df['signal_description'] = signals_df.apply(
            lambda row: self._get_signal_description(row), axis=1
        )
        
        logger.info(f"MACD策略生成信号完成: 买入={sum(signals_df['signal'] == 'buy')}, "
                   f"卖出={sum(signals_df['signal'] == 'sell')}, "
                   f"持有={sum(signals_df['signal'] == 'hold')}")
        
        return signals_df
    
    def _get_signal_description(self, row: pd.Series) -> str:
        """获取信号描述"""
        if pd.isna(row.get('macd_line')) or pd.isna(row.get('signal_line')):
            return "数据不足"
        
        macd = row['macd_line']
        signal = row['signal_line']
        histogram = row['histogram']
        
        if row['signal'] == 'buy':
            if macd > signal:
                return f"MACD({macd:.4f}) > 信号线({signal:.4f}), 柱状图={histogram:.4f}"
            else:
                return f"MACD({macd:.4f}) > 0, 柱状图={histogram:.4f}"
        elif row['signal'] == 'sell':
            if macd < signal:
                return f"MACD({macd:.4f}) < 信号线({signal:.4f}), 柱状图={histogram:.4f}"
            else:
                return f"MACD({macd:.4f}) < 0, 柱状图={histogram:.4f}"
        else:
            return f"MACD({macd:.4f}), 信号线({signal:.4f}), 柱状图={histogram:.4f}"
    
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
            if signal == 'buy' and position == 0:
                # 买入
                # 根据信号强度调整仓位：强信号用20%资金，中等信号用15%资金，弱信号用10%资金
                if signal_strength > 0.8:
                    position_ratio = 0.2
                elif signal_strength > 0.5:
                    position_ratio = 0.15
                else:
                    position_ratio = 0.1
                    
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
                        'signal_strength': signal_strength
                    })
                    
            elif signal == 'sell' and position > 0:
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
                    'signal_strength': signal_strength
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
            
            # 计算胜率
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
            'buy_signals': sum(signals_df['signal'] == 'buy'),
            'sell_signals': sum(signals_df['signal'] == 'sell'),
            'parameters': self.params,
            'trades': trades[:10],  # 只返回前10笔交易
            'portfolio_history': portfolio_values[-50:],  # 只返回最后50个点
            'macd_stats': {
                'avg_macd': signals_df['macd_line'].mean(),
                'avg_signal': signals_df['signal_line'].mean(),
                'avg_histogram': signals_df['histogram'].mean(),
                'macd_positive_days': sum(signals_df['macd_line'] > 0),
                'macd_negative_days': sum(signals_df['macd_line'] < 0)
            }
        }
        
        logger.info(f"MACD策略回测完成: 总收益={total_return:.2%}, 夏普比率={sharpe_ratio:.2f}, "
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
                'fast_period': [8, 12, 16],
                'slow_period': [21, 26, 30],
                'signal_period': [7, 9, 11]
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
            strategy = MACDStrategy(**params)
            
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