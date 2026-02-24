"""
日志模块测试入口
运行所有日志相关测试

使用方法:
    pytest tests/test_logging/test_all.py -v
    
或分别运行各模块测试:
    pytest tests/test_logging/test_models.py -v
    pytest tests/test_logging/test_core/ -v
    pytest tests/test_logging/test_processors/ -v
    pytest tests/test_logging/test_analyzers/ -v
    pytest tests/test_logging/test_exporters/ -v
    pytest tests/test_logging/test_archivers/ -v
"""

import pytest

# 这个文件用于标记日志模块测试的入口点
# 实际的测试分布在各个子模块中

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
