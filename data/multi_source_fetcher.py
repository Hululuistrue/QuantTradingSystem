"""
多数据源管理器
支持故障转移和数据质量检查
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import os
import json
import hashlib
from .fetcher import YahooFinanceFetcher
from .alpha_vantage_fetcher import AlphaVantageFetcher

logger = logging.getLogger(__name__)


class MultiSourceFetcher:
    """多数据源管理器"""
    
    def __init__(self, cache_dir: str = "/tmp/quant_cache"):
        """
        初始化多数据源管理器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # 初始化数据源（按优先级排序）
        self.data_sources = []
        
        # 1. Yahoo Finance（主要数据源）
        self.yahoo_fetcher = YahooFinanceFetcher(cache_dir=os.path.join(cache_dir, "yahoo"))
        self.data_sources.append(("yahoo", self.yahoo_fetcher))
        
        # 2. Alpha Vantage（备用数据源）
        alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if alpha_vantage_key:
            self.alpha_fetcher = AlphaVantageFetcher(
                api_key=alpha_vantage_key,
                cache_dir=os.path.join(cache_dir, "alpha_vantage")
            )
            self.data_sources.append(("alpha_vantage", self.alpha_fetcher))
            logger.info("Alpha Vantage数据源已启用")
        else:
            logger.warning("未设置ALPHA_VANTAGE_API_KEY环境变量，Alpha Vantage数据源未启用")
            self.alpha_fetcher = None
        
        # 数据源状态监控
        self.source_status = {name: {"success": 0, "failure": 0, "last_used": None} 
                             for name, _ in self.data_sources}
        
        logger.info(f"多数据源管理器初始化完成，可用数据源: {[name for name, _ in self.data_sources]}")
    
    def _get_cache_key(self, symbol: str, start_date: str = None, 
                      end_date: str = None, period: str = "1y", 
                      interval: str = "1d") -> str:
        """生成缓存键"""
        key_parts = [
            symbol,
            start_date or "",
            end_date or "",
            period,
            interval,
            datetime.now().strftime("%Y-%m-%d")  # 每天缓存不同
        ]
        key_str = "_".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _load_from_cache(self, cache_key: str) -> Optional[pd.DataFrame]:
        """从缓存加载数据"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.parquet")
        if os.path.exists(cache_file):
            try:
                # 检查缓存是否过期（1小时）
                file_mtime = os.path.getmtime(cache_file)
                if datetime.now().timestamp() - file_mtime < 3600:
                    df = pd.read_parquet(cache_file)
                    logger.debug(f"从缓存加载数据: {cache_key}")
                    return df
            except Exception as e:
                logger.warning(f"读取缓存失败: {e}")
        return None
    
    def _save_to_cache(self, cache_key: str, data: pd.DataFrame):
        """保存数据到缓存"""
        try:
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.parquet")
            data.to_parquet(cache_file)
            logger.debug(f"数据已缓存: {cache_key}")
        except Exception as e:
            logger.warning(f"保存缓存失败: {e}")
    
    def _validate_data(self, data: pd.DataFrame, symbol: str) -> Tuple[bool, str]:
        """
        验证数据质量
        
        Returns:
            (是否有效, 错误信息)
        """
        if data.empty:
            return False, "数据为空"
        
        # 检查必要列
        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in data.columns:
                return False, f"缺少必要列: {col}"
        
        # 检查数据行数
        if len(data) < 5:
            return False, f"数据行数不足: {len(data)}"
        
        # 检查日期顺序
        if not data['date'].is_monotonic_increasing:
            return False, "日期不是单调递增"
        
        # 检查缺失值
        missing_count = data[required_columns].isnull().sum().sum()
        if missing_count > len(data) * 0.1:  # 超过10%的缺失值
            return False, f"缺失值过多: {missing_count}"
        
        # 检查价格合理性
        price_columns = ['open', 'high', 'low', 'close']
        for col in price_columns:
            if (data[col] <= 0).any():
                return False, f"存在非正价格: {col}"
            if (data[col] > 10000).any():  # 假设价格不超过10000
                return False, f"价格异常高: {col}"
        
        # 检查high >= low >= close的逻辑
        invalid_rows = (
            (data['high'] < data['low']) | 
            (data['high'] < data['open']) | 
            (data['high'] < data['close']) |
            (data['low'] > data['open']) | 
            (data['low'] > data['close'])
        )
        if invalid_rows.any():
            return False, "价格数据逻辑错误"
        
        # 检查成交量
        if (data['volume'] < 0).any():
            return False, "存在负成交量"
        
        return True, "数据质量良好"
    
    def get_stock_data(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
        period: str = "1y",
        interval: str = "1d",
        use_cache: bool = True,
        validate: bool = True
    ) -> pd.DataFrame:
        """
        获取股票历史数据（支持多数据源故障转移）
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 数据周期
            interval: 数据间隔
            use_cache: 是否使用缓存
            validate: 是否验证数据质量
        
        Returns:
            股票数据DataFrame
        """
        # 生成缓存键
        cache_key = self._get_cache_key(symbol, start_date, end_date, period, interval)
        
        # 尝试从缓存加载
        if use_cache:
            cached_data = self._load_from_cache(cache_key)
            if cached_data is not None:
                logger.info(f"使用缓存数据: {symbol}")
                return cached_data
        
        # 按优先级尝试各个数据源
        best_data = pd.DataFrame()
        best_source = None
        best_quality_score = -1
        
        for source_name, fetcher in self.data_sources:
            try:
                logger.info(f"尝试从 {source_name} 获取 {symbol} 数据...")
                
                data = fetcher.get_stock_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    period=period,
                    interval=interval
                )
                
                if data.empty:
                    logger.warning(f"{source_name} 返回空数据: {symbol}")
                    self.source_status[source_name]["failure"] += 1
                    continue
                
                # 验证数据质量
                if validate:
                    is_valid, message = self._validate_data(data, symbol)
                    if not is_valid:
                        logger.warning(f"{source_name} 数据验证失败: {message}")
                        self.source_status[source_name]["failure"] += 1
                        continue
                
                # 计算数据质量分数
                quality_score = self._calculate_quality_score(data)
                
                # 更新最佳数据
                if quality_score > best_quality_score:
                    best_data = data
                    best_source = source_name
                    best_quality_score = quality_score
                    
                    self.source_status[source_name]["success"] += 1
                    self.source_status[source_name]["last_used"] = datetime.now()
                    
                    logger.info(f"{source_name} 提供优质数据: {symbol} (质量分: {quality_score:.2f})")
                
                # 如果质量分很高，直接使用
                if quality_score > 0.9:
                    break
                    
            except Exception as e:
                logger.error(f"{source_name} 获取数据失败: {e}")
                self.source_status[source_name]["failure"] += 1
        
        if best_data.empty:
            logger.error(f"所有数据源都失败: {symbol}")
            return pd.DataFrame()
        
        logger.info(f"最终使用 {best_source} 的数据: {symbol} (行数: {len(best_data)})")
        
        # 缓存数据
        if use_cache and not best_data.empty:
            self._save_to_cache(cache_key, best_data)
        
        return best_data
    
    def _calculate_quality_score(self, data: pd.DataFrame) -> float:
        """计算数据质量分数（0-1）"""
        if data.empty:
            return 0.0
        
        score = 0.0
        
        # 1. 数据完整性（30%）
        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        completeness = sum(1 for col in required_columns if col in data.columns) / len(required_columns)
        score += completeness * 0.3
        
        # 2. 数据量（20%）
        row_count = len(data)
        if row_count >= 200:
            row_score = 1.0
        elif row_count >= 100:
            row_score = 0.8
        elif row_count >= 50:
            row_score = 0.6
        elif row_count >= 20:
            row_score = 0.4
        else:
            row_score = 0.2
        score += row_score * 0.2
        
        # 3. 数据连续性（20%）
        if 'date' in data.columns and len(data) > 1:
            data = data.sort_values('date')
            date_diff = data['date'].diff().dt.days.iloc[1:].mean()
            if date_diff <= 1.5:  # 平均间隔小于1.5天
                continuity = 1.0
            elif date_diff <= 3:
                continuity = 0.7
            elif date_diff <= 7:
                continuity = 0.4
            else:
                continuity = 0.1
            score += continuity * 0.2
        
        # 4. 数据合理性（30%）
        if all(col in data.columns for col in ['open', 'high', 'low', 'close']):
            # 检查价格逻辑
            valid_logic = (
                (data['high'] >= data['low']) & 
                (data['high'] >= data['open']) & 
                (data['high'] >= data['close']) &
                (data['low'] <= data['open']) & 
                (data['low'] <= data['close'])
            ).mean()
            
            # 检查价格变化合理性
            price_columns = ['open', 'high', 'low', 'close']
            price_changes = data[price_columns].pct_change().abs()
            reasonable_changes = (price_changes < 0.5).all(axis=1).mean()  # 单日涨跌幅小于50%
            
            rationality = (valid_logic + reasonable_changes) / 2
            score += rationality * 0.3
        
        return min(score, 1.0)
    
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """获取股票基本信息"""
        for source_name, fetcher in self.data_sources:
            try:
                info = fetcher.get_stock_info(symbol)
                if info:
                    logger.info(f"从 {source_name} 获取股票信息: {symbol}")
                    return info
            except Exception as e:
                logger.warning(f"{source_name} 获取股票信息失败: {e}")
        
        logger.error(f"所有数据源都未能获取股票信息: {symbol}")
        return {}
    
    def get_current_price(self, symbol: str) -> float:
        """获取当前股价"""
        for source_name, fetcher in self.data_sources:
            try:
                price = fetcher.get_current_price(symbol)
                if price > 0:
                    logger.info(f"从 {source_name} 获取当前价格: {symbol} = {price}")
                    return price
            except Exception as e:
                logger.warning(f"{source_name} 获取当前价格失败: {e}")
        
        logger.error(f"所有数据源都未能获取当前价格: {symbol}")
        return 0.0
    
    def get_source_status(self) -> Dict[str, Dict[str, Any]]:
        """获取数据源状态"""
        status = {}
        for source_name in self.source_status:
            stats = self.source_status[source_name]
            total = stats["success"] + stats["failure"]
            success_rate = stats["success"] / total if total > 0 else 0
            
            status[source_name] = {
                "success": stats["success"],
                "failure": stats["failure"],
                "success_rate": success_rate,
                "last_used": stats["last_used"],
                "enabled": True
            }
        
        return status
    
    def get_multiple_stocks(
        self,
        symbols: List[str],
        start_date: str = None,
        end_date: str = None,
        period: str = "1y",
        interval: str = "1d"
    ) -> Dict[str, pd.DataFrame]:
        """批量获取多个股票数据"""
        results = {}
        
        for symbol in symbols:
            try:
                data = self.get_stock_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    period=period,
                    interval=interval
                )
                
                if not data.empty:
                    results[symbol] = data
                else:
                    logger.warning(f"股票 {symbol} 无数据")
                    
            except Exception as e:
                logger.error(f"获取股票 {symbol} 数据失败: {e}")
        
        return results