"""
Alpha Vantage数据获取器
免费API：500次/天，5次/分钟
"""

import requests
import pandas as pd
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import os

logger = logging.getLogger(__name__)


class AlphaVantageFetcher:
    """Alpha Vantage数据获取器"""
    
    def __init__(self, api_key: str = None, cache_dir: str = None):
        """
        初始化Alpha Vantage数据获取器
        
        Args:
            api_key: Alpha Vantage API密钥，如果为None则尝试从环境变量获取
            cache_dir: 缓存目录路径
        """
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_API_KEY')
        if not self.api_key:
            logger.warning("未提供Alpha Vantage API密钥，将无法使用此数据源")
        
        self.cache_dir = cache_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        
        self.base_url = "https://www.alphavantage.co/query"
        self.last_request_time = 0
        self.min_request_interval = 12  # 秒（5次/分钟 = 12秒/次）
    
    def _make_request(self, params: Dict[str, str]) -> Dict[str, Any]:
        """
        发送API请求，包含速率限制
        
        Args:
            params: 请求参数
        
        Returns:
            API响应数据
        """
        if not self.api_key:
            logger.error("未设置Alpha Vantage API密钥")
            return {}
        
        # 添加API密钥
        params['apikey'] = self.api_key
        
        # 速率限制
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.debug(f"速率限制，等待 {sleep_time:.1f} 秒")
            time.sleep(sleep_time)
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            self.last_request_time = time.time()
            
            # 检查错误
            if "Error Message" in data:
                logger.error(f"Alpha Vantage API错误: {data['Error Message']}")
                return {}
            if "Note" in data:  # 速率限制提示
                logger.warning(f"Alpha Vantage API提示: {data['Note']}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Alpha Vantage API请求失败: {e}")
            return {}
        except ValueError as e:
            logger.error(f"Alpha Vantage API响应解析失败: {e}")
            return {}
    
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
            interval: 数据间隔 (如: "1d", "1wk", "1mo")
        
        Returns:
            pandas DataFrame 包含股票数据
        """
        try:
            # Alpha Vantage支持的时间间隔映射
            interval_map = {
                "1d": "TIME_SERIES_DAILY",
                "1wk": "TIME_SERIES_WEEKLY",
                "1mo": "TIME_SERIES_MONTHLY"
            }
            
            if interval not in interval_map:
                logger.warning(f"Alpha Vantage不支持的时间间隔: {interval}，使用1d")
                interval = "1d"
            
            function = interval_map[interval]
            
            # 构建请求参数
            params = {
                "function": function,
                "symbol": symbol,
                "outputsize": "full" if period in ["2y", "5y", "10y", "max"] else "compact"
            }
            
            data = self._make_request(params)
            if not data:
                return pd.DataFrame()
            
            # 解析数据
            time_series_key = None
            for key in data.keys():
                if "Time Series" in key:
                    time_series_key = key
                    break
            
            if not time_series_key:
                logger.error(f"未找到时间序列数据: {symbol}")
                return pd.DataFrame()
            
            time_series = data[time_series_key]
            
            # 转换为DataFrame
            records = []
            for date_str, values in time_series.items():
                record = {
                    'date': pd.to_datetime(date_str).date(),
                    'open': float(values.get('1. open', 0)),
                    'high': float(values.get('2. high', 0)),
                    'low': float(values.get('3. low', 0)),
                    'close': float(values.get('4. close', 0)),
                    'volume': int(float(values.get('5. volume', 0))),
                    'symbol': symbol
                }
                records.append(record)
            
            df = pd.DataFrame(records)
            
            # 按日期排序
            df = df.sort_values('date')
            
            # 日期筛选
            if start_date:
                start_date_dt = pd.to_datetime(start_date).date()
                df = df[df['date'] >= start_date_dt]
            
            if end_date:
                end_date_dt = pd.to_datetime(end_date).date()
                df = df[df['date'] <= end_date_dt]
            
            # 根据period筛选
            if period != "max" and not start_date and not end_date:
                end_date_dt = datetime.now().date()
                if period == "1y":
                    start_date_dt = end_date_dt - timedelta(days=365)
                elif period == "6mo":
                    start_date_dt = end_date_dt - timedelta(days=180)
                elif period == "3mo":
                    start_date_dt = end_date_dt - timedelta(days=90)
                elif period == "1mo":
                    start_date_dt = end_date_dt - timedelta(days=30)
                elif period == "5d":
                    start_date_dt = end_date_dt - timedelta(days=5)
                elif period == "1d":
                    start_date_dt = end_date_dt - timedelta(days=1)
                
                df = df[df['date'] >= start_date_dt]
            
            logger.info(f"成功从Alpha Vantage获取 {symbol} 数据: {len(df)} 行")
            return df
            
        except Exception as e:
            logger.error(f"从Alpha Vantage获取股票 {symbol} 数据失败: {e}")
            return pd.DataFrame()
    
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取股票基本信息
        
        Args:
            symbol: 股票代码
        
        Returns:
            股票信息字典
        """
        try:
            params = {
                "function": "OVERVIEW",
                "symbol": symbol
            }
            
            data = self._make_request(params)
            if not data:
                return {}
            
            # 提取关键信息
            stock_info = {
                'symbol': symbol,
                'name': data.get('Name', ''),
                'sector': data.get('Sector', ''),
                'industry': data.get('Industry', ''),
                'market_cap': float(data.get('MarketCapitalization', 0)),
                'pe_ratio': float(data.get('PERatio', 0)),
                'dividend_yield': float(data.get('DividendYield', 0)),
                'beta': float(data.get('Beta', 0)),
                '52_week_high': float(data.get('52WeekHigh', 0)),
                '52_week_low': float(data.get('52WeekLow', 0)),
                'volume_avg': float(data.get('Volume', 0)),
                'currency': data.get('Currency', 'USD'),
                'exchange': data.get('Exchange', ''),
                'quote_type': 'EQUITY',
                'updated_at': datetime.now().isoformat()
            }
            
            return stock_info
            
        except Exception as e:
            logger.error(f"从Alpha Vantage获取股票 {symbol} 信息失败: {e}")
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
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol
            }
            
            data = self._make_request(params)
            if not data or "Global Quote" not in data:
                return 0.0
            
            quote = data["Global Quote"]
            price_str = quote.get("05. price", "0")
            
            try:
                price = float(price_str)
                return price
            except ValueError:
                logger.error(f"价格解析失败: {price_str}")
                return 0.0
                
        except Exception as e:
            logger.error(f"从Alpha Vantage获取股票 {symbol} 当前价格失败: {e}")
            return 0.0
    
    def get_technical_indicators(
        self,
        symbol: str,
        function: str = "SMA",
        interval: str = "daily",
        time_period: int = 20,
        series_type: str = "close"
    ) -> pd.DataFrame:
        """
        获取技术指标数据
        
        Args:
            symbol: 股票代码
            function: 技术指标函数 (SMA, EMA, RSI, MACD, BBANDS等)
            interval: 时间间隔 (daily, weekly, monthly)
            time_period: 时间周期
            series_type: 序列类型 (close, open, high, low)
        
        Returns:
            技术指标DataFrame
        """
        try:
            params = {
                "function": function,
                "symbol": symbol,
                "interval": interval,
                "time_period": time_period,
                "series_type": series_type
            }
            
            data = self._make_request(params)
            if not data or f"Technical Analysis: {function}" not in data:
                return pd.DataFrame()
            
            tech_key = f"Technical Analysis: {function}"
            tech_data = data[tech_key]
            
            # 转换为DataFrame
            records = []
            for date_str, values in tech_data.items():
                record = {'date': pd.to_datetime(date_str).date(), 'symbol': symbol}
                for key, value in values.items():
                    # 清理键名
                    clean_key = key.replace(f" {function}", "").strip()
                    try:
                        record[clean_key] = float(value)
                    except ValueError:
                        record[clean_key] = value
                records.append(record)
            
            df = pd.DataFrame(records)
            df = df.sort_values('date')
            
            return df
            
        except Exception as e:
            logger.error(f"获取技术指标失败: {e}")
            return pd.DataFrame()