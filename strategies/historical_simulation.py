"""
历史数据模拟交易策略
基于30天历史数据，对比30天整体均线和最后10天均线
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
import logging
from datetime import datetime, timedelta
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class HistoricalSimulationStrategy(BaseStrategy):
    """历史数据模拟交易策略
    
    基于30天历史数据，对比30天整体均线和最后10天均线
    给出买入/卖出判断，并用后续数据验证策略准确性
    """
    
    def __init__(
        self,
        name: str = "历史数据模拟交易策略",
        symbol: str = "SPY",
        parameters: Dict[str, Any] = None
    ):
        """
        初始化历史数据模拟交易策略
        
        Args:
            name: 策略名称
            symbol: 股票代码
            parameters: 策略参数，包含:
                - historical_days: 历史数据天数 (默认: 30)
                - recent_days: 最近天数 (默认: 10)
                - validation_days: 验证天数 (默认: 10)
                - ma_type: 移动平均类型 (默认: 'sma')
        """
        if parameters is None:
            parameters = {
                'historical_days': 30,
                'recent_days': 10,
                'validation_days': 10,
                'ma_type': 'sma'  # 'sma' or 'ema'
            }
        
        super().__init__(name)
        self.symbol = symbol
        self.parameters = parameters
        self.params = parameters
        
        # 存储验证结果
        self.validation_results = None
        self.trade_signal = None
        self.verification_data = None
    
    def get_required_parameters(self) -> List[str]:
        """获取必需参数列表"""
        return ['historical_days', 'recent_days', 'validation_days']
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算技术指标
        
        Args:
            data: 股票数据
        
        Returns:
            包含技术指标的数据
        """
        data = data.copy()
        
        historical_days = self.parameters['historical_days']
        recent_days = self.parameters['recent_days']
        ma_type = self.parameters.get('ma_type', 'sma')
        
        # 确保数据足够
        if len(data) < historical_days:
            logger.warning(f"数据不足，需要{historical_days}天，实际只有{len(data)}天")
            return data
        
        # 计算移动平均线
        if ma_type == 'ema':
            data['ma_30'] = data['close'].ewm(span=historical_days).mean()
            data['ma_10'] = data['close'].tail(recent_days).ewm(span=recent_days).mean()
        else:  # sma
            data['ma_30'] = data['close'].rolling(window=historical_days).mean()
            # 计算最后10天的移动平均线
            recent_data = data['close'].tail(recent_days)
            data['ma_10_recent'] = recent_data.rolling(window=recent_days).mean()
            # 将最后10天的移动平均值扩展到整个数据集
            data['ma_10'] = np.nan
            if len(recent_data) >= recent_days:
                ma_10_value = recent_data.rolling(window=recent_days).mean().iloc[-1]
                data.loc[data.index[-recent_days:], 'ma_10'] = ma_10_value
        
        # 计算均线差值
        data['ma_diff'] = data['ma_10'] - data['ma_30']
        
        # 计算相对位置
        data['ma_ratio'] = data['ma_10'] / data['ma_30']
        
        return data

    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        覆盖基类数据准备逻辑，仅要求date/close即可。
        """
        data = data.copy()
        
        if 'date' not in data.columns:
            if data.index.name:
                data = data.reset_index()
            else:
                data = data.reset_index().rename(columns={'index': 'date'})
        
        if 'close' not in data.columns:
            raise ValueError("数据缺少必需列: close")
        
        data = data.sort_values('date').reset_index(drop=True)
        return data
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        Args:
            data: 包含技术指标的数据
        
        Returns:
            包含信号的数据
        """
        data = data.copy()
        
        historical_days = self.parameters['historical_days']
        recent_days = self.parameters['recent_days']
        
        # 确保有足够的数据
        if len(data) < historical_days:
            logger.warning("数据不足，无法生成信号")
            data['signal'] = 'hold'
            data['signal_description'] = '数据不足'
            return data
        
        # 获取历史数据（前30天）
        historical_data = data.iloc[-historical_days:]
        
        # 计算30天整体均线
        ma_30_overall = historical_data['close'].mean()
        
        # 计算最后10天均线
        recent_data = historical_data.tail(recent_days)
        ma_10_recent = recent_data['close'].mean()
        
        # 生成交易信号
        signal = 'hold'
        signal_description = ''
        
        # 判断逻辑：最后10天均线 vs 30天整体均线
        if ma_10_recent > ma_30_overall:
            signal = 'buy'
            signal_description = f"最后{recent_days}天均线({ma_10_recent:.2f}) > 30天整体均线({ma_30_overall:.2f})"
        elif ma_10_recent < ma_30_overall:
            signal = 'sell'
            signal_description = f"最后{recent_days}天均线({ma_10_recent:.2f}) < 30天整体均线({ma_30_overall:.2f})"
        else:
            signal = 'hold'
            signal_description = f"最后{recent_days}天均线({ma_10_recent:.2f}) = 30天整体均线({ma_30_overall:.2f})"
        
        # 计算信号强度
        signal_strength = (ma_10_recent - ma_30_overall) / ma_30_overall * 100
        
        # 只在最后一天添加信号
        data['signal'] = 'hold'
        data['signal_description'] = ''
        data['signal_strength'] = 0.0
        
        if not data.empty:
            last_idx = data.index[-1]
            data.loc[last_idx, 'signal'] = signal
            data.loc[last_idx, 'signal_description'] = signal_description
            data.loc[last_idx, 'signal_strength'] = float(signal_strength)
            
            # 存储交易信号
            self.trade_signal = {
                'signal': signal,
                'signal_description': signal_description,
                'signal_strength': signal_strength,
                'ma_30_overall': ma_30_overall,
                'ma_10_recent': ma_10_recent,
                'historical_days': historical_days,
                'recent_days': recent_days,
                'decision_date': data.loc[last_idx, 'date'] if 'date' in data.columns else None
            }
        
        return data
    
    def validate_strategy(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        验证策略准确性
        
        Args:
            data: 完整数据（包含验证期）
        
        Returns:
            验证结果
        """
        historical_days = self.parameters['historical_days']
        validation_days = self.parameters['validation_days']
        
        # 确保数据足够
        total_days_needed = historical_days + validation_days
        if len(data) < total_days_needed:
            logger.warning(f"数据不足，需要{total_days_needed}天，实际只有{len(data)}天")
            return {
                'status': 'error',
                'message': f'数据不足，需要{total_days_needed}天，实际只有{len(data)}天'
            }
        
        # 分割数据
        historical_data = data.iloc[:historical_days]
        validation_data = data.iloc[historical_days:historical_days + validation_days]
        
        # 运行策略获取交易信号
        self.run(historical_data)
        
        if self.trade_signal is None:
            return {
                'status': 'error',
                'message': '无法生成交易信号'
            }
        
        # 验证信号准确性
        signal = self.trade_signal['signal']
        validation_results = self._verify_signal(signal, validation_data)
        
        # 存储验证数据
        self.verification_data = validation_data
        self.validation_results = validation_results
        
        return validation_results
    
    def _verify_signal(self, signal: str, validation_data: pd.DataFrame) -> Dict[str, Any]:
        """
        验证交易信号的准确性
        
        Args:
            signal: 交易信号 ('buy', 'sell', 'hold')
            validation_data: 验证期数据
        
        Returns:
            验证结果
        """
        if validation_data.empty:
            return {
                'status': 'error',
                'message': '验证数据为空'
            }
        
        # 计算验证期价格变化
        start_price = validation_data['close'].iloc[0]
        end_price = validation_data['close'].iloc[-1]
        price_change = end_price - start_price
        price_change_pct = (price_change / start_price) * 100
        
        # 判断信号是否正确
        is_correct = False
        correctness_reason = ""
        
        if signal == 'buy':
            # 买入信号：预期价格上涨
            if price_change > 0:
                is_correct = True
                correctness_reason = f"买入信号正确：价格从{start_price:.2f}上涨到{end_price:.2f} (+{price_change_pct:.2f}%)"
            else:
                correctness_reason = f"买入信号错误：价格从{start_price:.2f}下跌到{end_price:.2f} ({price_change_pct:.2f}%)"
        
        elif signal == 'sell':
            # 卖出信号：预期价格下跌
            if price_change < 0:
                is_correct = True
                correctness_reason = f"卖出信号正确：价格从{start_price:.2f}下跌到{end_price:.2f} ({price_change_pct:.2f}%)"
            else:
                correctness_reason = f"卖出信号错误：价格从{start_price:.2f}上涨到{end_price:.2f} (+{price_change_pct:.2f}%)"
        
        else:  # hold
            # 持有信号：预期价格波动不大
            price_volatility = validation_data['close'].std() / validation_data['close'].mean() * 100
            if abs(price_change_pct) < 5:  # 小于5%的波动
                is_correct = True
                correctness_reason = f"持有信号正确：价格波动较小 ({price_change_pct:.2f}%)，波动率{price_volatility:.2f}%"
            else:
                correctness_reason = f"持有信号错误：价格波动较大 ({price_change_pct:.2f}%)，波动率{price_volatility:.2f}%"
        
        # 计算验证期详细统计
        validation_stats = {
            'start_date': validation_data['date'].iloc[0] if 'date' in validation_data.columns else None,
            'end_date': validation_data['date'].iloc[-1] if 'date' in validation_data.columns else None,
            'start_price': float(start_price),
            'end_price': float(end_price),
            'price_change': float(price_change),
            'price_change_pct': float(price_change_pct),
            'max_price': float(validation_data['close'].max()),
            'min_price': float(validation_data['close'].min()),
            'avg_price': float(validation_data['close'].mean()),
            'volatility_pct': float(validation_data['close'].std() / validation_data['close'].mean() * 100),
            'validation_days': len(validation_data)
        }
        
        return {
            'status': 'success',
            'signal': signal,
            'is_correct': is_correct,
            'correctness_reason': correctness_reason,
            'validation_stats': validation_stats,
            'trade_signal': self.trade_signal
        }
    
    def get_validation_report(self) -> Dict[str, Any]:
        """
        获取完整的验证报告
        
        Returns:
            验证报告
        """
        if self.validation_results is None:
            return {
                'status': 'error',
                'message': '尚未进行验证'
            }
        
        report = self.validation_results.copy()
        
        # 添加策略参数
        report['strategy_parameters'] = self.parameters
        
        # 添加性能指标
        if self.verification_data is not None and not self.verification_data.empty:
            # 计算潜在收益/损失
            signal = report['signal']
            price_change_pct = report['validation_stats']['price_change_pct']
            
            if signal == 'buy':
                potential_return = price_change_pct
                potential_return_type = '收益' if price_change_pct > 0 else '损失'
            elif signal == 'sell':
                potential_return = -price_change_pct  # 卖出信号正确时，价格下跌是收益
                potential_return_type = '收益' if price_change_pct < 0 else '损失'
            else:
                potential_return = 0
                potential_return_type = '中性'
            
            report['performance'] = {
                'potential_return_pct': float(potential_return),
                'potential_return_type': potential_return_type,
                'signal_accuracy': '正确' if report['is_correct'] else '错误',
                'confidence_score': min(abs(self.trade_signal['signal_strength']) / 10, 100) if self.trade_signal else 0
            }
        
        return report
    
    def run_simulation(
        self,
        data: pd.DataFrame,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """
        运行完整的模拟交易
        
        Args:
            data: 股票数据
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
        
        Returns:
            模拟交易结果
        """
        # 过滤数据日期范围
        if start_date or end_date:
            if 'date' in data.columns:
                if start_date:
                    data = data[data['date'] >= start_date]
                if end_date:
                    data = data[data['date'] <= end_date]
        
        # 验证策略
        validation_result = self.validate_strategy(data)
        
        if validation_result['status'] != 'success':
            return validation_result
        
        # 获取验证报告
        report = self.get_validation_report()
        
        # 添加模拟交易总结
        report['simulation_summary'] = {
            'symbol': self.symbol,
            'strategy_name': self.name,
            'total_data_days': len(data),
            'historical_period': self.parameters['historical_days'],
            'validation_period': self.parameters['validation_days'],
            'simulation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return report

    def backtest(self, data: pd.DataFrame, initial_capital: float = 100000.0,
                commission: float = 0.001) -> Dict[str, Any]:
        """
        回测策略（历史模拟的简化回测，复用模拟结果）
        
        Args:
            data: 价格数据
            initial_capital: 初始资金（未使用）
            commission: 交易佣金率（未使用）
        
        Returns:
            模拟结果字典
        """
        report = self.run_simulation(data)
        if report.get('status') != 'success':
            return {"error": report.get('message', '模拟失败')}
        return report
