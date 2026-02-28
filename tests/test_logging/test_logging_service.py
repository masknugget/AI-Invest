"""
日志服务集成测试
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from app.services.logging import LogService, get_log_service
from app.services.logging.models import LogType, LogLevel


class TestLogService:
    """测试日志服务"""
    
    @pytest.fixture
    async def service(self, memory_storage):
        """服务实例"""
        service = LogService(
            storage=memory_storage,
            enable_async_processor=False,  # 测试时禁用异步处理器
            enable_archiver=False
        )
        yield service
    
    @pytest.mark.asyncio
    async def test_write_log(self, service):
        """测试写入日志"""
        result = await service.write_log(
            log_type=LogType.OPERATION,
            level=LogLevel.INFO,
            action="test_action",
            message="Test message",
            user_id="test_user"
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_write_log_with_details(self, service):
        """测试写入带详情的日志"""
        result = await service.write_log(
            log_type=LogType.ERROR,
            level=LogLevel.ERROR,
            action="api_error",
            message="API call failed",
            user_id="user1",
            username="Test User",
            details={"error_code": 500, "endpoint": "/api/test"},
            duration_ms=150
        )
        
        assert result is True
        
        # 验证数据已写入
        logs = await service.query_logs(days=1)
        assert len(logs) == 1
        assert logs[0]["details"]["error_code"] == 500
    
    @pytest.mark.asyncio
    async def test_query_logs(self, service):
        """测试查询日志"""
        # 写入测试数据
        for i in range(5):
            await service.write_log(
                log_type=LogType.OPERATION,
                level=LogLevel.INFO,
                action="action",
                message=f"Message {i}",
                user_id="user1"
            )
        
        logs = await service.query_logs(days=1, limit=10)
        
        assert len(logs) == 5
    
    @pytest.mark.asyncio
    async def test_count_logs(self, service):
        """测试统计日志"""
        # 写入不同类型日志
        await service.write_log(
            log_type=LogType.OPERATION,
            level=LogLevel.INFO,
            action="test",
            message="Info"
        )
        
        await service.write_log(
            log_type=LogType.ERROR,
            level=LogLevel.ERROR,
            action="test",
            message="Error"
        )
        
        total = await service.count_logs(days=1)
        errors = await service.count_logs(level=LogLevel.ERROR.value, days=1)
        
        assert total == 2
        assert errors == 1
    
    @pytest.mark.asyncio
    async def test_export_logs_csv(self, service):
        """测试 CSV 导出"""
        # 写入测试数据
        await service.write_log(
            log_type=LogType.OPERATION,
            level=LogLevel.INFO,
            action="test",
            message="Test"
        )
        
        result = await service.export_logs(format="csv", days=1)
        
        assert result.success is True
        assert result.record_count == 1
        assert result.format == "csv"
    
    @pytest.mark.asyncio
    async def test_export_logs_json(self, service):
        """测试 JSON 导出"""
        await service.write_log(
            log_type=LogType.OPERATION,
            level=LogLevel.INFO,
            action="test",
            message="Test"
        )
        
        result = await service.export_logs(format="json", days=1)
        
        assert result.success is True
        assert result.format == "json"
    
    @pytest.mark.asyncio
    async def test_export_empty_logs(self, service):
        """测试导出空日志"""
        result = await service.export_logs(format="csv", days=1)
        
        assert result.success is True
        assert result.record_count == 0
    
    @pytest.mark.asyncio
    async def test_analyze_user_activity(self, service):
        """测试用户活动分析"""
        # 写入用户活动数据
        for i in range(10):
            await service.write_log(
                log_type=LogType.OPERATION,
                level=LogLevel.INFO,
                action="stock_analysis",
                message="分析股票",
                user_id="test_user",
                details={"feature": "analysis"},
                success=True
            )
        
        stats = await service.analyze_user_activity("test_user", days=7)
        
        assert stats.user_id == "test_user"
        assert stats.total_actions == 10
    
    @pytest.mark.asyncio
    async def test_analyze_security(self, service):
        """测试安全分析"""
        # 写入安全相关日志
        for i in range(5):
            await service.write_log(
                log_type=LogType.SECURITY,
                level=LogLevel.WARNING,
                action="suspicious_access",
                severity="medium",
                message="Suspicious activity"
            )
        
        stats = await service.analyze_security(hours=24)
        
        assert stats.total_threats == 5
        assert stats.medium_threats == 5
    
    @pytest.mark.asyncio
    async def test_detect_anomalies(self, service):
        """测试异常检测"""
        # 写入异常行为数据
        for i in range(10):
            await service.write_log(
                log_type=LogType.OPERATION,
                level=LogLevel.INFO,
                action="login",
                message="Login attempt",
                user_id="user1",
                timestamp=datetime.utcnow() - timedelta(hours=i)
            )
        
        anomalies = await service.detect_anomalies(user_id="user1", hours=24)
        
        assert isinstance(anomalies, list)
    
    @pytest.mark.asyncio
    async def test_analyze_system_health(self, service):
        """测试系统健康分析"""
        # 写入访问日志
        for i in range(10):
            await service.write_log(
                log_type=LogType.ACCESS,
                level=LogLevel.INFO,
                action="api_request",
                message="API request",
                duration_ms=100 + i * 10
            )
        
        stats = await service.analyze_system_health(hours=24)
        
        assert stats.avg_response_time_ms > 0
        assert stats.requests_per_minute >= 0
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(self, memory_storage):
        """测试服务生命周期"""
        service = LogService(
            storage=memory_storage,
            enable_async_processor=True
        )
        
        # 启动
        await service.start()
        assert service._started is True
        
        # 停止
        await service.stop()
        assert service._started is False


class TestLogServiceSingleton:
    """测试日志服务单例"""
    
    def test_get_log_service(self):
        """测试获取单例实例"""
        service1 = get_log_service()
        service2 = get_log_service()
        
        assert service1 is service2
    
    @pytest.mark.asyncio
    async def test_init_and_shutdown(self):
        """测试初始化和关闭"""
        from app.services.logging import init_log_service, shutdown_log_service
        
        # 初始化
        service = await init_log_service()
        assert service is not None
        
        # 关闭
        await shutdown_log_service()
