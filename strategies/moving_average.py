"""
双均线交叉策略
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
import logging
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class MovingAverageCrossover(BaseStrategy):
    """双均线交叉策略"""
    
    def __init__(
        self,
        name: str = "双均线交叉策略",
        symbol: str = "SPY",
        parameters: Dict[str, Any] = None
    ):
        """
        初始化双均线交叉策略
        
        Args:
            name: 策略名称
            symbol: 股票代码
            parameters: 策略参数，包含:
                - fast_period: 快线周期 (默认: 10)
                - slow_period: 慢线周期 (默认: 30)
                - rsi_period: RSI周期 (默认: 14，用于过滤)
                - rsi_overbought: RSI超买阈值 (默认: 70)
                - rsi_oversold: RSI超卖阈值 (默认: 30)
        """
        super().__init__(name)
        
        self.symbol = symbol
        if parameters is None:
            self.parameters = {
                'fast_period': 10,
                'slow_period': 30,
                'rsi_period': 14,
                'rsi_overbought': 70,
                'rsi_oversold': 30
            }
        else:
            self.parameters = parameters
    
    def get_required_parameters(self) -> List[str]:
        """获取必需参数列表"""
        return ['fast_period', 'slow_period']
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算技术指标
        
        Args:
            data: 股票数据
        
        Returns:
            包含技术指标的数据
        """
        data = data.copy()
        
        # 计算移动平均线
        fast_period = self.parameters['fast_period']
        slow_period = self.parameters['slow_period']
        
        data['ma_fast'] = data['close'].rolling(window=fast_period).mean()
        data['ma_slow'] = data['close'].rolling(window=slow_period).mean()
        
        # 计算RSI（如果参数中包含）
        if 'rsi_period' in self.parameters:
            rsi_period = self.parameters['rsi_period']
            data['rsi'] = self._calculate_rsi(data['close'], rsi_period)
        
        # 计算移动平均线交叉
        data['ma_crossover'] = data['ma_fast'] - data['ma_slow']
        data['ma_crossover_signal'] = np.where(
            data['ma_crossover'] > 0, 1, -1
        )
        
        # 计算交叉点
        data['ma_crossover_point'] = data['ma_crossover_signal'].diff()
        
        return data
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        计算相对强弱指数(RSI)
        
        Args:
            prices: 价格序列
            period: RSI周期
        
        Returns:
            RSI序列
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        Args:
            data: 包含技术指标的数据
        
        Returns:
            包含信号的数据
        """
        data = data.copy()
        
        # 初始化信号列为'hold'
        data['signal'] = 'hold'
        
        # 确保有足够的数据
        if len(data) < max(self.parameters['fast_period'], self.parameters['slow_period']):
            logger.warning("数据不足，无法生成信号")
            return data
        
        # 生成买入信号（快线上穿慢线）
        buy_condition = (
            (data['ma_crossover_point'] > 0) &  # 快线上穿慢线
            (data['ma_fast'] > data['ma_slow'])  # 快线在慢线上方
        )
        
        # 生成卖出信号（快线下穿慢线）
        sell_condition = (
            (data['ma_crossover_point'] < 0) &  # 快线下穿慢线
            (data['ma_fast'] < data['ma_slow'])  # 快线在慢线下方
        )
        
        # 应用RSI过滤（如果可用）
        if 'rsi' in data.columns and 'rsi_oversold' in self.parameters:
            rsi_oversold = self.parameters['rsi_oversold']
            rsi_overbought = self.parameters['rsi_overbought']
            
            # 买入信号增加RSI超卖条件
            buy_condition = buy_condition & (data['rsi'] < rsi_oversold)
            
            # 卖出信号增加RSI超买条件
            sell_condition = sell_condition & (data['rsi'] > rsi_overbought)
        
        # 应用信号
        data.loc[buy_condition, 'signal'] = 'buy'
        data.loc[sell_condition, 'signal'] = 'sell'
        
        # 记录信号强度（使用float，避免pandas对int列赋float时报错）
        data['signal_strength'] = 0.0
        data.loc[data['signal'] == 'buy', 'signal_strength'] = data['ma_crossover'].astype(float)
        data.loc[data['signal'] == 'sell', 'signal_strength'] = (-data['ma_crossover']).astype(float)
        
        # 添加信号描述
        data['signal_description'] = ''
        data.loc[data['signal'] == 'buy', 'signal_description'] = f"快线({self.parameters['fast_period']}日)上穿慢线({self.parameters['slow_period']}日)"
        data.loc[data['signal'] == 'sell', 'signal_description'] = f"快线({self.parameters['fast_period']}日)下穿慢线({self.parameters['slow_period']}日)"
        
        # 如果使用了RSI过滤，添加到描述中
        if 'rsi' in data.columns:
            rsi_desc = f"，RSI={data['rsi'].round(2)}"
            data.loc[data['signal'] == 'buy', 'signal_description'] += rsi_desc
            data.loc[data['signal'] == 'sell', 'signal_description'] += rsi_desc
        
        return data
    
    def get_strategy_metrics(self) -> Dict[str, Any]:
        """
        获取策略指标
        
        Returns:
            策略指标字典
        """
        if self.data is None or self.signals is None:
            return {}
        
        # 计算策略表现指标
        signals = self.signals.copy()
        
        if signals.empty:
            return {
                'total_signals': 0,
                'buy_signals': 0,
                'sell_signals': 0,
                'signal_frequency': 0
            }
        
        # 计算信号频率（信号数量/总天数）
        total_days = len(self.data)
        signal_frequency = len(signals) / total_days if total_days > 0 else 0
        
        # 计算平均持仓时间（粗略估计）
        if len(signals) >= 2:
            signals = signals.sort_values('date')
            time_diffs = signals['date'].diff().dt.days.dropna()
            avg_holding_days = time_diffs.mean() if len(time_diffs) > 0 else 0
        else:
            avg_holding_days = 0
        
        metrics = {
            'total_signals': len(signals),
            'buy_signals': len(signals[signals['signal'] == 'buy']),
            'sell_signals': len(signals[signals['signal'] == 'sell']),
            'signal_frequency': round(signal_frequency, 4),
            'avg_holding_days': round(avg_holding_days, 1) if avg_holding_days > 0 else 0,
            'parameters': self.parameters,
            'data_period': {
                'start_date': self.data['date'].min().strftime('%Y-%m-%d'),
                'end_date': self.data['date'].max().strftime('%Y-%m-%d'),
                'total_days': total_days
            }
        }
        
        return metrics
    
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
        
        # 准备数据并计算指标
        prepared_data = self.prepare_data(data)
        indicators_data = self.calculate_indicators(prepared_data)

        # 生成信号
        signals_df = self.generate_signals(indicators_data)
        if signals_df.empty:
            return {"error": "生成信号失败"}
        
        # 准备回测数据
        backtest_data = indicators_data.copy()
        if 'date' not in backtest_data.columns:
            if backtest_data.index.name:
                backtest_data = backtest_data.reset_index()
            else:
                backtest_data = backtest_data.reset_index().rename(columns={'index': 'date'})

        if 'date' not in signals_df.columns:
            if signals_df.index.name:
                signals_df = signals_df.reset_index()
            else:
                signals_df = signals_df.reset_index().rename(columns={'index': 'date'})
        
        # 合并信号
        backtest_data = pd.merge(backtest_data, signals_df[['date', 'signal']], 
                                on='date', how='left')
        backtest_data['signal'] = backtest_data['signal'].fillna('hold')
        
        # 初始化回测变量
        capital = initial_capital
        position = 0
        trades = []
        equity_curve = []
        
        # 执行回测
        for i, row in backtest_data.iterrows():
            date = row['date']
            price = row['close']
            signal = row['signal']
            
            # 记录当前权益
            current_equity = capital + position * price
            equity_curve.append({
                'date': date,
                'equity': current_equity,
                'price': price
            })
            
            # 执行交易信号
            if signal == 'buy' and position == 0:
                # 买入
                shares_to_buy = capital // (price * (1 + commission))
                if shares_to_buy > 0:
                    cost = shares_to_buy * price * (1 + commission)
                    capital -= cost
                    position = shares_to_buy
                    trades.append({
                        'date': date,
                        'type': 'buy',
                        'price': price,
                        'shares': shares_to_buy,
                        'cost': cost
                    })
            
            elif signal == 'sell' and position > 0:
                # 卖出
                revenue = position * price * (1 - commission)
                capital += revenue
                trades.append({
                    'date': date,
                    'type': 'sell',
                    'price': price,
                    'shares': position,
                    'revenue': revenue
                })
                position = 0
        
        # 计算最终权益（平仓）
        final_equity = capital + position * backtest_data.iloc[-1]['close']
        
        # 计算性能指标
        total_return_pct = ((final_equity - initial_capital) / initial_capital) * 100
        
        # 计算夏普比率（简化版）
        equity_df = pd.DataFrame(equity_curve)
        equity_df['returns'] = equity_df['equity'].pct_change()
        sharpe_ratio = 0
        if len(equity_df) > 1 and equity_df['returns'].std() > 0:
            sharpe_ratio = (equity_df['returns'].mean() / equity_df['returns'].std()) * np.sqrt(252)
        
        # 计算最大回撤
        equity_df['cummax'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['cummax']) / equity_df['cummax'] * 100
        max_drawdown = equity_df['drawdown'].min()
        
        # 计算交易统计
        total_trades = len(trades)
        winning_trades = 0
        losing_trades = 0
        total_profit = 0
        
        if total_trades >= 2:
            # 配对交易（买入-卖出）
            for i in range(0, total_trades - 1, 2):
                if i + 1 < total_trades:
                    buy_trade = trades[i]
                    sell_trade = trades[i + 1]
                    if buy_trade['type'] == 'buy' and sell_trade['type'] == 'sell':
                        profit = sell_trade['revenue'] - buy_trade['cost']
                        total_profit += profit
                        if profit > 0:
                            winning_trades += 1
                        else:
                            losing_trades += 1
        
        win_rate = (winning_trades / (winning_trades + losing_trades) * 100) if (winning_trades + losing_trades) > 0 else 0
        
        # 返回回测结果
        return {
            'initial_capital': initial_capital,
            'final_equity': final_equity,
            'total_return': round(total_return_pct, 2),
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'sharpe_ratio': round(sharpe_ratio, 3),
            'max_drawdown': round(max_drawdown, 2),
            'total_profit': round(total_profit, 2),
            'trades': trades[:10],  # 只返回前10笔交易
            'equity_curve': equity_curve[-20:],  # 只返回最后20个权益点
            'parameters': self.parameters,
            'strategy_name': self.name
        }
    
    def optimize_parameters(
        self,
        data: pd.DataFrame,
        fast_range: range = range(5, 21, 5),
        slow_range: range = range(20, 61, 10)
    ) -> Dict[str, Any]:
        """
        优化策略参数
        
        Args:
            data: 股票数据
            fast_range: 快线周期范围
            slow_range: 慢线周期范围
        
        Returns:
            最佳参数和结果
        """
        best_result = None
        best_params = None
        
        for fast in fast_range:
            for slow in slow_range:
                if fast >= slow:
                    continue  # 快线必须小于慢线
                
                try:
                    # 创建新策略实例
                    params = {
                        'fast_period': fast,
                        'slow_period': slow
                    }
                    
                    # 复制其他参数
                    for key in ['rsi_period', 'rsi_overbought', 'rsi_oversold']:
                        if key in self.parameters:
                            params[key] = self.parameters[key]
                    
                    strategy = MovingAverageCrossover(
                        name=f"优化策略_{fast}_{slow}",
                        symbol=self.symbol,
                        parameters=params
                    )
                    
                    # 运行策略
                    result_data = strategy.run(data)
                    signals = strategy.signals
                    
                    # 评估策略（简单的信号数量评估）
                    if signals is not None and not signals.empty:
                        signal_count = len(signals)
                        
                        if best_result is None or signal_count > best_result:
                            best_result = signal_count
                            best_params = params
                            
                except Exception as e:
                    logger.warning(f"参数优化失败 fast={fast}, slow={slow}: {e}")
                    continue
        
        return {
            'best_params': best_params,
            'best_result': best_result,
            'original_params': self.parameters
        }
