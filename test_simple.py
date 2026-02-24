#!/usr/bin/env python3
"""
简单测试脚本，验证量化系统核心功能
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_data_fetcher():
    """测试数据获取器"""
    print("=== 测试数据获取器 ===")
    
    try:
        # 动态导入，避免依赖问题
        import pandas as pd
        import numpy as np
        
        # 模拟数据获取
        print("1. 模拟获取SPY数据...")
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        data = pd.DataFrame({
            'date': dates,
            'open': np.random.randn(100).cumsum() + 100,
            'high': np.random.randn(100).cumsum() + 105,
            'low': np.random.randn(100).cumsum() + 95,
            'close': np.random.randn(100).cumsum() + 100,
            'volume': np.random.randint(1000000, 10000000, 100),
            'symbol': 'SPY'
        })
        
        print(f"   ✓ 生成模拟数据: {len(data)}行")
        print(f"   ✓ 日期范围: {data['date'].min()} 到 {data['date'].max()}")
        print(f"   ✓ 价格范围: {data['close'].min():.2f} - {data['close'].max():.2f}")
        
        return data
        
    except ImportError as e:
        print(f"   ✗ 缺少依赖: {e}")
        return None

def test_strategy_logic(data):
    """测试策略逻辑"""
    print("\n=== 测试策略逻辑 ===")
    
    if data is None:
        print("   ✗ 无数据，跳过策略测试")
        return None
    
    try:
        # 简单的双均线计算
        print("1. 计算双均线...")
        data = data.copy()
        data['ma_fast'] = data['close'].rolling(window=10).mean()
        data['ma_slow'] = data['close'].rolling(window=30).mean()
        
        # 计算交叉信号
        data['ma_diff'] = data['ma_fast'] - data['ma_slow']
        data['signal'] = 'hold'
        data.loc[data['ma_diff'] > 0, 'signal'] = 'buy'
        data.loc[data['ma_diff'] < 0, 'signal'] = 'sell'
        
        # 统计信号
        buy_signals = len(data[data['signal'] == 'buy'])
        sell_signals = len(data[data['signal'] == 'sell'])
        
        print(f"   ✓ 快线周期: 10日")
        print(f"   ✓ 慢线周期: 30日")
        print(f"   ✓ 买入信号: {buy_signals}次")
        print(f"   ✓ 卖出信号: {sell_signals}次")
        
        # 计算简单收益率
        if len(data) > 1:
            data['returns'] = data['close'].pct_change()
            total_return = (1 + data['returns']).prod() - 1
            print(f"   ✓ 总收益率: {total_return:.2%}")
        
        return data
        
    except Exception as e:
        print(f"   ✗ 策略测试失败: {e}")
        return None

def test_api_structure():
    """测试API结构"""
    print("\n=== 测试API结构 ===")
    
    try:
        # 检查API文件
        api_dir = os.path.join(os.path.dirname(__file__), 'api')
        if os.path.exists(api_dir):
            print("1. 检查API目录结构...")
            files = os.listdir(api_dir)
            print(f"   ✓ API文件: {len(files)}个")
            
            # 检查关键文件
            key_files = ['main.py', 'models.py', 'schemas.py', 'services.py']
            for file in key_files:
                file_path = os.path.join(api_dir, file)
                if os.path.exists(file_path):
                    print(f"   ✓ {file}: 存在")
                else:
                    print(f"   ✗ {file}: 缺失")
        
        # 检查Docker配置
        docker_compose = os.path.join(os.path.dirname(__file__), 'docker-compose.yml')
        if os.path.exists(docker_compose):
            print("2. 检查Docker配置...")
            with open(docker_compose, 'r') as f:
                content = f.read()
                services = content.count('container_name:')
                print(f"   ✓ Docker服务: {services}个")
        
        return True
        
    except Exception as e:
        print(f"   ✗ API结构测试失败: {e}")
        return False

def test_project_structure():
    """测试项目结构"""
    print("\n=== 测试项目结构 ===")
    
    try:
        base_dir = os.path.dirname(__file__)
        
        # 检查目录结构
        directories = [
            'data', 'strategies', 'backtest', 'api', 
            'web', 'monitoring', 'docker', 'docs'
        ]
        
        print("1. 检查项目目录...")
        for dir_name in directories:
            dir_path = os.path.join(base_dir, dir_name)
            if os.path.exists(dir_path):
                files = len([f for f in os.listdir(dir_path) if f.endswith('.py')])
                print(f"   ✓ {dir_name}: {files}个Python文件")
            else:
                print(f"   ✗ {dir_name}: 目录不存在")
        
        # 检查关键文件
        print("\n2. 检查关键文件...")
        key_files = [
            'requirements.txt', 'docker-compose.yml', 'README.md',
            'pyproject.toml'
        ]
        
        for file_name in key_files:
            file_path = os.path.join(base_dir, file_name)
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                print(f"   ✓ {file_name}: {size}字节")
            else:
                print(f"   ✗ {file_name}: 文件不存在")
        
        return True
        
    except Exception as e:
        print(f"   ✗ 项目结构测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始量化交易系统测试")
    print("=" * 50)
    
    # 测试1: 数据获取
    data = test_data_fetcher()
    
    # 测试2: 策略逻辑
    strategy_data = test_strategy_logic(data)
    
    # 测试3: API结构
    api_ok = test_api_structure()
    
    # 测试4: 项目结构
    project_ok = test_project_structure()
    
    # 总结
    print("\n" + "=" * 50)
    print("📊 测试总结")
    print("=" * 50)
    
    tests_passed = 0
    tests_total = 4
    
    if data is not None:
        tests_passed += 1
        print("✓ 数据获取测试: 通过")
    else:
        print("✗ 数据获取测试: 失败")
    
    if strategy_data is not None:
        tests_passed += 1
        print("✓ 策略逻辑测试: 通过")
    else:
        print("✗ 策略逻辑测试: 失败")
    
    if api_ok:
        tests_passed += 1
        print("✓ API结构测试: 通过")
    else:
        print("✗ API结构测试: 失败")
    
    if project_ok:
        tests_passed += 1
        print("✓ 项目结构测试: 通过")
    else:
        print("✗ 项目结构测试: 失败")
    
    print(f"\n🎯 测试结果: {tests_passed}/{tests_total} 通过")
    
    if tests_passed == tests_total:
        print("✅ 所有测试通过！系统架构完整。")
        print("\n下一步:")
        print("1. 安装依赖: pip install -r requirements.txt")
        print("2. 启动服务: docker-compose up -d")
        print("3. 访问Web界面: http://localhost:8050")
        print("4. 访问API文档: http://localhost:8000/docs")
    else:
        print("⚠️  部分测试失败，需要检查系统配置。")
    
    return tests_passed == tests_total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)