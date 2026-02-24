"""
数据收集器模块
"""

import logging
from typing import List, Dict, Any
import pandas as pd
from datetime import datetime, timedelta
from .fetcher import YahooFinanceFetcher

logger = logging.getLogger(__name__)


class DataCollector:
    """数据收集器"""
    
    def __init__(self, cache_dir: str = None):
        """
        初始化数据收集器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.fetcher = YahooFinanceFetcher(cache_dir)
        self.cache_dir = cache_dir
    
    def collect_stock_data(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
        period: str = "1y",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        收集股票数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 数据周期
            interval: 数据间隔
        
        Returns:
            股票数据DataFrame
        """
        try:
            data = self.fetcher.get_stock_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                period=period,
                interval=interval
            )
            
            if data.empty:
                logger.warning(f"未收集到股票 {symbol} 的数据")
                return pd.DataFrame()
            
            logger.info(f"成功收集 {symbol} 数据: {len(data)} 行")
            return data
            
        except Exception as e:
            logger.error(f"收集股票 {symbol} 数据失败: {e}")
            return pd.DataFrame()
    
    def collect_multiple_stocks(
        self,
        symbols: List[str],
        start_date: str = None,
        end_date: str = None,
        period: str = "1y",
        interval: str = "1d"
    ) -> Dict[str, pd.DataFrame]:
        """
        批量收集多个股票数据
        
        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            period: 数据周期
            interval: 数据间隔
        
        Returns:
            字典，键为股票代码，值为DataFrame
        """
        results = {}
        
        for symbol in symbols:
            try:
                data = self.collect_stock_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    period=period,
                    interval=interval
                )
                
                if not data.empty:
                    results[symbol] = data
                    logger.info(f"成功收集 {symbol} 数据")
                else:
                    logger.warning(f"股票 {symbol} 无数据")
                    
            except Exception as e:
                logger.error(f"收集股票 {symbol} 数据失败: {e}")
        
        return results
    
    def update_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        更新股票信息
        
        Args:
            symbol: 股票代码
        
        Returns:
            股票信息字典
        """
        try:
            info = self.fetcher.get_stock_info(symbol)
            
            if info:
                logger.info(f"成功更新 {symbol} 股票信息")
                return info
            else:
                logger.warning(f"未找到 {symbol} 的股票信息")
                return {}
                
        except Exception as e:
            logger.error(f"更新股票 {symbol} 信息失败: {e}")
            return {}
    
    def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        获取多个股票的当前价格
        
        Args:
            symbols: 股票代码列表
        
        Returns:
            字典，键为股票代码，值为当前价格
        """
        prices = {}
        
        for symbol in symbols:
            try:
                price = self.fetcher.get_current_price(symbol)
                prices[symbol] = price
                logger.info(f"获取 {symbol} 当前价格: {price:.2f}")
            except Exception as e:
                logger.error(f"获取 {symbol} 当前价格失败: {e}")
                prices[symbol] = 0.0
        
        return prices
    
    def collect_daily_data(self, symbols: List[str]):
        """
        每日数据收集任务
        
        Args:
            symbols: 需要每日收集的股票代码列表
        """
        logger.info(f"开始每日数据收集任务，股票数量: {len(symbols)}")
        
        # 收集昨日数据
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        results = self.collect_multiple_stocks(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            period="1d",
            interval="1d"
        )
        
        logger.info(f"每日数据收集完成，成功收集 {len(results)} 个股票的数据")
        return results