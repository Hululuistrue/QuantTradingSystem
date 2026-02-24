// Multi-Strategy Trading Functions
// ============================================

// Strategy parameter configurations
const strategyParamConfigs = {
    moving_average: [
        { id: 'fast_period', label: 'Fast Period (days)', type: 'number', value: 10, min: 5, max: 50 },
        { id: 'slow_period', label: 'Slow Period (days)', type: 'number', value: 30, min: 20, max: 100 }
    ],
    rsi: [
        { id: 'period', label: 'RSI Period (days)', type: 'number', value: 14, min: 7, max: 30 },
        { id: 'oversold', label: 'Oversold Level', type: 'number', value: 30, min: 10, max: 40 },
        { id: 'overbought', label: 'Overbought Level', type: 'number', value: 70, min: 60, max: 90 }
    ],
    macd: [
        { id: 'fast_period', label: 'Fast EMA Period', type: 'number', value: 12, min: 5, max: 20 },
        { id: 'slow_period', label: 'Slow EMA Period', type: 'number', value: 26, min: 20, max: 40 },
        { id: 'signal_period', label: 'Signal Period', type: 'number', value: 9, min: 5, max: 15 }
    ],
    bollinger_bands: [
        { id: 'period', label: 'BB Period (days)', type: 'number', value: 20, min: 10, max: 50 },
        { id: 'std_dev', label: 'Standard Deviations', type: 'number', value: 2, min: 1, max: 3, step: 0.1 }
    ]
};

// Update strategy parameters when strategy changes
function updateStrategyParams() {
    const strategySelect = document.getElementById('strategy-select');
    const strategy = strategySelect.value;
    const paramsContainer = document.getElementById('strategy-params');

    // Clear existing parameters
    paramsContainer.innerHTML = '';

    // Add new parameters
    const params = strategyParamConfigs[strategy] || [];
    params.forEach(param => {
        const paramDiv = document.createElement('div');
        paramDiv.className = 'control-group';
        paramDiv.innerHTML = `
            <label for="${param.id}"><i class="fas fa-sliders-h"></i> ${param.label}:</label>
            <input type="${param.type}" id="${param.id}" value="${param.value}"
                   min="${param.min || ''}" max="${param.max || ''}" step="${param.step || 1}"
                   style="width: 100%; padding: 10px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); background: rgba(0,0,0,0.3); color: white;">
        `;
        paramsContainer.appendChild(paramDiv);
    });
}

// Get current strategy parameters
function getStrategyParams() {
    const strategy = document.getElementById('strategy-select').value;
    const params = {};

    const paramConfigs = strategyParamConfigs[strategy] || [];
    paramConfigs.forEach(param => {
        const input = document.getElementById(param.id);
        if (input) {
            params[param.id] = input.type === 'number' ? parseFloat(input.value) : input.value;
        }
    });

    return params;
}

// Run strategy function
async function runStrategy() {
    const strategy = document.getElementById('strategy-select').value;
    const symbol = document.getElementById('strategy-symbol').value;
    const period = document.getElementById('strategy-period').value;
    const params = getStrategyParams();

    const resultDiv = document.getElementById('strategy-result');
    const signalDisplay = document.getElementById('strategy-signal-display');
    const summaryDisplay = document.getElementById('strategy-summary-display');
    const metricsDisplay = document.getElementById('performance-metrics-display');
    const rawData = document.getElementById('strategy-raw-data');

    // Show loading state
    resultDiv.style.display = 'block';
    signalDisplay.innerHTML = '<p style="text-align: center;"><i class="fas fa-spinner fa-spin"></i> Running strategy...</p>';
    summaryDisplay.innerHTML = '';
    metricsDisplay.innerHTML = '';
    if (rawData) rawData.textContent = 'Loading...';

    try {
        // Build API URL with query parameters
        const baseUrl = 'http://76.13.108.193:8001';
        const endpoint = '/api/v1/strategy/run';

        // Build query string
        const queryParams = new URLSearchParams({
            symbol: symbol,
            strategy_id: strategy,
            period: period,
            ...params  // Add strategy-specific parameters
        });

        // Make API call with GET request
        const response = await fetch(`${baseUrl}${endpoint}?${queryParams.toString()}`, {
            method: 'GET'
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();

        // Display raw data
        if (rawData) rawData.textContent = JSON.stringify(data, null, 2);

        // Normalize API response (multistrategy schema)
        const latest = data.latest_signal || {};
        const signal = latest.signal || 'hold';
        const signalDescription = latest.signal_description || data.signal_description || 'No description available';
        const signalStrength = latest.signal_strength ?? data.signal_strength ?? null;
        const confidence = data.confidence ?? null;

        // Display signal
        let signalClass = 'signal-hold';
        let signalIcon = 'fas fa-pause-circle';
        if (signal === 'buy') {
            signalClass = 'signal-buy';
            signalIcon = 'fas fa-arrow-up';
        } else if (signal === 'sell') {
            signalClass = 'signal-sell';
            signalIcon = 'fas fa-arrow-down';
        }

        signalDisplay.innerHTML = `
            <div style="text-align: center; margin-bottom: 20px;">
                <div class="${signalClass}" style="font-size: 2rem; margin-bottom: 10px;">
                    <i class="${signalIcon}"></i> ${signal.toUpperCase()} SIGNAL
                </div>
                <p style="font-size: 1.1rem; margin-bottom: 10px;">${signalDescription}</p>
                <div style="display: flex; justify-content: center; gap: 30px; margin-top: 20px; flex-wrap: wrap;">
                    <div class="metric-item">
                        <div class="metric-label">Strategy</div>
                        <div class="metric-value">${strategy.replace(/_/g, ' ').toUpperCase()}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Symbol</div>
                        <div class="metric-value">${symbol}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Confidence</div>
                        <div class="metric-value">${confidence !== null ? Number(confidence).toFixed(2) + '%' : 'N/A'}</div>
                    </div>
                </div>
            </div>
        `;

        // Display strategy summary
        summaryDisplay.innerHTML = `
            <div class="metric-grid">
                <div class="metric-item">
                    <div class="metric-label">Current Price</div>
                    <div class="metric-value">N/A</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Signal Strength</div>
                    <div class="metric-value">${signalStrength !== null ? Number(signalStrength).toFixed(2) + '%' : 'N/A'}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Data Points</div>
                    <div class="metric-value">${data.data_points || 'N/A'}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Period</div>
                    <div class="metric-value">${period}</div>
                </div>
            </div>
        `;

        // Display performance metrics
        metricsDisplay.innerHTML = `
            <div class="metric-grid">
                <div class="metric-item">
                    <div class="metric-label">Parameters Used</div>
                    <div class="metric-value" style="font-size: 0.9rem;">${JSON.stringify(params)}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Timestamp</div>
                    <div class="metric-value">${new Date().toLocaleString()}</div>
                </div>
            </div>
        `;

    } catch (error) {
        signalDisplay.innerHTML = `
            <p class="signal-incorrect" style="text-align: center;">
                <i class="fas fa-exclamation-triangle"></i> Error: ${error.message}
            </p>
            <p style="text-align: center; margin-top: 10px; opacity: 0.8;">
                Please ensure the multi-strategy API is deployed and running.
            </p>
        `;
        if (rawData) rawData.textContent = `Error: ${error.message}`;
    }
}

// Run strategy backtest function
async function runStrategyBacktest() {
    const strategy = document.getElementById('strategy-select').value;
    const symbol = document.getElementById('strategy-symbol').value;
    const period = document.getElementById('strategy-period').value;
    const params = getStrategyParams();

    const resultDiv = document.getElementById('strategy-result');
    const signalDisplay = document.getElementById('strategy-signal-display');
    const summaryDisplay = document.getElementById('strategy-summary-display');
    const metricsDisplay = document.getElementById('performance-metrics-display');
    const rawData = document.getElementById('strategy-raw-data');

    // Show loading state
    resultDiv.style.display = 'block';
    signalDisplay.innerHTML = '<p style="text-align: center;"><i class="fas fa-spinner fa-spin"></i> Running backtest...</p>';
    summaryDisplay.innerHTML = '';
    metricsDisplay.innerHTML = '';
    if (rawData) rawData.textContent = 'Loading...';

    try {
        // Build API URL with query parameters
        const baseUrl = 'http://76.13.108.193:8001';
        const endpoint = '/api/v1/strategy/backtest';

        // Build query string
        const queryParams = new URLSearchParams({
            symbol: symbol,
            strategy_id: strategy,
            period: period,
            ...params  // Add strategy-specific parameters
        });

        // Make API call with GET request
        const response = await fetch(`${baseUrl}${endpoint}?${queryParams.toString()}`, {
            method: 'GET'
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();

        // Display raw data
        if (rawData) rawData.textContent = JSON.stringify(data, null, 2);

        // Display backtest results
        const totalReturn = data.total_return || 0;
        signalDisplay.innerHTML = `
            <div style="text-align: center; margin-bottom: 20px;">
                <div class="${totalReturn > 0 ? 'signal-buy' : 'signal-sell'}" style="font-size: 2rem; margin-bottom: 10px;">
                    <i class="fas fa-${totalReturn > 0 ? 'chart-line' : 'chart-line-down'}"></i>
                    ${totalReturn > 0 ? 'PROFITABLE' : 'LOSS'} BACKTEST
                </div>
                <p style="font-size: 1.1rem; margin-bottom: 10px;">${strategy.replace(/_/g, ' ').toUpperCase()} Strategy Backtest Results</p>
                <div style="display: flex; justify-content: center; gap: 30px; margin-top: 20px; flex-wrap: wrap;">
                    <div class="metric-item">
                        <div class="metric-label">Total Return</div>
                        <div class="metric-value ${totalReturn > 0 ? 'signal-correct' : 'signal-incorrect'}">
                            ${totalReturn > 0 ? '+' : ''}${totalReturn.toFixed(2)}%
                        </div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Win Rate</div>
                        <div class="metric-value">${data.win_rate ? data.win_rate.toFixed(2) + '%' : 'N/A'}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Total Trades</div>
                        <div class="metric-value">${data.total_trades || 0}</div>
                    </div>
                </div>
            </div>
        `;

        // Display strategy summary
        summaryDisplay.innerHTML = `
            <div class="metric-grid">
                <div class="metric-item">
                    <div class="metric-label">Sharpe Ratio</div>
                    <div class="metric-value">${data.sharpe_ratio ? data.sharpe_ratio.toFixed(3) : 'N/A'}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Max Drawdown</div>
                    <div class="metric-value ${(data.max_drawdown || 0) < -10 ? 'signal-incorrect' : ''}">
                        ${data.max_drawdown ? data.max_drawdown.toFixed(2) + '%' : 'N/A'}
                    </div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Avg Win</div>
                    <div class="metric-value">${data.avg_win ? data.avg_win.toFixed(2) + '%' : 'N/A'}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Avg Loss</div>
                    <div class="metric-value">${data.avg_loss ? data.avg_loss.toFixed(2) + '%' : 'N/A'}</div>
                </div>
            </div>
        `;

        // Display performance metrics
        metricsDisplay.innerHTML = `
            <div class="metric-grid">
                <div class="metric-item">
                    <div class="metric-label">Strategy</div>
                    <div class="metric-value">${strategy.replace(/_/g, ' ')}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Symbol</div>
                    <div class="metric-value">${symbol}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Period</div>
                    <div class="metric-value">${period}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Profit Factor</div>
                    <div class="metric-value">${data.profit_factor ? data.profit_factor.toFixed(2) : 'N/A'}</div>
                </div>
            </div>
        `;

    } catch (error) {
        signalDisplay.innerHTML = `
            <p class="signal-incorrect" style="text-align: center;">
                <i class="fas fa-exclamation-triangle"></i> Error: ${error.message}
            </p>
            <p style="text-align: center; margin-top: 10px; opacity: 0.8;">
                Please ensure the multi-strategy API is deployed and running.
            </p>
        `;
        if (rawData) rawData.textContent = `Error: ${error.message}`;
    }
}

// Compare strategies function
async function compareStrategies() {
    const symbol = document.getElementById('strategy-symbol').value;
    const period = document.getElementById('strategy-period').value;

    const resultDiv = document.getElementById('strategy-result');
    const signalDisplay = document.getElementById('strategy-signal-display');
    const summaryDisplay = document.getElementById('strategy-summary-display');
    const metricsDisplay = document.getElementById('performance-metrics-display');
    const rawData = document.getElementById('strategy-raw-data');

    // Show loading state
    resultDiv.style.display = 'block';
    signalDisplay.innerHTML = '<p style="text-align: center;"><i class="fas fa-spinner fa-spin"></i> Comparing strategies...</p>';
    summaryDisplay.innerHTML = '';
    metricsDisplay.innerHTML = '';
    if (rawData) rawData.textContent = 'Loading...';

    try {
        // Build API URL with query parameters
        const baseUrl = 'http://76.13.108.193:8001';
        const endpoint = '/api/v1/strategies/compare';

        // Build query string
        const queryParams = new URLSearchParams({
            symbol: symbol,
            period: period
        });

        // Make API call with GET request
        const response = await fetch(`${baseUrl}${endpoint}?${queryParams.toString()}`, {
            method: 'GET'
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();

        // Display raw data
        if (rawData) rawData.textContent = JSON.stringify(data, null, 2);

        // Find best performing strategy
        let bestStrategy = null;
        let bestReturn = -Infinity;

        const comparisonList = data.comparison || data.strategies || [];
        if (comparisonList.length > 0) {
            comparisonList.forEach(strategy => {
                const tr = Number(strategy.total_return);
                if (!Number.isNaN(tr) && tr > bestReturn) {
                    bestReturn = tr;
                    bestStrategy = strategy;
                }
            });
        }

        // Display comparison results
        signalDisplay.innerHTML = `
            <div style="text-align: center; margin-bottom: 20px;">
                <div class="${bestReturn > 0 ? 'signal-buy' : 'signal-sell'}" style="font-size: 2rem; margin-bottom: 10px;">
                    <i class="fas fa-balance-scale"></i> STRATEGY COMPARISON
                </div>
                <p style="font-size: 1.1rem; margin-bottom: 10px;">
                    Best Strategy: <strong>${bestStrategy ? (bestStrategy.strategy || bestStrategy.strategy_id || bestStrategy.strategy_name || 'N/A').toString().replace(/_/g, ' ').toUpperCase() : 'N/A'}</strong>
                </p>
                <div style="display: flex; justify-content: center; gap: 30px; margin-top: 20px; flex-wrap: wrap;">
                    <div class="metric-item">
                        <div class="metric-label">Best Return</div>
                        <div class="metric-value ${bestReturn > 0 ? 'signal-correct' : 'signal-incorrect'}">
                            ${bestReturn > 0 ? '+' : ''}${bestReturn.toFixed(2)}%
                        </div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Strategies Compared</div>
                        <div class="metric-value">${comparisonList.length}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Symbol</div>
                        <div class="metric-value">${symbol}</div>
                    </div>
                </div>
            </div>
        `;

        // Display strategy comparison table
        let comparisonHTML = '<div style="overflow-x: auto;"><table style="width: 100%; border-collapse: collapse; margin-top: 20px;">';
        comparisonHTML += '<thead><tr style="background: rgba(255,255,255,0.1);">';
        comparisonHTML += '<th style="padding: 12px; text-align: left; border-bottom: 2px solid rgba(255,255,255,0.2);">Strategy</th>';
        comparisonHTML += '<th style="padding: 12px; text-align: right; border-bottom: 2px solid rgba(255,255,255,0.2);">Return</th>';
        comparisonHTML += '<th style="padding: 12px; text-align: right; border-bottom: 2px solid rgba(255,255,255,0.2);">Win Rate</th>';
        comparisonHTML += '<th style="padding: 12px; text-align: right; border-bottom: 2px solid rgba(255,255,255,0.2);">Sharpe</th>';
        comparisonHTML += '<th style="padding: 12px; text-align: right; border-bottom: 2px solid rgba(255,255,255,0.2);">Max DD</th>';
        comparisonHTML += '</tr></thead><tbody>';

        if (comparisonList.length > 0) {
            comparisonList.forEach((strategy, index) => {
                const isBest = strategy === bestStrategy;
                const rowStyle = isBest ? 'background: rgba(76, 175, 80, 0.2);' : index % 2 === 0 ? 'background: rgba(255,255,255,0.05);' : '';
                comparisonHTML += `<tr style="${rowStyle}">`;
                const name = (strategy.strategy || strategy.strategy_id || strategy.strategy_name || 'N/A').toString().replace(/_/g, ' ');
                comparisonHTML += `<td style="padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.1);">${name}${isBest ? ' 🏆' : ''}</td>`;
                comparisonHTML += `<td style="padding: 12px; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.1);" class="${strategy.total_return > 0 ? 'signal-correct' : 'signal-incorrect'}">${strategy.total_return > 0 ? '+' : ''}${strategy.total_return.toFixed(2)}%</td>`;
                comparisonHTML += `<td style="padding: 12px; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.1);">${strategy.win_rate ? strategy.win_rate.toFixed(2) + '%' : 'N/A'}</td>`;
                comparisonHTML += `<td style="padding: 12px; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.1);">${strategy.sharpe_ratio ? strategy.sharpe_ratio.toFixed(3) : 'N/A'}</td>`;
                comparisonHTML += `<td style="padding: 12px; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.1);">${strategy.max_drawdown ? strategy.max_drawdown.toFixed(2) + '%' : 'N/A'}</td>`;
                comparisonHTML += '</tr>';
            });
        }

        comparisonHTML += '</tbody></table></div>';

        summaryDisplay.innerHTML = comparisonHTML;
        metricsDisplay.innerHTML = `
            <div style="padding: 15px; background: rgba(255, 255, 255, 0.1); border-radius: 8px;">
                <p><i class="fas fa-info-circle"></i> <strong>Comparison Period:</strong> ${period}</p>
                <p style="margin-top: 10px; opacity: 0.9;">All strategies were backtested on ${symbol} for the same period with their default parameters.</p>
            </div>
        `;

    } catch (error) {
        signalDisplay.innerHTML = `
            <p class="signal-incorrect" style="text-align: center;">
                <i class="fas fa-exclamation-triangle"></i> Error: ${error.message}
            </p>
            <p style="text-align: center; margin-top: 10px; opacity: 0.8;">
                Please ensure the multi-strategy API is deployed and running.
            </p>
        `;
        if (rawData) rawData.textContent = `Error: ${error.message}`;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize strategy parameters for default selection
    updateStrategyParams();
});
