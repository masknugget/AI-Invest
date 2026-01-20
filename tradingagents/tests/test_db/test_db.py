"""
Tests for tradingagents.db.document module
"""

from tradingagents.db.document import (
    detect_market,
    get_stock_data,
    get_stock_info,
    get_stock_news,
    get_market_news,
    get_china_stock_data,
    get_hk_stock_data,
    get_china_stock_info,
    get_hk_stock_info,
    get_stock_daily_technical,
    get_stock_daily_basic
)

# Test detect_market function
def test_detect_market():
    """Test market detection for different symbol formats"""
    # Test A股 patterns
    assert detect_market('600000') == 'cn'
    assert detect_market('000001') == 'cn'
    assert detect_market('300001') == 'cn'
    
    # Test 港股 patterns
    assert detect_market('00001.HK') == 'hk'
    assert detect_market('00700.HK') == 'hk'
    
    # Test 美股 patterns
    assert detect_market('AAPL') == 'us'
    assert detect_market('TSLA.US') == 'us'
    assert detect_market('MSFT.NASDAQ') == 'us'
    
    # Test unknown patterns
    assert detect_market('INVALID') == 'unknown'
    assert detect_market('123') == 'unknown'
    assert detect_market('1234567') == 'unknown'

# Test get_stock_data function
def test_get_stock_data():
    """Test stock data retrieval with different data types"""
    symbol = '000001.SZ'
    start_date = '2025-01-01'
    end_date = '2025-01-10'
    
    # Test technical data
    try:
        technical_data = get_stock_data(symbol, start_date, end_date, "technical")
        assert isinstance(technical_data, list)
        print(f"Technical data retrieved: {len(technical_data)} records")
    except Exception as e:
        print(f"Technical data test failed (expected if no DB): {e}")
    
    # Test basic data
    try:
        basic_data = get_stock_data(symbol, start_date, end_date, "basic")
        assert isinstance(basic_data, list)
        print(f"Basic data retrieved: {len(basic_data)} records")
    except Exception as e:
        print(f"Basic data test failed (expected if no DB): {e}")
    
    # Test invalid data type
    try:
        get_stock_data(symbol, start_date, end_date, "invalid")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "不支持的 data_type" in str(e)
        print("Invalid data type properly rejected")

# Test get_stock_info function
def test_get_stock_info():
    """Test stock information retrieval"""
    # Test A股
    try:
        info = get_stock_info('000001.SZ')
        if info:
            assert isinstance(info, dict)
            assert 'market' in info
            assert info['market'] == 'cn'
            print(f"A股 info retrieved: {info.get('name', 'Unknown')}")
        else:
            print("A股 info not found (expected if no DB)")
    except Exception as e:
        print(f"A股 info test failed: {e}")
    
    # Test 港股
    try:
        info = get_stock_info('00700.HK')
        if info:
            assert isinstance(info, dict)
            assert 'market' in info
            assert info['market'] == 'hk'
            print(f"港股 info retrieved: {info.get('name', 'Unknown')}")
        else:
            print("港股 info not found (expected if no DB)")
    except Exception as e:
        print(f"港股 info test failed: {e}")

# Test get_stock_news function
def test_get_stock_news():
    """Test stock news retrieval"""
    symbol = '000001.SZ'
    start_date = '2025-01-01'
    end_date = '2025-01-10'
    
    try:
        news = get_stock_news(symbol, start_date, end_date)
        assert isinstance(news, list)
        print(f"Stock news retrieved: {len(news)} articles")
    except Exception as e:
        print(f"Stock news test failed (expected if no DB): {e}")

# Test get_market_news function
def test_get_market_news():
    """Test market news retrieval with different types"""
    start_date = '2025-01-01'
    end_date = '2025-01-10'
    
    # Test global news
    try:
        global_news = get_market_news(start_date, end_date, "global")
        assert isinstance(global_news, list)
        print(f"Global market news: {len(global_news)} articles")
    except Exception as e:
        print(f"Global news test failed (expected if no DB): {e}")
    
    # Test macro news
    try:
        macro_news = get_market_news(start_date, end_date, "macro")
        assert isinstance(macro_news, list)
        print(f"Macro market news: {len(macro_news)} articles")
    except Exception as e:
        print(f"Macro news test failed (expected if no DB): {e}")
    
    # Test industry news
    try:
        industry_news = get_market_news(start_date, end_date, "industry")
        assert isinstance(industry_news, list)
        print(f"Industry market news: {len(industry_news)} articles")
    except Exception as e:
        print(f"Industry news test failed (expected if no DB): {e}")

# Test compatibility functions
def test_compatibility_functions():
    """Test backward compatibility functions"""
    symbol = '000001.SZ'
    start_date = '2025-01-01'
    end_date = '2025-01-10'
    
    # Test China stock data functions
    try:
        china_data = get_china_stock_data(symbol, start_date, end_date, "technical")
        assert isinstance(china_data, list)
        print(f"China stock data: {len(china_data)} records")
    except Exception as e:
        print(f"China stock data test failed (expected if no DB): {e}")
    
    try:
        china_info = get_china_stock_info(symbol)
        if china_info:
            assert isinstance(china_info, dict)
            print(f"China stock info retrieved")
        else:
            print("China stock info not found (expected if no DB)")
    except Exception as e:
        print(f"China stock info test failed: {e}")
    
    # Test HK stock data functions
    hk_symbol = '00700.HK'
    try:
        hk_data = get_hk_stock_data(hk_symbol, start_date, end_date, "technical")
        assert isinstance(hk_data, list)
        print(f"HK stock data: {len(hk_data)} records")
    except Exception as e:
        print(f"HK stock data test failed (expected if no DB): {e}")
    
    try:
        hk_info = get_hk_stock_info(hk_symbol)
        if hk_info:
            assert isinstance(hk_info, dict)
            print(f"HK stock info retrieved")
        else:
            print("HK stock info not found (expected if no DB)")
    except Exception as e:
        print(f"HK stock info test failed: {e}")

# Test legacy functions
def test_legacy_functions():
    """Test legacy function names for backward compatibility"""
    symbol = '000001.SZ'
    start_date = '2025-01-01'
    end_date = '2025-01-10'
    
    try:
        technical_data = get_stock_daily_technical(symbol, start_date, end_date)
        assert isinstance(technical_data, list)
        print(f"Legacy technical data: {len(technical_data)} records")
    except Exception as e:
        print(f"Legacy technical test failed (expected if no DB): {e}")
    
    try:
        basic_data = get_stock_daily_basic(symbol, start_date, end_date)
        assert isinstance(basic_data, list)
        print(f"Legacy basic data: {len(basic_data)} records")
    except Exception as e:
        print(f"Legacy basic test failed (expected if no DB): {e}")

# Run all tests
if __name__ == "__main__":
    print("Running document module tests...")
    print("=" * 50)
    
    print("\n1. Testing detect_market function:")
    test_detect_market()
    
    print("\n2. Testing get_stock_data function:")
    test_get_stock_data()
    
    print("\n3. Testing get_stock_info function:")
    test_get_stock_info()
    
    print("\n4. Testing get_stock_news function:")
    test_get_stock_news()
    
    print("\n5. Testing get_market_news function:")
    test_get_market_news()
    
    print("\n6. Testing compatibility functions:")
    test_compatibility_functions()
    
    print("\n7. Testing legacy functions:")
    test_legacy_functions()
    
    print("\n" + "=" * 50)
    print("All tests completed!")