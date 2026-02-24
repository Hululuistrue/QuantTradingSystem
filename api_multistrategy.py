#!/usr/bin/env python3
"""
量化交易系统API - 多策略版本
支持：双均线、RSI、MACD、布林带、历史数据模拟
"""

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import sys
from typing import List, Optional, Dict, Any

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入策略管理器
try:
    from strategies.strategy_manager import strategy_manager
    STRATEGY_MANAGER_ENABLED = True
    print("策略管理器加载成功")
except ImportError as e:
    print(f"策略管理器加载失败: {e}")
    STRATEGY_MANAGER_ENABLED = False

# 尝试导入图表模块
try:
    from charts import chart_generator
    CHARTS_ENABLED = True
    print("图表模块加载成功")
except ImportError as e:
    print(f"图表模块加载失败: {e}")
    CHARTS_ENABLED = False
    # 创建虚拟的chart_generator
    class DummyChartGenerator:
        def generate_price_chart(self, *args, **kwargs):
            return None
        def generate_strategy_chart(self, *args, **kwargs):
            return None
        def generate_backtest_chart(self, *args, **kwargs):
            return None
    chart_generator = DummyChartGenerator()

# 创建FastAPI应用
app = FastAPI(
    title="量化交易系统API - 多策略版本",
    description="美股量化交易系统API接口，支持多种交易策略",
    version="2.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查端点"""
    import socket
    import time
    import os
    from urllib.parse import urlparse
    
    status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "quant-trading-api-multistrategy",
        "version": "2.0.0",
        "database": "healthy",
        "redis": "healthy",
        "api": "healthy",
        "strategies_enabled": STRATEGY_MANAGER_ENABLED,
        "charts_enabled": CHARTS_ENABLED,
        "checks": {}
    }
    
    # Resolve DB/Redis hostnames from environment (fall back to service aliases)
    db_host = "postgres"
    redis_host = "redis"
    try:
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url:
            db_host = urlparse(db_url).hostname or db_host
    except Exception:
        pass
    try:
        redis_url = os.environ.get("REDIS_URL", "")
        if redis_url:
            redis_host = urlparse(redis_url).hostname or redis_host
    except Exception:
        pass

    # 检查数据库连接
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((db_host, 5432))
        sock.close()
        
        if result == 0:
            status["checks"]["postgres"] = "reachable"
        else:
            status["checks"]["postgres"] = "unreachable"
            status["database"] = "degraded"
    except Exception as e:
        status["checks"]["postgres"] = f"error: {str(e)}"
        status["database"] = "error"
    
    # 检查Redis连接
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((redis_host, 6379))
        sock.close()
        
        if result == 0:
            status["checks"]["redis"] = "reachable"
        else:
            status["checks"]["redis"] = "unreachable"
            status["redis"] = "degraded"
    except Exception as e:
        status["checks"]["redis"] = f"error: {str(e)}"
        status["redis"] = "error"
    
    # 检查yfinance数据源
    try:
        test_ticker = yf.Ticker("SPY")
        test_data = test_ticker.history(period="1d")
        if not test_data.empty:
            status["checks"]["yfinance"] = "working"
        else:
            status["checks"]["yfinance"] = "no_data"
            status["api"] = "degraded"
    except Exception as e:
        status["checks"]["yfinance"] = f"error: {str(e)}"
        status["api"] = "error"
    
    # 检查策略管理器
    if STRATEGY_MANAGER_ENABLED:
        strategies = strategy_manager.get_available_strategies()
        status["checks"]["strategy_manager"] = f"working ({len(strategies)} strategies)"
    else:
        status["checks"]["strategy_manager"] = "disabled"
        status["strategies_enabled"] = False
    
    return status


# 数据获取端点
@app.get("/api/v1/data")
async def get_stock_data(
    symbol: str,
    period: str = Query("1mo", description="数据周期 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)"),
    interval: str = Query("1d", description="数据间隔 (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)")
):
    """获取股票数据"""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)
        
        if data.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票数据: {symbol}")
        
        # 转换数据格式
        records = []
        for idx, row in data.iterrows():
            records.append({
                "date": idx.isoformat(),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
                "dividends": float(row["Dividends"]) if "Dividends" in row and not pd.isna(row["Dividends"]) else 0,
                "stock_splits": float(row["Stock Splits"]) if "Stock Splits" in row and not pd.isna(row["Stock Splits"]) else 0
            })
        
        return {
            "symbol": symbol,
            "period": period,
            "interval": interval,
            "data_points": len(records),
            "start_date": records[0]["date"] if records else None,
            "end_date": records[-1]["date"] if records else None,
            "latest_price": records[-1]["close"] if records else None,
            "data": records[-100:] if len(records) > 100 else records  # 限制返回数据量
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")


# 获取可用策略列表
@app.get("/api/v1/strategies")
async def get_available_strategies():
    """获取所有可用策略"""
    if not STRATEGY_MANAGER_ENABLED:
        raise HTTPException(status_code=503, detail="策略管理器未启用")
    
    strategies = strategy_manager.get_available_strategies()
    
    return {
        "total_strategies": len(strategies),
        "strategies": strategies,
        "timestamp": datetime.now().isoformat()
    }


# 通用策略运行端点
@app.get("/api/v1/strategy/run")
async def run_strategy(
    request: Request,
    symbol: str,
    strategy_id: str = Query("moving_average", description="策略ID"),
    period: str = Query("1mo", description="数据周期")
):
    """运行指定策略"""
    if not STRATEGY_MANAGER_ENABLED:
        raise HTTPException(status_code=503, detail="策略管理器未启用")

    try:
        # 获取所有查询参数
        query_params = dict(request.query_params)

        # 移除已知参数
        strategy_params = {k: v for k, v in query_params.items()
                          if k not in ['symbol', 'strategy_id', 'period']}

        # 转换参数类型（尝试转换为数字）
        for key, value in strategy_params.items():
            try:
                # 尝试转换为浮点数
                strategy_params[key] = float(value)
                # 如果是整数，转换为整数
                if strategy_params[key].is_integer():
                    strategy_params[key] = int(strategy_params[key])
            except (ValueError, AttributeError):
                # 保持字符串
                pass

        # 获取数据
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)

        if data.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票数据: {symbol}")

        # 准备数据格式
        data_df = pd.DataFrame({
            'date': data.index,
            'open': data['Open'],
            'high': data['High'],
            'low': data['Low'],
            'close': data['Close'],
            'volume': data['Volume']
        })

        # 运行策略
        result = strategy_manager.run_strategy(strategy_id, data_df, **strategy_params)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        # 添加股票信息
        result["symbol"] = symbol
        result["period"] = period
        result["data_points"] = len(data_df)
        result["timestamp"] = datetime.now().isoformat()
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"策略运行失败: {str(e)}")


# 策略回测端点
@app.get("/api/v1/strategy/backtest")
async def backtest_strategy(
    request: Request,
    symbol: str,
    strategy_id: str = Query("moving_average", description="策略ID"),
    period: str = Query("1mo", description="数据周期"),
    initial_capital: float = Query(100000.0, description="初始资金"),
    commission: float = Query(0.001, description="交易佣金率")
):
    """回测指定策略"""
    if not STRATEGY_MANAGER_ENABLED:
        raise HTTPException(status_code=503, detail="策略管理器未启用")

    try:
        # 获取所有查询参数
        query_params = dict(request.query_params)

        # 移除已知参数
        strategy_params = {k: v for k, v in query_params.items()
                          if k not in ['symbol', 'strategy_id', 'period', 'initial_capital', 'commission']}

        # 转换参数类型
        for key, value in strategy_params.items():
            try:
                strategy_params[key] = float(value)
                if strategy_params[key].is_integer():
                    strategy_params[key] = int(strategy_params[key])
            except (ValueError, AttributeError):
                pass

        # 获取数据
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)

        if data.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票数据: {symbol}")

        # 准备数据格式
        data_df = pd.DataFrame({
            'date': data.index,
            'open': data['Open'],
            'high': data['High'],
            'low': data['Low'],
            'close': data['Close'],
            'volume': data['Volume']
        })

        # 运行回测
        result = strategy_manager.backtest_strategy(
            strategy_id, data_df, initial_capital, commission, **strategy_params
        )
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        # 添加股票信息
        result["symbol"] = symbol
        result["period"] = period
        result["initial_capital"] = initial_capital
        result["commission"] = commission
        result["timestamp"] = datetime.now().isoformat()
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"策略回测失败: {str(e)}")


# 策略比较端点
@app.get("/api/v1/strategies/compare")
async def compare_strategies(
    symbol: str,
    period: str = Query("1mo", description="数据周期"),
    initial_capital: float = Query(100000.0, description="初始资金"),
    commission: float = Query(0.001, description="交易佣金率")
):
    """比较所有策略性能"""
    if not STRATEGY_MANAGER_ENABLED:
        raise HTTPException(status_code=503, detail="策略管理器未启用")
    
    try:
        # 获取数据
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)
        
        if data.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票数据: {symbol}")
        
        # 准备数据格式
        data_df = pd.DataFrame({
            'date': data.index,
            'open': data['Open'],
            'high': data['High'],
            'low': data['Low'],
            'close': data['Close'],
            'volume': data['Volume']
        })
        
        # 比较策略
        result = strategy_manager.compare_strategies(data_df, initial_capital, commission)
        
        # 添加股票信息
        result["symbol"] = symbol
        result["period"] = period
        result["initial_capital"] = initial_capital
        result["commission"] = commission
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"策略比较失败: {str(e)}")


# 历史数据模拟交易端点（保持原有功能）
@app.get("/api/v1/simulation/historical")
async def historical_simulation(
    symbol: str,
    historical_days: int = Query(30, description="历史数据天数"),
    recent_days: int = Query(10, description="最近数据天数"),
    validation_days: int = Query(10, description="验证数据天数")
):
    """历史数据模拟交易"""
    try:
        # 获取更多数据以包含验证期
        total_days = historical_days + validation_days + 10  # 额外10天作为缓冲
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=f"{total_days}d")
        
        if data.empty or len(data) < historical_days + validation_days:
            raise HTTPException(status_code=404, detail=f"数据不足: 需要{historical_days + validation_days}天数据，实际{len(data)}天")
        
        # 准备数据
        data_df = pd.DataFrame({
            'date': data.index,
            'close': data['Close']
        })
        
        # 创建历史模拟策略
        from strategies.historical_simulation import HistoricalSimulationStrategy
        params = {
            "historical_days": historical_days,
            "recent_days": recent_days,
            "validation_days": validation_days
        }
        strategy = HistoricalSimulationStrategy(symbol=symbol, parameters=params)
        
        # 运行模拟
        report = strategy.run_simulation(data_df)
        if report.get("status") != "success":
            raise HTTPException(status_code=500, detail=report.get("message", "模拟失败"))
        
        trade_signal = report.get("trade_signal") or {}
        validation_stats = report.get("validation_stats") or {}
        performance = report.get("performance") or {}
        simulation_summary = report.get("simulation_summary") or {}
        
        response = {
            "symbol": symbol,
            "trade_signal": trade_signal,
            "validation": {
                "is_correct": report.get("is_correct", False),
                "correctness_reason": report.get("correctness_reason", ""),
                "price_stats": {
                    "start_price": validation_stats.get("start_price"),
                    "end_price": validation_stats.get("end_price"),
                    "price_change": validation_stats.get("price_change"),
                    "price_change_pct": validation_stats.get("price_change_pct"),
                    "volatility_pct": validation_stats.get("volatility_pct")
                },
                "validation_period": {
                    "days": validation_stats.get("validation_days"),
                    "start_date": validation_stats.get("start_date"),
                    "end_date": validation_stats.get("end_date")
                }
            },
            "performance": {
                "signal_accuracy": performance.get("signal_accuracy"),
                "confidence_score": performance.get("confidence_score"),
                "potential_return_pct": performance.get("potential_return_pct"),
                "potential_return_type": performance.get("potential_return_type")
            },
            "data_summary": {
                "simulation_date": simulation_summary.get("simulation_date"),
                "total_data_days": simulation_summary.get("total_data_days")
            },
            "parameters": params,
            "timestamp": datetime.now().isoformat()
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"历史数据模拟失败: {str(e)}")


# 图表端点
@app.get("/api/v1/charts/price")
async def get_price_chart(
    symbol: str,
    period: str = Query("1mo", description="数据周期"),
    width: int = Query(800, description="图表宽度"),
    height: int = Query(400, description="图表高度")
):
    """获取价格图表"""
    if not CHARTS_ENABLED:
        raise HTTPException(status_code=503, detail="图表模块未启用")
    
    try:
        chart = chart_generator.generate_price_chart(symbol, period, width, height)
        if chart:
            return JSONResponse(content={"chart_url": chart})
        else:
            raise HTTPException(status_code=500, detail="生成图表失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成图表失败: {str(e)}")


# 根端点 - 显示API信息
@app.get("/")
async def root():
    """API根端点"""
    api_info = {
        "service": "Quant Trading System API",
        "version": "2.0.0",
        "description": "美股量化交易系统API，支持多种交易策略",
        "endpoints": {
            "health": "/health",
            "data": "/api/v1/data?symbol=SPY&period=1mo",
            "strategies": "/api/v1/strategies",
            "run_strategy": "/api/v1/strategy/run?symbol=SPY&strategy_id=moving_average&period=1mo",
            "backtest": "/api/v1/strategy/backtest?symbol=SPY&strategy_id=moving_average&period=1mo",
            "compare_strategies": "/api/v1/strategies/compare?symbol=SPY&period=1mo",
            "historical_simulation": "/api/v1/simulation/historical?symbol=SPY",
            "price_chart": "/api/v1/charts/price?symbol=SPY&period=1mo"
        },
        "available_strategies": [],
        "timestamp": datetime.now().isoformat()
    }
    
    if STRATEGY_MANAGER_ENABLED:
        strategies = strategy_manager.get_available_strategies()
        api_info["available_strategies"] = [s["name"] for s in strategies]
    
    return api_info


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
