"""
量化交易系统API主模块
"""

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import uvicorn
import logging
from datetime import datetime, date
import os

from . import models, schemas, services
from .database import SessionLocal, engine
from .dependencies import get_db

# 创建数据库表
models.Base.metadata.create_all(bind=engine)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="美股量化交易系统API",
    description="提供量化策略管理、数据获取、回测等功能",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 依赖注入
def get_data_service():
    """获取数据服务"""
    return services.DataService()

def get_strategy_service():
    """获取策略服务"""
    return services.StrategyService()

def get_backtest_service():
    """获取回测服务"""
    return services.BacktestService()


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "欢迎使用美股量化交易系统API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "quant-trading-api"
    }


@app.get("/api/v1/data/{symbol}")
async def get_stock_data(
    symbol: str,
    start_date: Optional[str] = Query(None, description="开始日期，格式: YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式: YYYY-MM-DD"),
    period: str = Query("1y", description="数据周期"),
    data_service: services.DataService = Depends(get_data_service),
    db: SessionLocal = Depends(get_db)
):
    """获取股票数据"""
    try:
        data = await data_service.get_stock_data(
            db=db,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period=period
        )
        
        if data.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票 {symbol} 的数据")
        
        # 转换为字典列表
        records = data.to_dict(orient='records')
        
        return {
            "symbol": symbol,
            "count": len(records),
            "start_date": data['date'].min().strftime('%Y-%m-%d') if not data.empty else None,
            "end_date": data['date'].max().strftime('%Y-%m-%d') if not data.empty else None,
            "data": records
        }
        
    except Exception as e:
        logger.error(f"获取股票数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/data/{symbol}/info")
async def get_stock_info(
    symbol: str,
    data_service: services.DataService = Depends(get_data_service)
):
    """获取股票基本信息"""
    try:
        info = data_service.get_stock_info(symbol)
        
        if not info:
            raise HTTPException(status_code=404, detail=f"未找到股票 {symbol} 的信息")
        
        return info
        
    except Exception as e:
        logger.error(f"获取股票信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/strategies")
async def create_strategy(
    strategy_data: schemas.StrategyCreate,
    strategy_service: services.StrategyService = Depends(get_strategy_service),
    db: SessionLocal = Depends(get_db)
):
    """创建策略"""
    try:
        strategy = await strategy_service.create_strategy(db, strategy_data)
        
        return {
            "message": "策略创建成功",
            "strategy_id": strategy.id,
            "strategy_name": strategy.name,
            "status": strategy.status
        }
        
    except Exception as e:
        logger.error(f"创建策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/strategies")
async def list_strategies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    strategy_service: services.StrategyService = Depends(get_strategy_service),
    db: SessionLocal = Depends(get_db)
):
    """获取策略列表"""
    try:
        strategies, total = await strategy_service.list_strategies(
            db, skip=skip, limit=limit, status=status
        )
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "strategies": strategies
        }
        
    except Exception as e:
        logger.error(f"获取策略列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/strategies/{strategy_id}")
async def get_strategy(
    strategy_id: int,
    strategy_service: services.StrategyService = Depends(get_strategy_service),
    db: SessionLocal = Depends(get_db)
):
    """获取策略详情"""
    try:
        strategy = await strategy_service.get_strategy(db, strategy_id)
        
        if not strategy:
            raise HTTPException(status_code=404, detail=f"未找到ID为 {strategy_id} 的策略")
        
        return strategy
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/strategies/{strategy_id}/run")
async def run_strategy(
    strategy_id: int,
    run_data: schemas.StrategyRun,
    strategy_service: services.StrategyService = Depends(get_strategy_service),
    db: SessionLocal = Depends(get_db)
):
    """运行策略"""
    try:
        result = await strategy_service.run_strategy(db, strategy_id, run_data)
        
        return {
            "message": "策略运行成功",
            "strategy_id": strategy_id,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"运行策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/backtest")
async def run_backtest(
    backtest_data: schemas.BacktestCreate,
    backtest_service: services.BacktestService = Depends(get_backtest_service),
    db: SessionLocal = Depends(get_db)
):
    """运行回测"""
    try:
        result = await backtest_service.run_backtest(db, backtest_data)
        
        return {
            "message": "回测运行成功",
            "backtest_id": result.id,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"运行回测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/backtest/{backtest_id}")
async def get_backtest_result(
    backtest_id: int,
    backtest_service: services.BacktestService = Depends(get_backtest_service),
    db: SessionLocal = Depends(get_db)
):
    """获取回测结果"""
    try:
        result = await backtest_service.get_backtest_result(db, backtest_id)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"未找到ID为 {backtest_id} 的回测结果")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取回测结果失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/metrics")
async def get_system_metrics():
    """获取系统指标"""
    try:
        import psutil
        import os
        
        # 系统指标
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 进程指标
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        return {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_mb": memory.used / 1024 / 1024,
                "memory_total_mb": memory.total / 1024 / 1024,
                "disk_percent": disk.percent,
                "disk_used_gb": disk.used / 1024 / 1024 / 1024,
                "disk_total_gb": disk.total / 1024 / 1024 / 1024
            },
            "process": {
                "memory_mb": round(process_memory, 2),
                "cpu_percent": process.cpu_percent(),
                "threads": process.num_threads(),
                "connections": len(process.connections())
            }
        }
        
    except Exception as e:
        logger.error(f"获取系统指标失败: {e}")
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
        {"symbol": "META", "name": "Meta Platforms Inc.", "type": "Stock"},
        {"symbol": "BRK.B", "name": "Berkshire Hathaway Inc.", "type": "Stock"},
        {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "type": "Stock"},
        {"symbol": "V", "name": "Visa Inc.", "type": "Stock"},
        {"symbol": "JNJ", "name": "Johnson & Johnson", "type": "Stock"},
        {"symbol": "WMT", "name": "Walmart Inc.", "type": "Stock"},
        {"symbol": "PG", "name": "Procter & Gamble Co.", "type": "Stock"},
        {"symbol": "MA", "name": "Mastercard Incorporated", "type": "Stock"},
        {"symbol": "UNH", "name": "UnitedHealth Group Incorporated", "type": "Stock"},
        {"symbol": "HD", "name": "The Home Depot Inc.", "type": "Stock"},
        {"symbol": "BAC", "name": "Bank of America Corporation", "type": "Stock"},
        {"symbol": "DIS", "name": "The Walt Disney Company", "type": "Stock"}
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
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )