"""
日志 API 路由测试
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

from app.main import app
from app.services.logging.models import LogType, LogLevel


# 模拟管理员用户
@pytest.fixture
def mock_admin_user():
    return {
        "id": "admin",
        "username": "admin",
        "is_admin": True
    }


# 模拟日志服务
@pytest.fixture
def mock_log_service():
    service = Mock()
    service.query_logs = AsyncMock(return_value=[
        {
            "id": "1",
            "log_type": "operation",
            "level": "info",
            "action": "login",
            "message": "User login",
            "timestamp": datetime.utcnow().isoformat()
        }
    ])
    service.count_logs = AsyncMock(return_value=100)
    service.get_log_by_id = AsyncMock(return_value={
        "id": "1",
        "log_type": "operation",
        "message": "Test"
    })
    service.export_logs = AsyncMock(return_value=Mock(
        success=True,
        file_path="/tmp/test.csv",
        file_name="test.csv",
        file_size_bytes=1024,
        record_count=10,
        format="csv",
        created_at=datetime.utcnow()
    ))
    service.analyze_user_activity = AsyncMock(return_value=Mock(
        user_id="test_user",
        total_actions=50,
        active_days=20,
        model_dump=lambda: {
            "user_id": "test_user",
            "total_actions": 50,
            "active_days": 20
        }
    ))
    service.analyze_security = AsyncMock(return_value=Mock(
        total_threats=5,
        model_dump=lambda: {"total_threats": 5}
    ))
    service.analyze_system_health = AsyncMock(return_value=Mock(
        health_score=95,
        model_dump=lambda: {"health_score": 95}
    ))
    service.detect_anomalies = AsyncMock(return_value=[
        {"type": "unusual_login", "severity": "medium"}
    ])
    service.get_archive_stats = AsyncMock(return_value={
        "total_files": 10,
        "total_size_mb": 100
    })
    service.storage = Mock()
    service.storage.query = AsyncMock(return_value=[])
    service.storage.count = AsyncMock(return_value=0)
    service.storage.delete = AsyncMock(return_value=10)
    return service


class TestLogsAPI:
    """测试日志 API"""
    
    @pytest.fixture(autouse=True)
    def setup_mocks(self, mock_log_service, mock_admin_user):
        """设置模拟"""
        with patch("app.routers.logs.get_log_service", return_value=mock_log_service), \
             patch("app.routers.logs.get_current_admin_user", return_value=mock_admin_user):
            yield
    
    def test_query_logs_post(self, client):
        """测试 POST 查询日志"""
        response = client.post("/api/logs/query", json={
            "log_type": "operation",
            "days": 7,
            "limit": 50
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "logs" in data["data"]
    
    def test_query_logs_get(self, client):
        """测试 GET 查询日志"""
        response = client.get("/api/logs/query?log_type=operation&days=7&limit=50")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_get_log_detail(self, client):
        """测试获取日志详情"""
        response = client.get("/api/logs/507f1f77bcf86cd799439011")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_get_log_detail_not_found(self, client, mock_log_service):
        """测试获取不存在的日志"""
        mock_log_service.get_log_by_id = AsyncMock(return_value=None)
        
        response = client.get("/api/logs/nonexistent")
        
        assert response.status_code == 404
    
    def test_export_logs(self, client):
        """测试导出日志"""
        response = client.post("/api/logs/export", json={
            "format": "csv",
            "days": 7,
            "log_type": "operation"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["format"] == "csv"
    
    def test_list_exports(self, client):
        """测试列出导出文件"""
        response = client.get("/api/logs/exports/list")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
    
    def test_get_stats_overview(self, client):
        """测试获取统计概览"""
        response = client.get("/api/logs/stats/overview?days=7")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "type_distribution" in data["data"]
    
    def test_analyze_user_post(self, client):
        """测试 POST 用户分析"""
        response = client.post("/api/logs/analytics/user", json={
            "user_id": "test_user",
            "days": 30
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["user_id"] == "test_user"
    
    def test_analyze_user_get(self, client):
        """测试 GET 用户分析"""
        response = client.get("/api/logs/analytics/user/test_user?days=30")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_analyze_security(self, client):
        """测试安全分析"""
        response = client.get("/api/logs/analytics/security?hours=24")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_analyze_health(self, client):
        """测试健康分析"""
        response = client.get("/api/logs/analytics/health?hours=24")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_detect_anomalies(self, client):
        """测试异常检测"""
        response = client.get("/api/logs/analytics/anomalies?hours=24")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "anomalies" in data["data"]
    
    def test_get_active_users(self, client):
        """测试获取活跃用户"""
        response = client.get("/api/logs/analytics/active-users?days=7")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_archive_logs(self, client):
        """测试归档日志"""
        response = client.post("/api/logs/archive", json={
            "log_type": "operation",
            "days": 90
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_get_archive_stats(self, client):
        """测试获取归档统计"""
        response = client.get("/api/logs/archive/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_get_service_stats(self, client):
        """测试获取服务统计"""
        response = client.get("/api/logs/management/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_cleanup_logs(self, client):
        """测试清理日志"""
        response = client.post("/api/logs/management/cleanup?days=365")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted_count" in data["data"]
    
    def test_get_log_types(self, client):
        """测试获取日志类型枚举"""
        response = client.get("/api/logs/enums/types")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0
    
    def test_get_log_levels(self, client):
        """测试获取日志级别枚举"""
        response = client.get("/api/logs/enums/levels")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0


# 测试客户端 fixture
@pytest.fixture
def client():
    """测试客户端"""
    return TestClient(app)
