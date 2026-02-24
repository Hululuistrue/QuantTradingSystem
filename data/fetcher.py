"""
雅虎财经数据获取器
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import List, Optional, Dict, Any
import time

logger = logging.getLogger(__name__)


class YahooFinanceFetcher:
    """雅虎财经数据获取器"""
    
    def __init__(self, cache_dir: str = None):
        """
        初始化数据获取器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = cache_dir
        if cache_dir:
            import os
            os.makedirs(cache_dir, exist_ok=True)
    
    def get_stock_data(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
        period: str = "1y",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        获取股票历史数据
        
        Args:
            symbol: 股票代码 (如: "SPY", "AAPL")
            start_date: 开始日期 (格式: "YYYY-MM-DD")
            end_date: 结束日期 (格式: "YYYY-MM-DD")
            period: 数据周期 (如: "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")
            interval: 数据间隔 (如: "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo")
        
        Returns:
            pandas DataFrame 包含股票数据
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # 获取数据
            if start_date and end_date:
                data = ticker.history(start=start_date, end=end_date, interval=interval)
            else:
                data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                logger.warning(f"未找到股票 {symbol} 的数据")
                return pd.DataFrame()
            
            # 重命名列以匹配数据库
            data = data.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume',
                'Dividends': 'dividend',
                'Stock Splits': 'split'
            })
            
            # 添加symbol列
            data['symbol'] = symbol
            
            # 重置索引，将日期作为列
            data = data.reset_index()
            data = data.rename(columns={'Date': 'date'})
            
            # 确保日期格式正确
            data['date'] = pd.to_datetime(data['date']).dt.date
            
            logger.info(f"成功获取 {symbol} 数据: {len(data)} 行")
            return data
            
        except Exception as e:
            logger.error(f"获取股票 {symbol} 数据失败: {e}")
            return pd.DataFrame()
    
    def get_multiple_stocks(
        self,
        symbols: List[str],
        start_date: str = None,
        end_date: str = None,
        period: str = "1y",
        interval: str = "1d"
    ) -> Dict[str, pd.DataFrame]:
        """
        批量获取多个股票数据
        
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
                data = self.get_stock_data(symbol, start_date, end_date, period, interval)
                if not data.empty:
                    results[symbol] = data
                else:
                    logger.warning(f"股票 {symbol} 无数据")
                
                # 避免请求过于频繁
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"获取股票 {symbol} 数据失败: {e}")
        
        return results
    
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取股票基本信息
        
        Args:
            symbol: 股票代码
        
        Returns:
            股票信息字典
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # 提取关键信息
            stock_info = {
                'symbol': symbol,
                'name': info.get('longName', ''),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'dividend_yield': info.get('dividendYield', 0),
                'beta': info.get('beta', 0),
                '52_week_high': info.get('fiftyTwoWeekHigh', 0),
                '52_week_low': info.get('fiftyTwoWeekLow', 0),
                'volume_avg': info.get('averageVolume', 0),
                'currency': info.get('currency', 'USD'),
                'exchange': info.get('exchange', ''),
                'quote_type': info.get('quoteType', ''),
                'updated_at': datetime.now().isoformat()
            }
            
            return stock_info
            
        except Exception as e:
            logger.error(f"获取股票 {symbol} 信息失败: {e}")
            return {}
    
    def get_current_price(self, symbol: str) -> float:
        """
        获取当前股价
        
        Args:
            symbol: 股票代码
        
        Returns:
            当前股价，获取失败返回0
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"获取股票 {symbol} 当前价格失败: {e}")
            return 0.0