"""
简化版量化交易系统API
避免数据库依赖，快速启动测试
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import uvicorn
import logging
from datetime import datetime, date
import pandas as pd
import numpy as np
import yfinance as yf

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="美股量化交易系统API (简化版)",
    description="提供量化策略管理、数据获取、回测等功能",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据获取器
class YahooFinanceFetcher:
    """雅虎财经数据获取器"""
    
    def get_stock_data(self, symbol: str, period: str = "1mo") -> pd.DataFrame:
        """获取股票数据"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period)
            
            if data.empty:
                return pd.DataFrame()
            
            # 重命名列
            data = data.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # 添加symbol列
            data['symbol'] = symbol
            
            # 重置索引
            data = data.reset_index()
            data = data.rename(columns={'Date': 'date'})
            
            # 确保日期格式正确
            data['date'] = pd.to_datetime(data['date']).dt.date
            
            return data
            
        except Exception as e:
            logger.error(f"获取股票 {symbol} 数据失败: {e}")
            return pd.DataFrame()

# 策略类
class MovingAverageStrategy:
    """双均线交叉策略"""
    
    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        self.fast_period = fast_period
        self.slow_period = slow_period
    
    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        """运行策略"""
        data = data.copy()
        
        # 计算移动平均线
        data['ma_fast'] = data['close'].rolling(window=self.fast_period).mean()
        data['ma_slow'] = data['close'].rolling(window=self.slow_period).mean()
        
        # 计算交叉信号
        data['ma_diff'] = data['ma_fast'] - data['ma_slow']
        data['signal'] = 'hold'
        data.loc[data['ma_diff'] > 0, 'signal'] = 'buy'
        data.loc[data['ma_diff'] < 0, 'signal'] = 'sell'
        
        # 计算信号变化点
        data['signal_change'] = data['signal'].ne(data['signal'].shift())
        
        return data

# 全局实例
fetcher = YahooFinanceFetcher()
strategy = MovingAverageStrategy()

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "欢迎使用美股量化交易系统API (简化版)",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": [
            "/api/v1/data/{symbol}",
            "/api/v1/strategy/{symbol}",
            "/api/v1/backtest/{symbol}"
        ]
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "quant-trading-api-simple"
    }

@app.get("/api/v1/data/{symbol}")
async def get_stock_data(
    symbol: str,
    period: str = Query("1mo", description="数据周期: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max")
):
    """获取股票数据"""
    try:
        data = fetcher.get_stock_data(symbol, period)
        
        if data.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票 {symbol} 的数据")
        
        # 转换为字典列表
        records = data.to_dict(orient='records')
        
        return {
            "symbol": symbol,
            "count": len(records),
            "period": period,
            "start_date": data['date'].min().strftime('%Y-%m-%d') if not data.empty else None,
            "end_date": data['date'].max().strftime('%Y-%m-%d') if not data.empty else None,
            "price_range": {
                "min": float(data['close'].min()) if not data.empty else 0,
                "max": float(data['close'].max()) if not data.empty else 0,
                "latest": float(data['close'].iloc[-1]) if not data.empty else 0
            },
            "data": records[:100]  # 限制返回数量
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取股票数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/strategy/{symbol}")
async def run_strategy(
    symbol: str,
    period: str = Query("1mo", description="数据周期"),
    fast_period: int = Query(10, description="快线周期"),
    slow_period: int = Query(30, description="慢线周期")
):
    """运行策略"""
    try:
        # 获取数据
        data = fetcher.get_stock_data(symbol, period)
        
        if data.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票 {symbol} 的数据")
        
        # 创建策略实例
        strategy_instance = MovingAverageStrategy(
            fast_period=fast_period,
            slow_period=slow_period
        )
        
        # 运行策略
        result = strategy_instance.run(data)
        
        # 统计信号
        signals = result[result['signal_change']]
        buy_signals = len(signals[signals['signal'] == 'buy'])
        sell_signals = len(signals[signals['signal'] == 'sell'])
        
        # 获取信号详情
        signal_details = []
        for idx, row in signals.iterrows():
            if row['signal'] in ['buy', 'sell']:
                signal_details.append({
                    "date": row['date'].strftime('%Y-%m-%d'),
                    "signal": row['signal'],
                    "price": float(row['close']),
                    "ma_fast": float(row['ma_fast']),
                    "ma_slow": float(row['ma_slow'])
                })
        
        return {
            "symbol": symbol,
            "period": period,
            "parameters": {
                "fast_period": fast_period,
                "slow_period": slow_period
            },
            "statistics": {
                "total_days": len(data),
                "buy_signals": buy_signals,
                "sell_signals": sell_signals,
                "total_signals": buy_signals + sell_signals
            },
            "latest_signal": {
                "signal": result['signal'].iloc[-1],
                "date": result['date'].iloc[-1].strftime('%Y-%m-%d'),
                "price": float(result['close'].iloc[-1]),
                "ma_fast": float(result['ma_fast'].iloc[-1]),
                "ma_slow": float(result['ma_slow'].iloc[-1])
            } if len(result) > 0 else None,
            "signals": signal_details[:20]  # 限制返回数量
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"运行策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/backtest/{symbol}")
async def run_backtest(
    symbol: str,
    period: str = Query("1y", description="数据周期"),
    fast_period: int = Query(10, description="快线周期"),
    slow_period: int = Query(30, description="慢线周期"),
    initial_capital: float = Query(10000, description="初始资金")
):
    """运行回测"""
    try:
        # 获取数据
        data = fetcher.get_stock_data(symbol, period)
        
        if data.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票 {symbol} 的数据")
        
        # 运行策略
        strategy_instance = MovingAverageStrategy(
            fast_period=fast_period,
            slow_period=slow_period
        )
        result = strategy_instance.run(data)
        
        # 简单回测逻辑
        capital = initial_capital
        position = 0
        trades = []
        
        for i in range(len(result)):
            if result.iloc[i]['signal'] == 'buy' and position == 0:
                # 买入
                price = result.iloc[i]['close']
                position = capital / price
                capital = 0
                trades.append({
                    "date": result.iloc[i]['date'].strftime('%Y-%m-%d'),
                    "type": "buy",
                    "price": float(price),
                    "shares": float(position)
                })
            elif result.iloc[i]['signal'] == 'sell' and position > 0:
                # 卖出
                price = result.iloc[i]['close']
                capital = position * price
                position = 0
                trades.append({
                    "date": result.iloc[i]['date'].strftime('%Y-%m-%d'),
                    "type": "sell",
                    "price": float(price),
                    "shares": 0
                })
        
        # 计算最终价值
        if position > 0:
            final_value = position * result.iloc[-1]['close']
        else:
            final_value = capital
        
        total_return = (final_value - initial_capital) / initial_capital
        
        # 计算简单指标
        if len(trades) >= 2:
            # 计算胜率（简单版本）
            profitable_trades = 0
            for i in range(0, len(trades)-1, 2):
                if i+1 < len(trades):
                    buy_price = trades[i]['price']
                    sell_price = trades[i+1]['price']
                    if sell_price > buy_price:
                        profitable_trades += 1
            
            win_rate = profitable_trades / (len(trades) // 2) if len(trades) >= 2 else 0
        else:
            win_rate = 0
        
        return {
            "symbol": symbol,
            "period": period,
            "parameters": {
                "fast_period": fast_period,
                "slow_period": slow_period,
                "initial_capital": initial_capital
            },
            "results": {
                "initial_capital": initial_capital,
                "final_value": float(final_value),
                "total_return": float(total_return),
                "total_trades": len(trades),
                "win_rate": float(win_rate),
                "position": "持有" if position > 0 else "空仓"
            },
            "trades": trades[:20]  # 限制返回数量
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"运行回测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/symbols/popular")
async def get_popular_symbols():
    """获取热门股票代码"""
    popular_symbols = [
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "type": "ETF"},
        {"symbol": "QQQ", "name": "Invesco QQQ Trust", "type": "ETF"},
        {"symbol": "AAPL", "name": "Apple Inc.", "type": "Stock"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "type": "Stock"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "type": "Stock"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "type": "Stock"},
        {"symbol": "TSLA", "name": "Tesla Inc.", "type": "Stock"},
        {"symbol": "NVDA", "name": "NVIDIA Corporation", "type": "Stock"},
        {"symbol": "META", "name": "Meta Platforms Inc.", "type": "Stock"}
    ]
    
    return {
        "count": len(popular_symbols),
        "symbols": popular_symbols
    }

# 错误处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """通用异常处理"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "内部服务器错误",
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "api_simple:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )