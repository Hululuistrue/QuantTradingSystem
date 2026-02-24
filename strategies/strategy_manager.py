"""
策略管理器 - 统一管理所有交易策略
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

# 导入所有策略
from .moving_average import MovingAverageCrossover
from .rsi_strategy import RSIStrategy
from .macd_strategy import MACDStrategy
from .bollinger_bands_strategy import BollingerBandsStrategy
from .historical_simulation import HistoricalSimulationStrategy

logger = logging.getLogger(__name__)


class StrategyManager:
    """策略管理器"""
    
    def __init__(self):
        """初始化策略管理器"""
        self.strategies = {
            "moving_average": {
                "name": "双均线交叉策略",
                "class": MovingAverageCrossover,
                "description": "基于快速均线和慢速均线的交叉信号",
                "default_params": {"fast_period": 10, "slow_period": 30}
            },
            "rsi": {
                "name": "RSI策略",
                "class": RSIStrategy,
                "description": "基于相对强弱指数的超买超卖信号",
                "default_params": {"period": 14, "oversold": 30, "overbought": 70}
            },
            "macd": {
                "name": "MACD策略",
                "class": MACDStrategy,
                "description": "基于移动平均收敛发散的趋势信号",
                "default_params": {"fast_period": 12, "slow_period": 26, "signal_period": 9}
            },
            "bollinger_bands": {
                "name": "布林带策略",
                "class": BollingerBandsStrategy,
                "description": "基于布林带的突破和回归信号",
                "default_params": {"period": 20, "std_dev": 2.0}
            },
            "historical_simulation": {
                "name": "历史数据模拟策略",
                "class": HistoricalSimulationStrategy,
                "description": "基于历史数据的模拟交易和验证",
                "default_params": {"historical_days": 30, "recent_days": 10, "validation_days": 10}
            }
        }
        
        logger.info("策略管理器初始化完成")
    
    def get_available_strategies(self) -> List[Dict[str, Any]]:
        """获取所有可用策略"""
        strategies_list = []
        
        for strategy_id, strategy_info in self.strategies.items():
            strategies_list.append({
                "id": strategy_id,
                "name": strategy_info["name"],
                "description": strategy_info["description"],
                "default_params": strategy_info["default_params"]
            })
        
        return strategies_list
    
    def create_strategy(self, strategy_id: str, **params) -> Any:
        """
        创建策略实例
        
        Args:
            strategy_id: 策略ID
            **params: 策略参数
        
        Returns:
            策略实例
        """
        if strategy_id not in self.strategies:
            raise ValueError(f"未知的策略ID: {strategy_id}")
        
        strategy_info = self.strategies[strategy_id]
        strategy_class = strategy_info["class"]
        
        # 合并默认参数和用户参数
        default_params = strategy_info["default_params"].copy()
        default_params.update(params)
        
        # 创建策略实例 - 根据策略类调整参数传递方式
        try:
            # 尝试直接传递参数
            strategy = strategy_class(**default_params)
        except TypeError as e:
            # 如果失败，尝试使用parameters参数
            if "parameters" in strategy_class.__init__.__code__.co_varnames:
                strategy = strategy_class(parameters=default_params)
            else:
                # 如果还是失败，尝试使用其他方式
                try:
                    strategy = strategy_class(name=strategy_info["name"], parameters=default_params)
                except TypeError:
                    # 最后尝试使用默认参数
                    strategy = strategy_class()
                    # 手动设置参数
                    for key, value in default_params.items():
                        if hasattr(strategy, key):
                            setattr(strategy, key, value)
        
        logger.info(f"创建策略实例: {strategy_id} with params: {default_params}")
        return strategy
    
    def run_strategy(self, strategy_id: str, data: pd.DataFrame, **params) -> Dict[str, Any]:
        """
        运行策略
        
        Args:
            strategy_id: 策略ID
            data: 价格数据
            **params: 策略参数
        
        Returns:
            策略结果
        """
        try:
            # 创建策略实例
            strategy = self.create_strategy(strategy_id, **params)

            # 计算技术指标（如果策略有该方法）
            if hasattr(strategy, 'calculate_indicators'):
                data = strategy.calculate_indicators(data)

            # 生成信号
            signals_df = strategy.generate_signals(data)
            
            if signals_df.empty:
                return {"error": "生成信号失败"}
            
            # 提取信号信息
            latest_signal = None
            if len(signals_df) > 0:
                latest_row = signals_df.iloc[-1]
                latest_signal = {
                    "date": signals_df.index[-1].isoformat() if hasattr(signals_df.index[-1], 'isoformat') else str(signals_df.index[-1]),
                    "signal": latest_row['signal'],
                    "signal_strength": float(latest_row.get('signal_strength', 0.0)),
                    "signal_description": latest_row.get('signal_description', '')
                }
            
            # 统计信号
            buy_signals = sum(signals_df['signal'] == 'buy')
            sell_signals = sum(signals_df['signal'] == 'sell')
            hold_signals = sum(signals_df['signal'] == 'hold')
            
            # 准备结果
            result = {
                "strategy_id": strategy_id,
                "strategy_name": self.strategies[strategy_id]["name"],
                "parameters": params,
                "signals_summary": {
                    "total": len(signals_df),
                    "buy": buy_signals,
                    "sell": sell_signals,
                    "hold": hold_signals
                },
                "latest_signal": latest_signal,
                "recent_signals": []
            }
            
            # 添加最近10个信号
            signal_indices = signals_df[signals_df['signal'] != 'hold'].index
            if len(signal_indices) > 0:
                recent_indices = signal_indices[-10:] if len(signal_indices) > 10 else signal_indices
                for idx in recent_indices:
                    row = signals_df.loc[idx]
                    result["recent_signals"].append({
                        "date": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
                        "signal": row['signal'],
                        "signal_strength": float(row.get('signal_strength', 0.0)),
                        "signal_description": row.get('signal_description', '')
                    })
            
            logger.info(f"策略运行完成: {strategy_id}, 买入信号={buy_signals}, 卖出信号={sell_signals}")
            return result
            
        except Exception as e:
            logger.error(f"运行策略失败: {strategy_id}, 错误: {str(e)}")
            return {"error": f"运行策略失败: {str(e)}"}
    
    def backtest_strategy(self, strategy_id: str, data: pd.DataFrame, 
                         initial_capital: float = 100000.0, commission: float = 0.001, **params) -> Dict[str, Any]:
        """
        回测策略
        
        Args:
            strategy_id: 策略ID
            data: 价格数据
            initial_capital: 初始资金
            commission: 交易佣金率
            **params: 策略参数
        
        Returns:
            回测结果
        """
        try:
            # 创建策略实例
            strategy = self.create_strategy(strategy_id, **params)
            
            # 运行回测
            backtest_result = strategy.backtest(data, initial_capital, commission)
            
            # 添加策略信息
            backtest_result["strategy_id"] = strategy_id
            backtest_result["strategy_name"] = self.strategies[strategy_id]["name"]
            
            logger.info(f"策略回测完成: {strategy_id}, 总收益={backtest_result.get('total_return', 0):.2%}")
            return backtest_result
            
        except Exception as e:
            logger.error(f"策略回测失败: {strategy_id}, 错误: {str(e)}")
            return {"error": f"策略回测失败: {str(e)}"}
    
    def compare_strategies(self, data: pd.DataFrame, initial_capital: float = 100000.0, 
                          commission: float = 0.001) -> Dict[str, Any]:
        """
        比较所有策略
        
        Args:
            data: 价格数据
            initial_capital: 初始资金
            commission: 交易佣金率
        
        Returns:
            策略比较结果
        """
        comparison_results = []
        
        for strategy_id in self.strategies.keys():
            try:
                # 跳过历史模拟策略（需要特殊参数）
                if strategy_id == "historical_simulation":
                    continue
                
                # 使用默认参数回测
                strategy_info = self.strategies[strategy_id]
                strategy = self.create_strategy(strategy_id)
                
                backtest_result = strategy.backtest(data, initial_capital, commission)
                
                if "error" not in backtest_result:
                    comparison_results.append({
                        "strategy_id": strategy_id,
                        "strategy_name": strategy_info["name"],
                        "total_return": backtest_result.get("total_return", 0),
                        "annualized_return": backtest_result.get("annualized_return", 0),
                        "sharpe_ratio": backtest_result.get("sharpe_ratio", 0),
                        "max_drawdown": backtest_result.get("max_drawdown", 0),
                        "win_rate": backtest_result.get("win_rate", 0),
                        "total_trades": backtest_result.get("total_trades", 0)
                    })
                    
            except Exception as e:
                logger.warning(f"策略比较时跳过 {strategy_id}: {str(e)}")
                continue
        
        # 按夏普比率排序
        comparison_results.sort(key=lambda x: x.get("sharpe_ratio", 0), reverse=True)
        
        return {
            "comparison_date": datetime.now().isoformat(),
            "total_strategies": len(comparison_results),
            "strategies": comparison_results,
            "best_strategy": comparison_results[0] if comparison_results else None
        }


# 创建全局策略管理器实例
strategy_manager = StrategyManager()