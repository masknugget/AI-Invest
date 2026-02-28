"""
安全分析器测试
"""

import pytest
from datetime import datetime, timedelta

from app.services.logging.analyzers import SecurityAnalyzer
from app.services.logging.models import LogType, LogLevel


class TestSecurityAnalyzer:
    """测试安全分析器"""
    
    @pytest.fixture
    async def analyzer(self, memory_storage):
        """分析器实例"""
        return SecurityAnalyzer(memory_storage)
    
    @pytest.mark.asyncio
    async def test_analyze_security_basic(self, analyzer, memory_storage):
        """测试基础安全分析"""
        now = datetime.utcnow()
        
        # 添加安全日志
        for i in range(5):
            await memory_storage.write({
                "log_type": LogType.SECURITY.value,
                "level": LogLevel.WARNING.value,
                "action": "suspicious_access",
                "severity": "medium",
                "threat_type": "scan",
                "timestamp": now
            })
        
        stats = await analyzer.analyze_security(hours=24)
        
        assert stats.total_threats == 5
        assert stats.medium_threats == 5
    
    @pytest.mark.asyncio
    async def test_brute_force_detection(self, analyzer, memory_storage):
        """测试暴力破解检测"""
        now = datetime.utcnow()
        
        # 模拟暴力破解攻击
        for i in range(10):
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "level": LogLevel.ERROR.value,
                "action": "user_login",
                "message": "登录失败",
                "user_id": "victim",
                "ip_address": "10.0.0.1",
                "success": False,
                "timestamp": now + timedelta(minutes=i * 2)
            })
        
        attacks = await analyzer._detect_brute_force(now - timedelta(hours=1))
        
        assert len(attacks) >= 1
        assert attacks[0]["type"] == "brute_force"
        assert attacks[0]["source_ip"] == "10.0.0.1"
    
    @pytest.mark.asyncio
    async def test_rapid_access_detection(self, analyzer, memory_storage):
        """测试高频访问检测"""
        now = datetime.utcnow()
        
        # 模拟高频访问
        for i in range(150):
            await memory_storage.write({
                "log_type": LogType.ACCESS.value,
                "action": "api_request",
                "ip_address": "192.168.1.100",
                "timestamp": now + timedelta(seconds=i * 10),
                "user_id": "user1"
            })
        
        attacks = await analyzer._detect_rapid_access(now - timedelta(hours=1))
        
        assert len(attacks) >= 1
        assert attacks[0]["type"] == "rapid_access"
    
    @pytest.mark.asyncio
    async def test_unusual_login_time_detection(self, analyzer, memory_storage):
        """测试非常规登录时间检测"""
        base_time = datetime.utcnow().replace(hour=0, minute=0)
        
        # 深夜登录 (2点和3点)
        for hour in [2, 3]:
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "user_login",
                "message": "用户登录",
                "user_id": "user1",
                "ip_address": "192.168.1.1",
                "success": True,
                "timestamp": base_time + timedelta(hours=hour)
            })
        
        attacks = await analyzer._detect_unusual_login_times(base_time)
        
        # 应该检测到非常规时间登录
        unusual_logins = [a for a in attacks if a["type"] == "unusual_login_time"]
        assert len(unusual_logins) >= 1
    
    @pytest.mark.asyncio
    async def test_sql_injection_detection(self, analyzer, memory_storage):
        """测试SQL注入检测"""
        now = datetime.utcnow()
        
        # 模拟SQL注入尝试
        payloads = [
            "SELECT * FROM users WHERE id = 1 OR 1=1",
            "'; DROP TABLE users; --",
            "UNION SELECT * FROM passwords"
        ]
        
        for payload in payloads:
            await memory_storage.write({
                "log_type": LogType.ERROR.value,
                "level": LogLevel.ERROR.value,
                "action": "api_request",
                "message": f"Error processing: {payload}",
                "ip_address": "10.0.0.99",
                "timestamp": now
            })
        
        attacks = await analyzer._detect_injection_attempts(now - timedelta(hours=1))
        
        sql_attacks = [a for a in attacks if a["type"] == "sql_injection_attempt"]
        assert len(sql_attacks) >= 1
    
    @pytest.mark.asyncio
    async def test_threat_severity_classification(self, analyzer, memory_storage):
        """测试威胁严重级别分类"""
        now = datetime.utcnow()
        
        # 不同级别的威胁
        threats = [
            ("critical", "data_breach"),
            ("high", "brute_force"),
            ("medium", "scan"),
            ("low", "info_leak")
        ]
        
        for severity, threat_type in threats:
            await memory_storage.write({
                "log_type": LogType.SECURITY.value,
                "level": LogLevel.ERROR.value if severity in ["critical", "high"] else LogLevel.WARNING.value,
                "severity": severity,
                "threat_type": threat_type,
                "timestamp": now
            })
        
        stats = await analyzer.analyze_security(hours=24)
        
        assert stats.critical_threats == 1
        assert stats.high_threats == 1
        assert stats.medium_threats == 1
        assert stats.low_threats == 1
    
    @pytest.mark.asyncio
    async def test_top_source_ips(self, analyzer, memory_storage):
        """测试Top攻击源IP统计"""
        now = datetime.utcnow()
        
        # 不同IP的攻击
        ip_counts = {"10.0.0.1": 20, "10.0.0.2": 15, "10.0.0.3": 5}
        
        for ip, count in ip_counts.items():
            for i in range(count):
                await memory_storage.write({
                    "log_type": LogType.SECURITY.value,
                    "source_ip": ip,
                    "threat_type": "scan",
                    "timestamp": now
                })
        
        stats = await analyzer.analyze_security(hours=24)
        
        # 验证Top IP排序
        assert len(stats.top_source_ips) == 3
        assert stats.top_source_ips[0]["ip"] == "10.0.0.1"
        assert stats.top_source_ips[0]["count"] == 20
    
    @pytest.mark.asyncio
    async def test_auth_security_stats(self, analyzer, memory_storage):
        """测试认证安全统计"""
        now = datetime.utcnow()
        
        # 正常登录
        for i in range(20):
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "user_login",
                "user_id": f"user_{i % 5}",
                "ip_address": f"192.168.1.{i}",
                "success": True,
                "timestamp": now
            })
        
        # 失败登录
        for i in range(10):
            await memory_storage.write({
                "log_type": LogType.OPERATION.value,
                "action": "user_login",
                "user_id": "target_user",
                "ip_address": "10.0.0.1",
                "success": False,
                "timestamp": now
            })
        
        stats = await analyzer.analyze_security(hours=24)
        
        assert stats.failed_login_attempts == 10
        assert "target_user" in stats.suspicious_accounts
    
    @pytest.mark.asyncio
    async def test_threat_trend(self, analyzer, memory_storage):
        """测试威胁趋势"""
        base_time = datetime.utcnow() - timedelta(hours=24)
        
        # 模拟24小时的趋势
        for hour in range(24):
            for i in range(5 if hour < 12 else 10):  # 下午更多
                await memory_storage.write({
                    "log_type": LogType.SECURITY.value,
                    "level": LogLevel.WARNING.value,
                    "threat_type": "scan",
                    "timestamp": base_time + timedelta(hours=hour)
                })
        
        stats = await analyzer.analyze_security(hours=24)
        
        assert len(stats.threat_trend) > 0
        # 验证趋势数据包含count和error_count
        assert hasattr(stats.threat_trend[0], 'count')
    
    @pytest.mark.asyncio
    async def test_generate_security_report(self, analyzer, memory_storage):
        """测试生成安全报告"""
        now = datetime.utcnow()
        
        # 添加一些威胁数据
        for i in range(5):
            await memory_storage.write({
                "log_type": LogType.SECURITY.value,
                "severity": "high",
                "threat_type": "attack",
                "timestamp": now
            })
        
        report = await analyzer.generate_security_report(days=7)
        
        assert report["period_days"] == 7
        assert "summary" in report
        assert "details" in report
        assert "recommendations" in report
        assert report["summary"]["threat_level"] in ["low", "medium", "high", "critical"]
    
    def test_calculate_threat_level(self, analyzer):
        """测试威胁等级计算"""
        from app.services.logging.models import SecurityStats
        
        # 低风险
        low_stats = SecurityStats(total_threats=1, critical_threats=0, high_threats=0)
        assert analyzer._calculate_threat_level(low_stats) == "low"
        
        # 高风险
        high_stats = SecurityStats(total_threats=50, critical_threats=2, high_threats=5)
        assert analyzer._calculate_threat_level(high_stats) == "high"
        
        # 严重风险
        critical_stats = SecurityStats(total_threats=100, critical_threats=5, high_threats=10)
        assert analyzer._calculate_threat_level(critical_stats) == "critical"
    
    def test_is_private_ip(self, analyzer):
        """测试私有IP判断"""
        assert analyzer.is_private_ip("192.168.1.1") is True
        assert analyzer.is_private_ip("10.0.0.1") is True
        assert analyzer.is_private_ip("172.16.0.1") is True
        assert analyzer.is_private_ip("8.8.8.8") is False
        assert analyzer.is_private_ip("invalid") is False
