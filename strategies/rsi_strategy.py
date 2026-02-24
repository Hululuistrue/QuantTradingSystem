"""
RSI（相对强弱指数）策略
RSI > 70: 超买，卖出信号
RSI < 30: 超卖，买入信号
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import logging
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class RSIStrategy(BaseStrategy):
    """RSI策略"""
    
    def __init__(self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        """
        初始化RSI策略
        
        Args:
            period: RSI计算周期（默认14）
            oversold: 超卖阈值（默认30）
            overbought: 超买阈值（默认70）
        """
        super().__init__(name="RSI Strategy")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        
        # 策略参数
        self.params = {
            "period": period,
            "oversold": oversold,
            "overbought": overbought
        }
        
        logger.info(f"初始化RSI策略: period={period}, oversold={oversold}, overbought={overbought}")
    
    def calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """
        计算RSI指标
        
        Args:
            prices: 价格序列（通常是收盘价）
        
        Returns:
            RSI序列
        """
        # 计算价格变化
        delta = prices.diff()
        
        # 分离上涨和下跌
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        
        # 计算相对强度（RS）
        rs = gain / loss
        
        # 计算RSI
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
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
        
        # 计算RSI
        signals_df['rsi'] = self.calculate_rsi(signals_df['close'])
        
        # 初始化信号列
        signals_df['signal'] = 'hold'
        signals_df['signal_strength'] = 0.0
        
        # 生成信号
        for i in range(len(signals_df)):
            if pd.isna(signals_df['rsi'].iloc[i]):
                continue
            
            rsi_value = signals_df['rsi'].iloc[i]
            
            if rsi_value < self.oversold:
                # 超卖区域，买入信号
                signals_df.loc[signals_df.index[i], 'signal'] = 'buy'
                # 信号强度：RSI越低，买入信号越强
                signal_strength = (self.oversold - rsi_value) / self.oversold
                signals_df.loc[signals_df.index[i], 'signal_strength'] = min(signal_strength, 1.0)
                
            elif rsi_value > self.overbought:
                # 超买区域，卖出信号
                signals_df.loc[signals_df.index[i], 'signal'] = 'sell'
                # 信号强度：RSI越高，卖出信号越强
                signal_strength = (rsi_value - self.overbought) / (100 - self.overbought)
                signals_df.loc[signals_df.index[i], 'signal_strength'] = min(signal_strength, 1.0)
        
        # 添加信号描述
        signals_df['signal_description'] = signals_df.apply(
            lambda row: self._get_signal_description(row), axis=1
        )
        
        logger.info(f"RSI策略生成信号完成: 买入={sum(signals_df['signal'] == 'buy')}, "
                   f"卖出={sum(signals_df['signal'] == 'sell')}, "
                   f"持有={sum(signals_df['signal'] == 'hold')}")
        
        return signals_df
    
    def _get_signal_description(self, row: pd.Series) -> str:
        """获取信号描述"""
        if row['signal'] == 'buy':
            return f"RSI({row['rsi']:.1f}) < 超卖阈值({self.oversold})"
        elif row['signal'] == 'sell':
            return f"RSI({row['rsi']:.1f}) > 超买阈值({self.overbought})"
        else:
            return f"RSI({row['rsi']:.1f}) 在正常范围"
    
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
            date = signals_df.index[i] if hasattr(signals_df.index[i], 'strftime') else i
            
            # 记录当前投资组合价值
            portfolio_value = capital + position * current_price
            portfolio_values.append({
                'date': date,
                'portfolio_value': portfolio_value,
                'price': current_price,
                'position': position,
                'capital': capital
            })
            
            # 执行交易
            if signal == 'buy' and position == 0:
                # 买入
                shares_to_buy = capital * 0.1 / current_price  # 使用10%资金
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
                        'commission': cost * commission
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
                    'commission': revenue * commission
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
                winning_trades = [t for t in trades if t['type'] == 'sell' and 
                                 t.get('revenue', 0) > t.get('cost', 0)]
                win_rate = len(winning_trades) / len([t for t in trades if t['type'] == 'sell'])
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
            'signals_summary': {
                'buy': sum(signals_df['signal'] == 'buy'),
                'sell': sum(signals_df['signal'] == 'sell'),
                'hold': sum(signals_df['signal'] == 'hold')
            }
        }
        
        logger.info(f"RSI策略回测完成: 总收益={total_return:.2%}, 夏普比率={sharpe_ratio:.2f}, "
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
                'period': [7, 14, 21],
                'oversold': [20, 25, 30],
                'overbought': [70, 75, 80]
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
            strategy = RSIStrategy(**params)
            
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