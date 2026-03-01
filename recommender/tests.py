"""
Recommender 模块测试入口

运行方式:
    # 运行所有测试
    python -m pytest tests/test_recommender/ -v
    
    # 运行特定测试文件
    python -m pytest tests/test_recommender/test_models.py -v
    
    # 运行特定测试用例
    python -m pytest tests/test_recommender/test_models.py::TestStockRecommendation::test_full_creation -v
    
    # 生成覆盖率报告
    python -m pytest tests/test_recommender/ --cov=recommender --cov-report=html

手动测试（需要真实数据库连接）:
    python recommender/tests.py manual
"""

import sys


def run_manual_tests():
    """手动测试（无需 mock，需要真实数据库连接）"""
    from recommender.stock_scanner import (
        get_all_stocks,
        get_all_symbols,
        get_stock_count,
        get_market_distribution,
        get_industries,
    )
    
    print("\n" + "="*60)
    print("Recommender 模块手动测试")
    print("="*60)
    
    try:
        # 测试股票扫描器
        print("\n1. 测试 get_all_symbols()")
        symbols = get_all_symbols()
        print(f"   获取到 {len(symbols)} 个股票代码")
        if symbols:
            print(f"   前5个: {symbols[:5]}")
        
        print("\n2. 测试 get_all_stocks()")
        stocks = get_all_stocks(fields=['symbol', 'name', 'industry'])
        print(f"   获取到 {len(stocks)} 只股票详细信息")
        if stocks:
            print(f"   第一只: {stocks[0]}")
        
        print("\n3. 测试 get_stock_count()")
        count = get_stock_count()
        print(f"   股票总数: {count}")
        
        print("\n4. 测试 get_market_distribution()")
        dist = get_market_distribution()
        print(f"   市场分布: {dist}")
        
        print("\n5. 测试 get_industries()")
        industries = get_industries()
        print(f"   行业数量: {len(industries)}")
        if industries:
            print(f"   前5个: {industries[:5]}")
        
        print("\n" + "="*60)
        print("✅ 所有手动测试通过！")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'manual':
        run_manual_tests()
    else:
        print(__doc__)
        print("\n提示: 使用 'manual' 参数运行手动测试")
        print("示例: python recommender/tests.py manual")
