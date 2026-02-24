# TradingAgents-CN 测试模块

本项目测试模块采用简洁的开发测试风格，不使用 pytest 框架，直接使用 Python 脚本运行测试。

## 测试结构

```
tests/
├── test_core/              # 核心模块单元测试
│   ├── test_config.py      # 配置管理测试
│   ├── test_response.py    # 响应格式测试
│   └── test_rate_limiter.py # 速率限制测试
├── test_services/          # 服务层单元测试
│   ├── test_auth_service.py # 认证服务测试
│   └── test_trading_time.py # 交易时间工具测试
├── test_utils/             # 工具函数测试
│   └── test_stock_utils.py # 股票工具函数测试
├── test_dataflows/         # 数据流测试
│   └── test_data_source.py # 数据源测试
├── test_integration/       # 集成测试
│   └── test_analysis_workflow.py # 分析工作流测试
├── test_api/               # API接口测试
│   ├── test_auth_api.py    # 认证API测试
│   ├── test_analysis_api.py # 分析API测试
│   ├── test_chatbot_api.py # 聊天机器人API测试
│   └── test_stock_data_api.py # 股票数据API测试
├── test_connect/           # 连接测试
│   ├── test_mongo.py       # MongoDB连接测试
│   ├── test_redis.py       # Redis连接测试
│   ├── test_pgsql.py       # PostgreSQL连接测试
│   └── test_es.py          # Elasticsearch连接测试
├── test_db/                # 数据库操作测试
│   └── test_db.py          # 数据库操作测试
├── test_router/            # 路由测试
│   └── test_config_provider.py # 配置提供者测试
├── run_tests.py            # 测试运行器
└── README.md               # 本文件
```

## 运行测试

### 运行所有测试

```bash
# 使用虚拟环境的 Python
.venv\Scripts\python.exe tests\run_tests.py

# 或使用 python 命令 (如果虚拟环境已激活)
python tests\run_tests.py
```

### 运行快速测试 (不包括连接测试)

```bash
.venv\Scripts\python.exe tests\run_tests.py --quick
```

### 运行特定类别测试

```bash
.venv\Scripts\python.exe tests\run_tests.py --category 核心模块
.venv\Scripts\python.exe tests\run_tests.py --category 服务层
.venv\Scripts\python.exe tests\run_tests.py --category 连接测试
```

### 运行单个测试文件

```bash
.venv\Scripts\python.exe tests\test_core\test_config.py
.venv\Scripts\python.exe tests\test_services\test_auth_service.py
```

## 测试分类

### 1. 单元测试 (test_core, test_services, test_utils)

测试独立的函数和类，不依赖外部服务。

- **test_core/**: 测试核心配置、响应格式、速率限制等
- **test_services/**: 测试认证服务、交易时间计算等
- **test_utils/**: 测试股票代码处理、数据转换等工具函数

### 2. API测试 (test_api)

测试HTTP接口，需要后端服务运行。

**前置条件**: 
```bash
python -m app.main
```

运行测试:
```bash
python tests/test_api/test_auth_api.py
python tests/test_api/test_analysis_api.py
```

### 3. 连接测试 (test_connect)

测试数据库和中间件连接。

**前置条件**: MongoDB、Redis等服务已启动

### 4. 集成测试 (test_integration)

测试完整的业务流程，可能需要外部API密钥。

## 编写新测试

参考现有测试文件的风格:

```python
"""
测试描述
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 导入被测试的模块
from app.xxx import xxx


def test_something():
    """测试描述"""
    print("=== 测试描述 ===")
    
    # 测试代码
    result = xxx()
    assert result == expected, "错误信息"
    
    print("✅ 测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    tests = [
        ("测试名称", test_something),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ {test_name} 测试失败: {e}")
            failed += 1
    
    print(f"\n测试结果: 通过 {passed}, 失败 {failed}")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
```

## 测试规范

1. **每个测试函数应该有明确的名称和描述**
2. **使用 `print` 输出测试进度和结果**
3. **使用 `assert` 进行验证**
4. **返回 `True` 表示测试通过**
5. **测试文件应该可以直接运行**: `python test_xxx.py`
6. **测试应该独立，不依赖其他测试的执行顺序**

## 环境要求

- Python 3.10+
- 项目依赖已安装: `pip install -r requirements.txt`
- 对于API测试: 后端服务需要运行
- 对于连接测试: 相关数据库服务需要运行

## 注意事项

1. **API测试**需要有效的用户账号，默认使用 `admin/admin123`
2. **连接测试**需要正确的数据库配置 (.env 文件)
3. **集成测试**可能需要配置外部API密钥
4. 测试文件中的硬编码API密钥仅用于测试，生产环境请使用环境变量
