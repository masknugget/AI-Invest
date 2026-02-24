"""
用户行为分析器测试
"""

import pytest
from datetime import datetime, timedelta

from app.services.logging.analyzers import UserBehaviorAnalyzer
from app.services.logging.models import LogType, LogLevel


class TestUserBehaviorAnalyzer:
    """测试用户行为分析器"""
    
    @pytest.fixture
    async def analyzer(self, memory_storage):
        """分析器实例"""
        return UserBehaviorAnalyzer(memory_storage)
    
    @pytest.mark.asyncio
    async def test_analyze_user_activity_basic(self, analyzer, memory_storage):
        """测试基础用户活动分析"""
        # 准备测试数据
        user_id = "test_user"
        now = datetime.utcnow()
        
        for i in range(5):
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "level": LogLevel.INFO.value,
                "action": "stock_analysis",
                "message": "分析股票",
                "user_id": user_id,
                "username": "Test User",
                "timestamp": now - timedelta(hours=i),
                "success": True,
                "duration_ms": 100
            })
        
        stats = await analyzer.analyze_user_activity(user_id, days=7)
        
        assert stats.user_id == user_id
        assert stats.total_actions == 5
        assert stats.active_days >= 1
        assert "stock_analysis" in stats.action_distribution
    
    @pytest.mark.asyncio
    async def test_analyze_user_activity_empty(self, analyzer):
        """测试无数据用户"""
        stats = await analyzer.analyze_user_activity("non_existent_user", days=7)
        
        assert stats.user_id == "non_existent_user"
        assert stats.total_actions == 0
        assert stats.active_days == 0
    
    @pytest.mark.asyncio
    async def test_action_distribution(self, analyzer, memory_storage):
        """测试动作分布统计"""
        user_id = "user1"
        now = datetime.utcnow()
        
        # 不同动作类型
        actions = ["login", "view", "edit", "login", "view", "view"]
        for action in actions:
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "action": action,
                "user_id": user_id,
                "timestamp": now,
                "success": True
            })
        
        stats = await analyzer.analyze_user_activity(user_id, days=1)
        
        assert stats.action_distribution["view"] == 3
        assert stats.action_distribution["login"] == 2
        assert stats.action_distribution["edit"] == 1
    
    @pytest.mark.asyncio
    async def test_hourly_distribution(self, analyzer, memory_storage):
        """测试小时分布"""
        user_id = "user1"
        base_time = datetime.utcnow().replace(hour=0, minute=0)
        
        # 在特定小时创建日志
        for hour in [9, 9, 10, 14, 14, 14]:
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "test",
                "user_id": user_id,
                "timestamp": base_time + timedelta(hours=hour)
            })
        
        stats = await analyzer.analyze_user_activity(user_id, days=1)
        
        assert stats.hourly_distribution[9] == 2
        assert stats.hourly_distribution[10] == 1
        assert stats.hourly_distribution[14] == 3
    
    @pytest.mark.asyncio
    async def test_success_rate_calculation(self, analyzer, memory_storage):
        """测试成功率计算"""
        user_id = "user1"
        now = datetime.utcnow()
        
        # 成功和失败混合
        for i in range(8):
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "api_call",
                "user_id": user_id,
                "timestamp": now,
                "success": i < 7  # 7成功，1失败
            })
        
        stats = await analyzer.analyze_user_activity(user_id, days=1)
        
        assert stats.success_rate == 87.5  # 7/8 = 87.5%
    
    @pytest.mark.asyncio
    async def test_unusual_hours_detection(self, analyzer, memory_storage):
        """测试非常规时段检测"""
        user_id = "user1"
        base_time = datetime.utcnow().replace(hour=0)
        
        # 深夜操作 (0-5点)
        for hour in [2, 3, 4]:
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "login",
                "user_id": user_id,
                "timestamp": base_time + timedelta(hours=hour)
            })
        
        # 正常时间操作
        for hour in [9, 10]:
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "login",
                "user_id": user_id,
                "timestamp": base_time + timedelta(hours=hour)
            })
        
        stats = await analyzer.analyze_user_activity(user_id, days=1)
        
        assert stats.unusual_hours_count == 3
    
    @pytest.mark.asyncio
    async def test_most_used_feature(self, analyzer, memory_storage):
        """测试最常用功能"""
        user_id = "user1"
        now = datetime.utcnow()
        
        features = ["screening", "analysis", "analysis", "report", "analysis"]
        for feature in features:
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "use_feature",
                "user_id": user_id,
                "timestamp": now,
                "details": {"feature": feature}
            })
        
        stats = await analyzer.analyze_user_activity(user_id, days=1)
        
        assert stats.most_used_feature == "analysis"
        assert stats.feature_usage["analysis"] == 3
    
    @pytest.mark.asyncio
    async def test_compare_users(self, analyzer, memory_storage):
        """测试用户对比"""
        now = datetime.utcnow()
        
        # 用户1数据
        for i in range(10):
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "test",
                "user_id": "user1",
                "timestamp": now
            })
        
        # 用户2数据
        for i in range(5):
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "test",
                "user_id": "user2",
                "timestamp": now
            })
        
        comparison = await analyzer.compare_users(["user1", "user2"], days=1)
        
        assert comparison["summary"]["total_users"] == 2
        assert comparison["summary"]["total_actions"] == 15
        assert comparison["summary"]["most_active_user"] == "user1"
    
    @pytest.mark.asyncio
    async def test_get_active_users(self, analyzer, memory_storage):
        """测试获取活跃用户"""
        now = datetime.utcnow()
        
        # 活跃用户
        for i in range(5):
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "test",
                "user_id": f"active_user_{i}",
                "username": f"User {i}",
                "timestamp": now
            })
        
        # 不活跃用户 (7天前)
        await memory_storage.write({
            "log_type": LogType.OPERATION.value,
            "action": "test",
            "user_id": "inactive_user",
            "timestamp": now - timedelta(days=10)
        })
        
        users = await analyzer.get_active_users(days=7, min_actions=1)
        
        assert len(users) == 5
    
    @pytest.mark.asyncio
    async def test_session_analysis(self, analyzer, memory_storage):
        """测试会话分析"""
        user_id = "user1"
        base_time = datetime.utcnow()
        
        # 会话1
        for i in range(3):
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "action": f"action_{i}",
                "user_id": user_id,
                "session_id": "session_1",
                "timestamp": base_time + timedelta(minutes=i * 5)
            })
        
        # 会话2
        for i in range(2):
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "action": f"action_{i}",
                "user_id": user_id,
                "session_id": "session_2",
                "timestamp": base_time + timedelta(hours=2, minutes=i * 10)
            })
        
        session_stats = await analyzer.get_user_session_analysis(user_id, days=1)
        
        assert session_stats["total_sessions"] == 2
        assert len(session_stats["sessions"]) == 2
