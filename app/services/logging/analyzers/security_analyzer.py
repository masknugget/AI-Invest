"""
安全分析器
检测安全威胁和异常行为
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict
import ipaddress
import logging

from app.services.logging.models import SecurityStats, LogTrend

logger = logging.getLogger("webapi")


class SecurityAnalyzer:
    """安全分析器"""
    
    def __init__(self, storage):
        self.storage = storage
        
        # 威胁检测规则
        self.threat_rules = {
            "brute_force": {
                "description": "暴力破解攻击",
                "threshold": 5,
                "window_minutes": 5
            },
            "unusual_login_time": {
                "description": "非常规时间登录",
                "unusual_hours": [0, 1, 2, 3, 4, 5]
            },
            "rapid_access": {
                "description": "高频访问",
                "threshold": 100,
                "window_minutes": 1
            },
            "privilege_escalation": {
                "description": "权限提升尝试"
            },
            "data_exfiltration": {
                "description": "数据导出异常",
                "threshold": 1000  # 记录数阈值
            }
        }
    
    async def analyze_security(
        self,
        hours: int = 24
    ) -> SecurityStats:
        """
        安全分析主入口
        
        Args:
            hours: 分析时间窗口（小时）
        """
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        # 基础统计
        threat_stats = await self._get_threat_stats(start_time)
        
        # 认证安全分析
        auth_stats = await self._analyze_auth_security(start_time)
        
        # 检测到的攻击
        detected_attacks = await self._detect_attacks(start_time)
        
        # 威胁趋势
        trend = await self._get_threat_trend(start_time, hours)
        
        return SecurityStats(
            period_hours=hours,
            total_threats=threat_stats["total"],
            critical_threats=threat_stats["critical"],
            high_threats=threat_stats["high"],
            medium_threats=threat_stats["medium"],
            low_threats=threat_stats["low"],
            threat_type_distribution=threat_stats["by_type"],
            top_source_ips=threat_stats["top_ips"],
            blocked_ips=await self._get_blocked_ips_count(),
            failed_login_attempts=auth_stats["failed_attempts"],
            unique_ips_failed_login=auth_stats["unique_failed_ips"],
            suspicious_accounts=auth_stats["suspicious_accounts"],
            detected_attacks=detected_attacks,
            threat_trend=trend
        )
    
    async def _get_threat_stats(self, start_time: datetime) -> Dict[str, Any]:
        """获取威胁统计"""
        pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": start_time},
                    "$or": [
                        {"log_type": "security"},
                        {"level": {"$in": ["error", "critical"]}, "action": {"$regex": "login|auth|access", "$options": "i"}}
                    ]
                }
            },
            {
                "$group": {
                    "_id": {
                        "severity": {"$ifNull": ["$severity", "medium"]},
                        "type": {"$ifNull": ["$threat_type", "unknown"]}
                    },
                    "count": {"$sum": 1},
                    "ips": {"$addToSet": "$source_ip"}
                }
            }
        ]
        
        results = await self.storage.aggregate(pipeline)
        
        stats = {
            "total": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "by_type": defaultdict(int),
            "top_ips": []
        }
        
        ip_counts = defaultdict(int)
        
        for r in results:
            severity = r["_id"].get("severity", "medium")
            threat_type = r["_id"].get("type", "unknown")
            count = r["count"]
            
            stats["total"] += count
            stats[severity] = stats.get(severity, 0) + count
            stats["by_type"][threat_type] += count
            
            for ip in r.get("ips", []):
                if ip:
                    ip_counts[ip] += count
        
        # Top 10 IP
        stats["top_ips"] = [
            {"ip": ip, "count": count}
            for ip, count in sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        stats["by_type"] = dict(stats["by_type"])
        return stats
    
    async def _analyze_auth_security(self, start_time: datetime) -> Dict[str, Any]:
        """分析认证安全"""
        # 失败登录
        failed_logins = await self.storage.query(
            action="user_login",
            start_time=start_time,
            limit=10000
        )
        
        failed_attempts = [log for log in failed_logins if not log.get("success", True)]
        
        # 统计失败来源IP
        failed_ips = defaultdict(int)
        failed_users = defaultdict(int)
        
        for log in failed_attempts:
            ip = log.get("ip_address")
            user = log.get("user_id")
            if ip:
                failed_ips[ip] += 1
            if user:
                failed_users[user] += 1
        
        # 识别可疑账户（多次失败登录）
        suspicious_accounts = [
            user for user, count in failed_users.items()
            if count >= 3
        ]
        
        return {
            "failed_attempts": len(failed_attempts),
            "unique_failed_ips": len(failed_ips),
            "suspicious_accounts": suspicious_accounts,
            "failed_ip_distribution": dict(failed_ips),
            "failed_user_distribution": dict(failed_users)
        }
    
    async def _detect_attacks(self, start_time: datetime) -> List[Dict[str, Any]]:
        """检测攻击模式"""
        attacks = []
        
        # 1. 暴力破解检测
        brute_force = await self._detect_brute_force(start_time)
        attacks.extend(brute_force)
        
        # 2. 高频访问检测
        rapid_access = await self._detect_rapid_access(start_time)
        attacks.extend(rapid_access)
        
        # 3. 非常规时间登录
        unusual_logins = await self._detect_unusual_login_times(start_time)
        attacks.extend(unusual_logins)
        
        # 4. SQL注入/XSS检测（基于日志内容）
        injection_attempts = await self._detect_injection_attempts(start_time)
        attacks.extend(injection_attempts)
        
        # 按严重程度和数量排序
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        attacks.sort(key=lambda a: (severity_order.get(a.get("severity"), 99), -a.get("count", 0)))
        
        return attacks[:50]  # 限制返回数量
    
    async def _detect_brute_force(self, start_time: datetime) -> List[Dict[str, Any]]:
        """检测暴力破解攻击"""
        attacks = []
        window = timedelta(minutes=self.threat_rules["brute_force"]["window_minutes"])
        threshold = self.threat_rules["brute_force"]["threshold"]
        
        # 按IP和时间窗口聚合失败登录
        pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": start_time},
                    "action": {"$regex": "login", "$options": "i"},
                    "$or": [{"success": False}, {"level": "error"}]
                }
            },
            {
                "$group": {
                    "_id": {
                        "ip": "$ip_address",
                        "hour": {"$hour": "$timestamp"}
                    },
                    "count": {"$sum": 1},
                    "users": {"$addToSet": "$user_id"},
                    "first_attempt": {"$min": "$timestamp"},
                    "last_attempt": {"$max": "$timestamp"}
                }
            },
            {"$match": {"count": {"$gte": threshold}}}
        ]
        
        results = await self.storage.aggregate(pipeline)
        
        for r in results:
            attacks.append({
                "type": "brute_force",
                "severity": "high",
                "source_ip": r["_id"].get("ip"),
                "count": r["count"],
                "targeted_users": r.get("users", []),
                "time_range": {
                    "start": r.get("first_attempt"),
                    "end": r.get("last_attempt")
                },
                "description": f"Detected {r['count']} failed login attempts from {r['_id'].get('ip')}",
                "recommendation": "Block IP temporarily and notify affected users"
            })
        
        return attacks
    
    async def _detect_rapid_access(self, start_time: datetime) -> List[Dict[str, Any]]:
        """检测高频访问"""
        attacks = []
        
        pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": start_time},
                    "ip_address": {"$exists": True}
                }
            },
            {
                "$group": {
                    "_id": {
                        "ip": "$ip_address",
                        "minute": {"$minute": "$timestamp"}
                    },
                    "count": {"$sum": 1},
                    "actions": {"$addToSet": "$action"}
                }
            },
            {"$match": {"count": {"$gte": 100}}}
        ]
        
        results = await self.storage.aggregate(pipeline)
        
        for r in results:
            if r["count"] > 500:
                severity = "critical"
            elif r["count"] > 200:
                severity = "high"
            else:
                severity = "medium"
            
            attacks.append({
                "type": "rapid_access",
                "severity": severity,
                "source_ip": r["_id"].get("ip"),
                "count": r["count"],
                "actions": r.get("actions", []),
                "description": f"High frequency access ({r['count']} requests) from {r['_id'].get('ip')}",
                "recommendation": "Implement rate limiting and check for DDoS"
            })
        
        return attacks
    
    async def _detect_unusual_login_times(self, start_time: datetime) -> List[Dict[str, Any]]:
        """检测非常规时间登录"""
        attacks = []
        unusual_hours = self.threat_rules["unusual_login_time"]["unusual_hours"]
        
        pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": start_time},
                    "action": {"$regex": "login", "$options": "i"},
                    "success": True
                }
            },
            {
                "$project": {
                    "hour": {"$hour": "$timestamp"},
                    "user_id": 1,
                    "ip_address": 1,
                    "timestamp": 1
                }
            },
            {
                "$match": {
                    "hour": {"$in": unusual_hours}
                }
            },
            {
                "$group": {
                    "_id": {
                        "user": "$user_id",
                        "ip": "$ip_address"
                    },
                    "count": {"$sum": 1},
                    "logins": {"$push": "$timestamp"}
                }
            }
        ]
        
        results = await self.storage.aggregate(pipeline)
        
        for r in results:
            if r["count"] >= 2:  # 多次非常规时间登录
                attacks.append({
                    "type": "unusual_login_time",
                    "severity": "medium",
                    "user_id": r["_id"].get("user"),
                    "source_ip": r["_id"].get("ip"),
                    "count": r["count"],
                    "timestamps": r.get("logins", [])[:5],
                    "description": f"User {r['_id'].get('user')} logged in {r['count']} times during unusual hours",
                    "recommendation": "Verify user activity and consider additional verification"
                })
        
        return attacks
    
    async def _detect_injection_attempts(self, start_time: datetime) -> List[Dict[str, Any]]:
        """检测注入攻击尝试"""
        attacks = []
        
        # SQL注入特征
        sql_patterns = [
            r"(\%27)|(\')|(\-\-)|(\%23)|(#)",
            r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))",
            r"\w*((\%27)|(\'))((\%6F)|o|(\%4F))((\%72)|r|(\%52))",
            r"((\%27)|(\'))union",
            r"exec(\s|\+)+(s|x)p\w+",
            r"UNION\s+SELECT",
            r"INSERT\s+INTO",
            r"DELETE\s+FROM"
        ]
        
        # XSS特征
        xss_patterns = [
            r"<script[^>]*>[\s\S]*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe",
            r"<object",
            r"<embed"
        ]
        
        # 查询可能的攻击日志
        suspicious_logs = await self.storage.query(
            level="error",
            start_time=start_time,
            limit=1000
        )
        
        import re
        
        sql_regex = [re.compile(p, re.IGNORECASE) for p in sql_patterns]
        xss_regex = [re.compile(p, re.IGNORECASE) for p in xss_patterns]
        
        detected_ips = defaultdict(lambda: {"sql": 0, "xss": 0, "logs": []})
        
        for log in suspicious_logs:
            message = str(log.get("message", ""))
            details = str(log.get("details", ""))
            content = message + " " + details
            ip = log.get("ip_address") or log.get("source_ip")
            
            if not ip:
                continue
            
            # 检测SQL注入
            for regex in sql_regex:
                if regex.search(content):
                    detected_ips[ip]["sql"] += 1
                    detected_ips[ip]["logs"].append(log.get("timestamp"))
                    break
            
            # 检测XSS
            for regex in xss_regex:
                if regex.search(content):
                    detected_ips[ip]["xss"] += 1
                    detected_ips[ip]["logs"].append(log.get("timestamp"))
                    break
        
        # 生成攻击报告
        for ip, data in detected_ips.items():
            if data["sql"] > 0:
                attacks.append({
                    "type": "sql_injection_attempt",
                    "severity": "high",
                    "source_ip": ip,
                    "count": data["sql"],
                    "description": f"Possible SQL injection attempts detected from {ip}",
                    "recommendation": "Block IP and review WAF rules"
                })
            
            if data["xss"] > 0:
                attacks.append({
                    "type": "xss_attempt",
                    "severity": "high",
                    "source_ip": ip,
                    "count": data["xss"],
                    "description": f"Possible XSS attempts detected from {ip}",
                    "recommendation": "Block IP and implement CSP headers"
                })
        
        return attacks
    
    async def _get_blocked_ips_count(self) -> int:
        """获取已阻止的IP数量"""
        # 这里应该从防火墙或阻止列表中查询
        # 简化实现，从安全日志中统计
        return 0
    
    async def _get_threat_trend(self, start_time: datetime, hours: int) -> List[LogTrend]:
        """获取威胁趋势"""
        interval = max(1, hours // 24)  # 最多24个数据点
        
        pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": start_time},
                    "$or": [
                        {"log_type": "security"},
                        {"level": {"$in": ["error", "critical"]}}
                    ]
                }
            },
            {
                "$group": {
                    "_id": {
                        "$subtract": [
                            {"$toLong": "$timestamp"},
                            {"$mod": [{"$toLong": "$timestamp"}, 1000 * 60 * interval]}
                        ]
                    },
                    "count": {"$sum": 1},
                    "error_count": {
                        "$sum": {"$cond": [{"$eq": ["$level", "error"]}, 1, 0]}
                    }
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        results = await self.storage.aggregate(pipeline)
        
        return [
            LogTrend(
                timestamp=datetime.fromtimestamp(r["_id"] / 1000),
                count=r["count"],
                error_count=r.get("error_count", 0)
            )
            for r in results
        ]
    
    def is_private_ip(self, ip: str) -> bool:
        """判断是否是私有IP"""
        try:
            addr = ipaddress.ip_address(ip)
            return addr.is_private
        except ValueError:
            return False
    
    async def generate_security_report(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """生成安全报告"""
        hours = days * 24
        
        # 当前周期
        current_stats = await self.analyze_security(hours=hours)
        
        # 上一周期（对比）
        previous_start = datetime.utcnow() - timedelta(hours=hours * 2)
        previous_end = datetime.utcnow() - timedelta(hours=hours)
        
        previous_logs = await self.storage.query(
            start_time=previous_start,
            end_time=previous_end,
            limit=10000
        )
        
        previous_threats = len([l for l in previous_logs if l.get("log_type") == "security"])
        
        # 趋势分析
        trend = "stable"
        if current_stats.total_threats > previous_threats * 1.2:
            trend = "increasing"
        elif current_stats.total_threats < previous_threats * 0.8:
            trend = "decreasing"
        
        return {
            "period_days": days,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "threat_level": self._calculate_threat_level(current_stats),
                "trend": trend,
                "total_threats": current_stats.total_threats,
                "previous_period_threats": previous_threats,
                "change_percent": round(
                    (current_stats.total_threats - previous_threats) / previous_threats * 100, 2
                ) if previous_threats > 0 else 0
            },
            "details": current_stats.model_dump(),
            "recommendations": self._generate_recommendations(current_stats)
        }
    
    def _calculate_threat_level(self, stats: SecurityStats) -> str:
        """计算威胁等级"""
        score = 0
        score += stats.critical_threats * 10
        score += stats.high_threats * 5
        score += stats.medium_threats * 2
        score += stats.low_threats * 1
        
        if score >= 50:
            return "critical"
        elif score >= 20:
            return "high"
        elif score >= 5:
            return "medium"
        else:
            return "low"
    
    def _generate_recommendations(self, stats: SecurityStats) -> List[str]:
        """生成安全建议"""
        recommendations = []
        
        if stats.critical_threats > 0:
            recommendations.append("立即处理关键安全威胁，启动应急响应流程")
        
        if stats.failed_login_attempts > 20:
            recommendations.append("增加登录失败限制，考虑实施验证码或MFA")
        
        if stats.suspicious_accounts:
            recommendations.append(f"审查可疑账户活动: {', '.join(stats.suspicious_accounts[:5])}")
        
        if stats.blocked_ips < len(stats.top_source_ips) * 0.3:
            recommendations.append("建议加强IP封锁策略")
        
        if not recommendations:
            recommendations.append("当前安全状况良好，继续保持监控")
        
        return recommendations
