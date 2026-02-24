#!/usr/bin/env python3
"""
量化交易系统API - 简化Docker版本
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import sys
from typing import List, Optional

# 添加当前目录到Python路径，以便导入charts模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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
    title="量化交易系统API",
    description="美股量化交易系统API接口",
    version="1.0.0"
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
    
    status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "quant-trading-api",
        "version": "1.0.0",
        "database": "healthy",
        "redis": "healthy",
        "api": "healthy",
        "checks": {}
    }
    
    # 检查数据库连接
    try:
        # 尝试连接PostgreSQL
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('quant-postgres', 5432))
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
        result = sock.connect_ex(('quant-redis', 6379))
        sock.close()
        
        if result == 0:
            status["checks"]["redis"] = "reachable"
        else:
            status["checks"]["redis"] = "unreachable"
            status["redis"] = "degraded"
    except Exception as e:
        status["checks"]["redis"] = f"error: {str(e)}"
        status["redis"] = "error"
    
    # 检查API自身状态
    try:
        # 简单的自检
        test_data = yf.Ticker("SPY").history(period="1d")
        if not test_data.empty:
            status["checks"]["yfinance"] = "working"
        else:
            status["checks"]["yfinance"] = "no_data"
            status["api"] = "degraded"
    except Exception as e:
        status["checks"]["yfinance"] = f"error: {str(e)}"
        status["api"] = "error"
    
    # 如果任何组件有错误，整体状态设为degraded
    if "error" in [status["database"], status["redis"], status["api"]]:
        status["status"] = "degraded"
    elif "degraded" in [status["database"], status["redis"], status["api"]]:
        status["status"] = "degraded"
    
    return status

# 数据获取端点
@app.get("/api/v1/data/{symbol}")
async def get_stock_data(
    symbol: str,
    period: str = Query("1mo", description="数据周期: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max"),
    interval: str = Query("1d", description="数据间隔: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo")
):
    """获取股票数据"""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)
        
        if data.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票数据: {symbol}")
        
        # 转换为JSON格式
        result = []
        for idx, row in data.iterrows():
            result.append({
                "date": idx.isoformat(),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
                "dividends": float(row["Dividends"]) if "Dividends" in row else 0.0,
                "stock_splits": float(row["Stock Splits"]) if "Stock Splits" in row else 0.0
            })
        
        return {
            "symbol": symbol,
            "period": period,
            "interval": interval,
            "count": len(result),
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")

# 双均线策略端点
@app.get("/api/v1/strategy/moving_average")
async def moving_average_strategy(
    symbol: str,
    fast_period: int = Query(10, description="快线周期"),
    slow_period: int = Query(30, description="慢线周期"),
    period: str = Query("1mo", description="数据周期")
):
    """运行双均线策略"""
    try:
        # 获取数据
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)
        
        if data.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票数据: {symbol}")
        
        # 计算移动平均线
        data['ma_fast'] = data['Close'].rolling(window=fast_period).mean()
        data['ma_slow'] = data['Close'].rolling(window=slow_period).mean()
        
        # 计算交叉信号
        data['ma_diff'] = data['ma_fast'] - data['ma_slow']
        data['signal'] = 'hold'
        data.loc[data['ma_diff'] > 0, 'signal'] = 'buy'
        data.loc[data['ma_diff'] < 0, 'signal'] = 'sell'
        
        # 准备结果
        signals = []
        for idx, row in data.iterrows():
            if row['signal'] != 'hold':
                signals.append({
                    "date": idx.isoformat(),
                    "price": float(row["Close"]),
                    "signal": row['signal'],
                    "ma_fast": float(row['ma_fast']) if not pd.isna(row['ma_fast']) else None,
                    "ma_slow": float(row['ma_slow']) if not pd.isna(row['ma_slow']) else None
                })
        
        # 统计信息
        buy_signals = len([s for s in signals if s['signal'] == 'buy'])
        sell_signals = len([s for s in signals if s['signal'] == 'sell'])
        
        return {
            "symbol": symbol,
            "strategy": "moving_average_crossover",
            "parameters": {
                "fast_period": fast_period,
                "slow_period": slow_period
            },
            "period": period,
            "signals": {
                "total": len(signals),
                "buy": buy_signals,
                "sell": sell_signals
            },
            "latest_signal": signals[-1] if signals else None,
            "data": signals[-10:] if len(signals) > 10 else signals  # 返回最近10个信号
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"策略运行失败: {str(e)}")

# 简单回测端点
@app.get("/api/v1/backtest/simple")
async def simple_backtest(
    symbol: str,
    initial_capital: float = Query(10000.0, description="初始资金"),
    fast_period: int = Query(10, description="快线周期"),
    slow_period: int = Query(30, description="慢线周期"),
    period: str = Query("1mo", description="数据周期")
):
    """简单回测"""
    try:
        # 获取数据
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)
        
        if data.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票数据: {symbol}")
        
        # 计算移动平均线
        data['ma_fast'] = data['Close'].rolling(window=fast_period).mean()
        data['ma_slow'] = data['Close'].rolling(window=slow_period).mean()
        
        # 计算信号
        data['ma_diff'] = data['ma_fast'] - data['ma_slow']
        data['signal'] = 'hold'
        data.loc[data['ma_diff'] > 0, 'signal'] = 'buy'
        data.loc[data['ma_diff'] < 0, 'signal'] = 'sell'
        
        # 回测逻辑
        capital = initial_capital
        position = 0
        trades = []
        
        for i in range(len(data)):
            if data.iloc[i]['signal'] == 'buy' and position == 0:
                # 买入
                price = data.iloc[i]['Close']
                position = capital / price
                capital = 0
                trades.append({
                    "date": data.index[i].isoformat(),
                    "type": "buy",
                    "price": float(price),
                    "shares": float(position),
                    "value": float(position * price)
                })
            elif data.iloc[i]['signal'] == 'sell' and position > 0:
                # 卖出
                price = data.iloc[i]['Close']
                capital = position * price
                position = 0
                trades.append({
                    "date": data.index[i].isoformat(),
                    "type": "sell",
                    "price": float(price),
                    "shares": 0,
                    "value": float(capital)
                })
        
        # 计算最终价值
        if position > 0:
            final_value = position * data.iloc[-1]['Close']
        else:
            final_value = capital
        
        total_return = (final_value - initial_capital) / initial_capital
        
        return {
            "symbol": symbol,
            "initial_capital": initial_capital,
            "final_value": float(final_value),
            "total_return": float(total_return),
            "total_return_percent": f"{total_return:.2%}",
            "trades_count": len(trades),
            "trades": trades[-5:] if len(trades) > 5 else trades,  # 返回最近5次交易
            "parameters": {
                "fast_period": fast_period,
                "slow_period": slow_period,
                "period": period
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回测失败: {str(e)}")

# 历史数据模拟交易端点
@app.get("/api/v1/simulation/historical")
async def historical_simulation(
    symbol: str,
    historical_days: int = Query(30, description="历史数据天数"),
    recent_days: int = Query(10, description="最近天数"),
    validation_days: int = Query(10, description="验证天数"),
    period: str = Query("3mo", description="数据周期")
):
    """历史数据模拟交易
    
    基于历史数据，对比30天整体均线和最后10天均线
    给出买入/卖出判断，并用后续数据验证策略准确性
    """
    try:
        # 获取数据
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)
        
        if data.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票数据: {symbol}")
        
        # 重置索引并添加日期列
        data = data.reset_index()
        data['date'] = pd.to_datetime(data['Date'])
        
        # 确保数据足够
        total_days_needed = historical_days + validation_days
        if len(data) < total_days_needed:
            raise HTTPException(
                status_code=400, 
                detail=f"数据不足，需要{total_days_needed}天，实际只有{len(data)}天"
            )
        
        # 分割数据
        historical_data = data.iloc[:historical_days]
        validation_data = data.iloc[historical_days:historical_days + validation_days]
        
        # 计算30天整体均线
        ma_30_overall = historical_data['Close'].mean()
        
        # 计算最后10天均线
        recent_data = historical_data.tail(recent_days)
        ma_10_recent = recent_data['Close'].mean()
        
        # 生成交易信号
        signal = 'hold'
        signal_description = ''
        signal_strength = 0
        
        if ma_10_recent > ma_30_overall:
            signal = 'buy'
            signal_description = f"最后{recent_days}天均线({ma_10_recent:.2f}) > {historical_days}天整体均线({ma_30_overall:.2f})"
            signal_strength = (ma_10_recent - ma_30_overall) / ma_30_overall * 100
        elif ma_10_recent < ma_30_overall:
            signal = 'sell'
            signal_description = f"最后{recent_days}天均线({ma_10_recent:.2f}) < {historical_days}天整体均线({ma_30_overall:.2f})"
            signal_strength = (ma_10_recent - ma_30_overall) / ma_30_overall * 100
        else:
            signal_description = f"最后{recent_days}天均线({ma_10_recent:.2f}) = {historical_days}天整体均线({ma_30_overall:.2f})"
        
        # 验证信号准确性
        start_price = validation_data['Close'].iloc[0]
        end_price = validation_data['Close'].iloc[-1]
        price_change = end_price - start_price
        price_change_pct = (price_change / start_price) * 100
        
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
            price_volatility = validation_data['Close'].std() / validation_data['Close'].mean() * 100
            if abs(price_change_pct) < 5:  # 小于5%的波动
                is_correct = True
                correctness_reason = f"持有信号正确：价格波动较小 ({price_change_pct:.2f}%)，波动率{price_volatility:.2f}%"
            else:
                correctness_reason = f"持有信号错误：价格波动较大 ({price_change_pct:.2f}%)，波动率{price_volatility:.2f}%"
        
        # 计算潜在收益/损失
        if signal == 'buy':
            potential_return = price_change_pct
            potential_return_type = '收益' if price_change_pct > 0 else '损失'
        elif signal == 'sell':
            potential_return = -price_change_pct  # 卖出信号正确时，价格下跌是收益
            potential_return_type = '收益' if price_change_pct < 0 else '损失'
        else:
            potential_return = 0
            potential_return_type = '中性'
        
        # 构建响应
        response = {
            "symbol": symbol,
            "strategy": "historical_simulation",
            "parameters": {
                "historical_days": historical_days,
                "recent_days": recent_days,
                "validation_days": validation_days,
                "period": period
            },
            "trade_signal": {
                "signal": signal,
                "signal_description": signal_description,
                "signal_strength": float(signal_strength),
                "ma_30_overall": float(ma_30_overall),
                "ma_10_recent": float(ma_10_recent),
                "decision_date": historical_data['date'].iloc[-1].strftime('%Y-%m-%d') if not historical_data.empty else None
            },
            "validation": {
                "status": "completed",
                "is_correct": is_correct,
                "correctness_reason": correctness_reason,
                "validation_period": {
                    "start_date": validation_data['date'].iloc[0].strftime('%Y-%m-%d') if not validation_data.empty else None,
                    "end_date": validation_data['date'].iloc[-1].strftime('%Y-%m-%d') if not validation_data.empty else None,
                    "days": len(validation_data)
                },
                "price_stats": {
                    "start_price": float(start_price),
                    "end_price": float(end_price),
                    "price_change": float(price_change),
                    "price_change_pct": float(price_change_pct),
                    "max_price": float(validation_data['Close'].max()),
                    "min_price": float(validation_data['Close'].min()),
                    "avg_price": float(validation_data['Close'].mean()),
                    "volatility_pct": float(validation_data['Close'].std() / validation_data['Close'].mean() * 100)
                }
            },
            "performance": {
                "potential_return_pct": float(potential_return),
                "potential_return_type": potential_return_type,
                "signal_accuracy": "正确" if is_correct else "错误",
                "confidence_score": min(abs(signal_strength) / 10, 100)
            },
            "data_summary": {
                "total_data_days": len(data),
                "historical_period": historical_days,
                "validation_period": validation_days,
                "simulation_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"历史数据模拟交易失败: {str(e)}")

# 系统信息端点
@app.get("/api/v1/system/info")
async def system_info():
    """获取系统信息"""
    return {
        "service": "量化交易系统",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "features": [
            "股票数据获取",
            "双均线策略",
            "简单回测",
            "历史数据模拟交易",
            "REST API接口"
        ],
        "supported_symbols": ["SPY", "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META"],
        "default_parameters": {
            "fast_period": 10,
            "slow_period": 30,
            "initial_capital": 10000
        }
    }

# 导入图表模块
try:
    from charts import chart_generator
    CHARTS_ENABLED = True
except ImportError:
    CHARTS_ENABLED = False
    print("警告: 图表模块未找到，图表功能将不可用")

# 图表端点
@app.get("/api/v1/charts/price")
async def get_price_chart(
    symbol: str = Query("AAPL", description="股票代码"),
    period: str = Query("1mo", description="时间周期: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max"),
    interval: str = Query("1d", description="数据间隔: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo")
):
    """获取价格走势图表"""
    if not CHARTS_ENABLED:
        raise HTTPException(status_code=501, detail="图表功能未启用")
    
    try:
        result = chart_generator.generate_price_chart(symbol, period, interval)
        if result:
            return result
        else:
            raise HTTPException(status_code=404, detail="无法生成价格图表")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成价格图表失败: {str(e)}")

@app.get("/api/v1/charts/strategy")
async def get_strategy_chart(
    symbol: str = Query("SPY", description="股票代码"),
    fast_period: int = Query(10, description="快线周期"),
    slow_period: int = Query(30, description="慢线周期"),
    period: str = Query("3mo", description="时间周期")
):
    """获取策略图表（双均线交叉）"""
    if not CHARTS_ENABLED:
        raise HTTPException(status_code=501, detail="图表功能未启用")
    
    try:
        result = chart_generator.generate_strategy_chart(symbol, fast_period, slow_period, period)
        if result:
            return result
        else:
            raise HTTPException(status_code=404, detail="无法生成策略图表")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成策略图表失败: {str(e)}")

@app.get("/api/v1/charts/backtest")
async def get_backtest_chart(
    symbol: str = Query("AAPL", description="股票代码"),
    initial_capital: float = Query(10000, description="初始资金"),
    period: str = Query("6mo", description="时间周期")
):
    """获取回测结果图表"""
    if not CHARTS_ENABLED:
        raise HTTPException(status_code=501, detail="图表功能未启用")
    
    try:
        result = chart_generator.generate_backtest_chart(symbol, initial_capital, period)
        if result:
            return result
        else:
            raise HTTPException(status_code=404, detail="无法生成回测图表")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成回测图表失败: {str(e)}")

@app.get("/api/v1/charts/available")
async def get_available_charts():
    """获取可用的图表类型"""
    return {
        "charts_enabled": CHARTS_ENABLED,
        "available_charts": [
            {
                "name": "价格走势图",
                "endpoint": "/api/v1/charts/price",
                "description": "显示股票价格和成交量走势",
                "parameters": {
                    "symbol": "股票代码 (如 AAPL, SPY)",
                    "period": "时间周期 (1mo, 3mo, 6mo, 1y)",
                    "interval": "数据间隔 (1d)"
                }
            },
            {
                "name": "策略图表",
                "endpoint": "/api/v1/charts/strategy",
                "description": "显示双均线交叉策略信号",
                "parameters": {
                    "symbol": "股票代码",
                    "fast_period": "快线周期 (默认10)",
                    "slow_period": "慢线周期 (默认30)",
                    "period": "时间周期"
                }
            },
            {
                "name": "回测图表",
                "endpoint": "/api/v1/charts/backtest",
                "description": "显示策略回测结果和收益对比",
                "parameters": {
                    "symbol": "股票代码",
                    "initial_capital": "初始资金 (默认10000)",
                    "period": "时间周期"
                }
            }
        ]
    }

# 根端点
@app.get("/")
async def root():
    """根端点"""
    endpoints = {
        "data": "/api/v1/data/{symbol}",
        "strategy": "/api/v1/strategy/moving_average",
        "backtest": "/api/v1/backtest/simple",
        "simulation": "/api/v1/simulation/historical",
        "system_info": "/api/v1/system/info"
    }
    
    if CHARTS_ENABLED:
        endpoints["charts"] = "/api/v1/charts/available"
    
    return {
        "message": "欢迎使用量化交易系统API",
        "documentation": "/docs",
        "health_check": "/health",
        "endpoints": endpoints
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")