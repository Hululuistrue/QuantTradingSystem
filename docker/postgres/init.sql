-- 创建策略表
CREATE TABLE IF NOT EXISTS strategies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    parameters JSONB,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建交易记录表
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id),
    symbol VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL, -- buy/sell
    price DECIMAL(10, 2) NOT NULL,
    quantity INTEGER NOT NULL,
    total_value DECIMAL(12, 2) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- 创建性能指标表
CREATE TABLE IF NOT EXISTS performance (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id),
    date DATE NOT NULL,
    total_return DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(10, 4),
    win_rate DECIMAL(10, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX idx_strategies_symbol ON strategies(symbol);
CREATE INDEX idx_trades_strategy_id ON trades(strategy_id);
CREATE INDEX idx_trades_timestamp ON trades(timestamp);
CREATE INDEX idx_performance_strategy_date ON performance(strategy_id, date);

-- 创建超表（TimescaleDB特性）
SELECT create_hypertable('trades', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('performance', 'date', if_not_exists => TRUE);

-- 插入示例策略
INSERT INTO strategies (name, symbol, strategy_type, parameters) VALUES
('双均线策略-SPY', 'SPY', 'moving_average_crossover', '{"fast_period": 10, "slow_period": 30}'),
('双均线策略-AAPL', 'AAPL', 'moving_average_crossover', '{"fast_period": 10, "slow_period": 30}')
ON CONFLICT DO NOTHING;

