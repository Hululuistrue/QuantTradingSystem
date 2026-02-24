"""
策略模块 - 包含各种量化交易策略
"""

from .base_strategy import BaseStrategy
from .moving_average import MovingAverageCrossover
from .rsi_strategy import RSIStrategy
from .bollinger_bands_strategy import BollingerBandsStrategy
from .historical_simulation import HistoricalSimulationStrategy

__all__ = [
    'BaseStrategy',
    'MovingAverageCrossover',
    'RSIStrategy',
    'BollingerBandsStrategy',
    'HistoricalSimulationStrategy'
]