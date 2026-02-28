"""
过滤处理器测试
"""

import pytest

from app.services.logging.processors import FilterProcessor, LogFilterRule
from app.services.logging.models import LogLevel, LogType


class TestLogFilterRule:
    """测试日志过滤规则"""
    
    def test_match_log_type(self):
        """测试日志类型匹配"""
        rule = LogFilterRule(
            name="test_rule",
            log_types=[LogType.OPERATION.value, LogType.AUDIT.value],
            action="drop"
        )
        
        assert rule.matches({"log_type": LogType.OPERATION.value}) is True
        assert rule.matches({"log_type": LogType.ERROR.value}) is False
    
    def test_match_level(self):
        """测试级别匹配"""
        rule = LogFilterRule(
            name="test_rule",
            levels=[LogLevel.ERROR.value, LogLevel.CRITICAL.value],
            action="drop"
        )
        
        assert rule.matches({"level": LogLevel.ERROR.value}) is True
        assert rule.matches({"level": LogLevel.INFO.value}) is False
    
    def test_match_user(self):
        """测试用户匹配"""
        rule = LogFilterRule(
            name="test_rule",
            users=["admin", "root"],
            action="drop"
        )
        
        assert rule.matches({"user_id": "admin"}) is True
        assert rule.matches({"user_id": "user1"}) is False
    
    def test_match_text_content(self):
        """测试文本内容匹配"""
        rule = LogFilterRule(
            name="test_rule",
            contains_text="password",
            action="tag",
            tags_to_add=["sensitive"]
        )
        
        assert rule.matches({"message": "User password changed"}) is True
        assert rule.matches({"message": "User login success"}) is False
    
    def test_match_regex(self):
        """测试正则匹配"""
        rule = LogFilterRule(
            name="test_rule",
            regex_pattern=r"\d{3}-\d{4}",  # 匹配电话格式
            action="tag"
        )
        
        assert rule.matches({"message": "Contact: 123-4567"}) is True
        assert rule.matches({"message": "No phone here"}) is False
    
    def test_match_field_condition(self):
        """测试字段条件匹配"""
        rule = LogFilterRule(
            name="test_rule",
            field_conditions={"status": "failed", "retry_count": 3},
            action="drop"
        )
        
        assert rule.matches({"status": "failed", "retry_count": 3}) is True
        assert rule.matches({"status": "failed", "retry_count": 1}) is False
    
    def test_match_nested_field(self):
        """测试嵌套字段匹配"""
        rule = LogFilterRule(
            name="test_rule",
            field_conditions={"details.source": "api"},
            action="drop"
        )
        
        assert rule.matches({"details": {"source": "api"}}) is True
        assert rule.matches({"details": {"source": "web"}}) is False
    
    def test_disabled_rule(self):
        """测试禁用规则"""
        rule = LogFilterRule(
            name="test_rule",
            enabled=False,
            log_types=[LogType.OPERATION.value],
            action="drop"
        )
        
        assert rule.matches({"log_type": LogType.OPERATION.value}) is False


class TestFilterProcessor:
    """测试过滤处理器"""
    
    @pytest.fixture
    def processor(self):
        return FilterProcessor()
    
    @pytest.mark.asyncio
    async def test_keep_action(self, processor):
        """测试保留操作"""
        rule = LogFilterRule(
            name="keep_rule",
            log_types=[LogType.OPERATION.value],
            action="keep"
        )
        processor.add_rule(rule)
        
        entry = {"log_type": LogType.OPERATION.value, "message": "test"}
        result = await processor.process(entry)
        
        assert result is not None
        assert result["message"] == "test"
    
    @pytest.mark.asyncio
    async def test_drop_action(self, processor):
        """测试丢弃操作"""
        rule = LogFilterRule(
            name="drop_rule",
            levels=[LogLevel.DEBUG.value],
            action="drop"
        )
        processor.add_rule(rule)
        
        entry = {"level": LogLevel.DEBUG.value}
        result = await processor.process(entry)
        
        assert result is None
        assert processor._stats["dropped"] == 1
    
    @pytest.mark.asyncio
    async def test_tag_action(self, processor):
        """测试标签操作"""
        rule = LogFilterRule(
            name="tag_rule",
            log_types=[LogType.SECURITY.value],
            action="tag",
            tags_to_add=["alert", "high_priority"]
        )
        processor.add_rule(rule)
        
        entry = {"log_type": LogType.SECURITY.value, "tags": []}
        result = await processor.process(entry)
        
        assert "alert" in result["tags"]
        assert "high_priority" in result["tags"]
        assert processor._stats["tagged"] == 1
    
    @pytest.mark.asyncio
    async def test_sample_action(self, processor):
        """测试采样操作"""
        import random
        random.seed(42)  # 固定随机种子
        
        rule = LogFilterRule(
            name="sample_rule",
            log_types=[LogType.DEBUG.value],
            action="sample",
            sample_rate=0.5
        )
        processor.add_rule(rule)
        
        # 处理多条日志，部分应该被采样
        kept = 0
        for i in range(100):
            entry = {"log_type": LogType.DEBUG.value}
            result = await processor.process(entry)
            if result:
                kept += 1
        
        # 大约50%被保留
        assert 30 < kept < 70
    
    @pytest.mark.asyncio
    async def test_multiple_rules(self, processor):
        """测试多条规则"""
        processor.add_rule(LogFilterRule(
            name="rule1",
            levels=[LogLevel.DEBUG.value],
            action="drop"
        ))
        processor.add_rule(LogFilterRule(
            name="rule2",
            log_types=[LogType.ERROR.value],
            action="tag",
            tags_to_add=["error_tag"]
        ))
        
        # DEBUG 级别应该被丢弃
        result = await processor.process({"level": LogLevel.DEBUG.value})
        assert result is None
        
        # ERROR 类型应该被标签
        result = await processor.process({
            "level": LogLevel.INFO.value,
            "log_type": LogType.ERROR.value,
            "tags": []
        })
        assert "error_tag" in result["tags"]
    
    def test_remove_rule(self, processor):
        """测试移除规则"""
        processor.add_rule(LogFilterRule(name="rule1", action="keep"))
        processor.add_rule(LogFilterRule(name="rule2", action="keep"))
        
        assert processor.remove_rule("rule1") is True
        assert processor.remove_rule("rule1") is False
        assert len(processor.rules) == 1
    
    def test_get_stats(self, processor):
        """测试统计信息"""
        stats = processor.get_stats()
        
        assert "total_processed" in stats
        assert "dropped" in stats
        assert "tagged" in stats
    
    def test_reset_stats(self, processor):
        """测试重置统计"""
        processor._stats["total_processed"] = 100
        processor._stats["dropped"] = 10
        
        processor.reset_stats()
        
        assert processor._stats["total_processed"] == 0
        assert processor._stats["dropped"] == 0


class TestPredefinedRules:
    """测试预定义规则"""
    
    def test_ignore_health_checks(self):
        """测试忽略健康检查规则"""
        from app.services.logging.processors.filter_processor import PREDEFINED_RULES
        
        rule = PREDEFINED_RULES["ignore_health_checks"]
        
        assert rule.matches({"action": "/health"}) is True
        assert rule.matches({"action": "/healthz"}) is True
        assert rule.matches({"action": "/api/users"}) is False
    
    def test_drop_test_user_logs(self):
        """测试丢弃测试用户日志规则"""
        from app.services.logging.processors.filter_processor import PREDEFINED_RULES
        
        rule = PREDEFINED_RULES["drop_test_user_logs"]
        
        assert rule.matches({"user_id": "test"}) is True
        assert rule.matches({"user_id": "demo"}) is True
        assert rule.matches({"user_id": "admin"}) is False
