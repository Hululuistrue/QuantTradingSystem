"""
数据模块 - 负责股票数据的获取、清洗和存储
支持多数据源故障转移和数据质量检查
"""

from .collector import DataCollector
from .fetcher import YahooFinanceFetcher
from .alpha_vantage_fetcher import AlphaVantageFetcher
from .multi_source_fetcher import MultiSourceFetcher

__all__ = [
    'DataCollector', 
    'YahooFinanceFetcher',
    'AlphaVantageFetcher',
    'MultiSourceFetcher'
]