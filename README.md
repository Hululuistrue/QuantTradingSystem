# Quant Trading System

AI量化交易系统 - 支持多种交易策略的完整解决方案

## 🚀 系统特性

### 核心功能
- **5种交易策略**: 双均线交叉、RSI、MACD、布林带、历史数据模拟
- **实时数据获取**: 支持SPY、AAPL等8个美股，使用yfinance数据源
- **完整API**: RESTful API支持策略运行、回测、比较
- **Web界面**: 交互式交易界面，支持策略选择和参数调整
- **Docker部署**: 一键部署，包含数据库、缓存、监控

### 技术架构
- **后端**: FastAPI (Python 3.9+)
- **数据库**: PostgreSQL (TimescaleDB扩展)
- **缓存**: Redis
- **前端**: HTML5 + JavaScript + Chart.js
- **部署**: Docker Compose
- **监控**: Prometheus + Grafana

## 📊 系统状态

### 访问地址
- **Web界面**: http://76.13.108.193:8051/
- **API文档**: http://76.13.108.193:8001/docs
- **健康检查**: http://76.13.108.193:8001/health

### 当前部署
- **VPS地址**: 76.13.108.193
- **部署时间**: 2026-02-05
- **状态**: ✅ 正常运行中

## 🛠️ 快速开始

### 本地开发
```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/QuantTradingSystem.git
cd QuantTradingSystem

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行测试
python test_simple.py

# 4. 启动API服务
uvicorn api_simple_docker:app --host 0.0.0.0 --port 8000 --reload
```

### Docker部署
```bash
# 1. 使用简单版本
docker-compose -f docker-compose.simple.yml up -d

# 2. 使用多策略版本
docker-compose -f docker-compose.multistrategy.yml up -d

# 3. 查看服务状态
docker-compose ps
```

## 📈 交易策略

### 1. 双均线交叉策略 (Moving Average Crossover)
- **原理**: 短期均线上穿长期均线时买入，下穿时卖出
- **参数**: 快线周期(默认10天)、慢线周期(默认30天)

### 2. RSI策略 (Relative Strength Index)
- **原理**: RSI指标超卖时买入，超买时卖出
- **参数**: RSI周期(默认14天)、超卖阈值(默认30)、超买阈值(默认70)

### 3. MACD策略 (Moving Average Convergence Divergence)
- **原理**: MACD线上穿信号线时买入，下穿时卖出
- **参数**: 快线周期(默认12天)、慢线周期(默认26天)、信号线周期(默认9天)

### 4. 布林带策略 (Bollinger Bands)
- **原理**: 价格触及下轨时买入，触及上轨时卖出
- **参数**: 移动平均周期(默认20天)、标准差倍数(默认2)

### 5. 历史数据模拟策略
- **原理**: 对比历史区间均线和近期均线，预测未来走势
- **参数**: 历史天数、近期天数、验证天数

## 🔧 API接口

### 核心端点
- `GET /health` - 系统健康检查
- `GET /api/v1/data/{symbol}` - 获取股票数据
- `POST /api/v1/strategy/run` - 运行策略生成信号
- `POST /api/v1/strategy/backtest` - 回测策略性能
- `POST /api/v1/strategies/compare` - 比较多个策略
- `GET /api/v1/simulation/historical` - 历史数据模拟交易

### 示例请求
```bash
# 获取SPY数据
curl "http://localhost:8000/api/v1/data/SPY?days=30"

# 运行双均线策略
curl -X POST "http://localhost:8000/api/v1/strategy/run" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"SPY","strategy":"moving_average","fast_period":10,"slow_period":30}'
```

## 🖥️ Web界面功能

### 主要功能
1. **策略选择器**: 动态切换4种交易策略
2. **三个核心按钮**:
   - **Run Strategy**: 运行策略生成交易信号
   - **Run Backtest**: 回测策略历史表现
   - **Compare Strategies**: 比较所有策略性能
3. **参数调整**: 每个策略可自定义参数
4. **结果展示**: 信号、摘要、指标、原始数据
5. **股票选择**: 支持8个热门美股

### 界面特点
- 响应式设计，支持移动端
- 实时数据更新
- 图表可视化
- 错误处理和加载状态

## 📁 项目结构

```
QuantTradingSystem/
├── api/                    # API相关代码
├── strategies/            # 交易策略实现
│   ├── base_strategy.py   # 策略基类
│   ├── moving_average.py  # 双均线策略
│   ├── rsi_strategy.py    # RSI策略
│   ├── macd_strategy.py   # MACD策略
│   ├── bollinger_bands_strategy.py  # 布林带策略
│   ├── historical_simulation.py      # 历史模拟策略
│   └── strategy_manager.py # 策略管理器
├── data/                  # 数据获取模块
├── web/                   # Web界面文件
├── docker/                # Docker配置文件
├── docs/                  # 文档
├── monitoring/            # 监控配置
├── backtest/              # 回测模块
├── api_multistrategy.py   # 多策略API
├── api_simple_docker.py   # 简单API
├── docker-compose.yml     # Docker Compose配置
├── requirements.txt       # Python依赖
└── README.md             # 项目说明
```

## 🔍 监控和日志

### 健康检查
系统提供完整的健康检查端点，监控以下组件：
- PostgreSQL数据库连接
- Redis缓存服务
- yfinance数据源可用性
- 策略管理器状态

### 日志系统
- API访问日志
- 策略运行日志
- 错误日志
- 性能监控日志

## 🚨 故障排除

### 常见问题
1. **API无法访问**: 检查端口是否被占用，服务是否启动
2. **数据获取失败**: 检查网络连接，yfinance API状态
3. **策略运行错误**: 检查参数设置，数据完整性
4. **Docker启动失败**: 检查端口冲突，资源限制

### 调试方法
```bash
# 查看服务日志
docker-compose logs -f

# 检查API状态
curl http://localhost:8000/health

# 测试数据获取
python -c "import yfinance as yf; print(yf.download('SPY', period='1mo'))"
```

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📞 联系方式

如有问题，请通过GitHub Issues提交。

---

**最后更新**: 2026-02-24
**版本**: 2.0.0
**状态**: ✅ 生产环境运行中
