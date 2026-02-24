"""
异常检测器
基于统计和机器学习的异常检测
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import statistics
import logging
import math

logger = logging.getLogger("webapi")


class AnomalyDetector:
    """异常检测器"""
    
    def __init__(self, storage):
        self.storage = storage
        self._baseline_stats: Dict[str, Dict] = {}
    
    async def detect_anomalies(
        self,
        user_id: Optional[str] = None,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        检测异常
        
        Args:
            user_id: 指定用户，None则检测所有用户
            hours: 检测时间窗口
        """
        anomalies = []
        
        # 1. 行为模式异常
        behavior_anomalies = await self._detect_behavior_anomalies(user_id, hours)
        anomalies.extend(behavior_anomalies)
        
        # 2. 时间模式异常
        time_anomalies = await self._detect_time_anomalies(user_id, hours)
        anomalies.extend(time_anomalies)
        
        # 3. 频率异常
        frequency_anomalies = await self._detect_frequency_anomalies(user_id, hours)
        anomalies.extend(frequency_anomalies)
        
        # 4. 地理位置异常（如果有IP信息）
        geo_anomalies = await self._detect_geo_anomalies(user_id, hours)
        anomalies.extend(geo_anomalies)
        
        # 按严重程度排序
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        anomalies.sort(key=lambda a: severity_order.get(a.get("severity"), 99))
        
        return anomalies
    
    async def _detect_behavior_anomalies(
        self,
        user_id: Optional[str],
        hours: int
    ) -> List[Dict[str, Any]]:
        """检测行为模式异常"""
        anomalies = []
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        # 获取历史基线（7天）
        baseline_end = start_time
        baseline_start = baseline_end - timedelta(days=7)
        
        target_users = [user_id] if user_id else await self._get_active_users(start_time)
        
        for uid in target_users:
            # 当前行为
            current_logs = await self.storage.query(
                user_id=uid,
                start_time=start_time,
                limit=1000
            )
            
            # 历史基线
            baseline_logs = await self.storage.query(
                user_id=uid,
                start_time=baseline_start,
                end_time=baseline_end,
                limit=10000
            )
            
            if len(baseline_logs) < 10:  # 基线数据不足
                continue
            
            # 对比动作分布
            current_actions = defaultdict(int)
            baseline_actions = defaultdict(int)
            
            for log in current_logs:
                current_actions[log.get("action", "unknown")] += 1
            
            for log in baseline_logs:
                baseline_actions[log.get("action", "unknown")] += 1
            
            # 检测新动作类型
            avg_baseline_total = len(baseline_logs) / 7  # 日均
            current_total = len(current_logs)
            
            # 检测总量异常
            if avg_baseline_total > 0:
                ratio = current_total / avg_baseline_total * (24 / hours)
                
                if ratio > 3:  # 活动量激增
                    anomalies.append({
                        "type": "activity_spike",
                        "severity": "medium",
                        "user_id": uid,
                        "description": f"用户活动量激增 {ratio:.1f} 倍",
                        "details": {
                            "current_count": current_total,
                            "baseline_avg": round(avg_baseline_total, 2),
                            "ratio": round(ratio, 2)
                        },
                        "timestamp": datetime.utcnow().isoformat()
                    })
                elif ratio < 0.1 and avg_baseline_total > 10:  # 活动量骤降
                    anomalies.append({
                        "type": "activity_drop",
                        "severity": "low",
                        "user_id": uid,
                        "description": f"用户活动量显著下降",
                        "details": {
                            "current_count": current_total,
                            "baseline_avg": round(avg_baseline_total, 2),
                            "ratio": round(ratio, 2)
                        },
                        "timestamp": datetime.utcnow().isoformat()
                    })
            
            # 检测新动作
            for action in current_actions:
                if action not in baseline_actions:
                    anomalies.append({
                        "type": "new_action_pattern",
                        "severity": "low",
                        "user_id": uid,
                        "description": f"用户首次执行动作: {action}",
                        "details": {
                            "action": action,
                            "count": current_actions[action]
                        },
                        "timestamp": datetime.utcnow().isoformat()
                    })
        
        return anomalies
    
    async def _detect_time_anomalies(
        self,
        user_id: Optional[str],
        hours: int
    ) -> List[Dict[str, Any]]:
        """检测时间模式异常"""
        anomalies = []
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        # 历史基线（30天）
        baseline_start = start_time - timedelta(days=30)
        
        target_users = [user_id] if user_id else await self._get_active_users(start_time)
        
        for uid in target_users:
            # 获取历史活跃时段
            baseline_logs = await self.storage.query(
                user_id=uid,
                start_time=baseline_start,
                end_time=start_time,
                limit=5000
            )
            
            if len(baseline_logs) < 20:
                continue
            
            # 计算历史活跃时段分布
            hour_distribution = [0] * 24
            for log in baseline_logs:
                ts = log.get("timestamp")
                if ts:
                    hour = ts.hour if isinstance(ts, datetime) else datetime.fromisoformat(ts).hour
                    hour_distribution[hour] += 1
            
            # 确定常用时段（活跃度 > 平均的时段）
            avg_activity = sum(hour_distribution) / 24
            usual_hours = {h for h, count in enumerate(hour_distribution) if count > avg_activity * 0.3}
            
            # 检查当前时段
            current_logs = await self.storage.query(
                user_id=uid,
                start_time=start_time,
                limit=1000
            )
            
            unusual_logins = []
            for log in current_logs:
                ts = log.get("timestamp")
                if not ts:
                    continue
                
                hour = ts.hour if isinstance(ts, datetime) else datetime.fromisoformat(ts).hour
                
                # 深夜登录 (0-5点)
                if hour in [0, 1, 2, 3, 4, 5]:
                    unusual_logins.append(log)
                # 非常用时段
                elif usual_hours and hour not in usual_hours:
                    unusual_logins.append(log)
            
            if len(unusual_logins) >= 2:
                anomalies.append({
                    "type": "unusual_time_activity",
                    "severity": "medium",
                    "user_id": uid,
                    "description": f"用户在非常规时段有 {len(unusual_logins)} 次活动",
                    "details": {
                        "count": len(unusual_logins),
                        "usual_hours": sorted(usual_hours),
                        "samples": [log.get("timestamp") for log in unusual_logins[:3]]
                    },
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        return anomalies
    
    async def _detect_frequency_anomalies(
        self,
        user_id: Optional[str],
        hours: int
    ) -> List[Dict[str, Any]]:
        """检测频率异常"""
        anomalies = []
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        # 查询登录失败频率
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
                        "user": "$user_id",
                        "ip": "$ip_address",
                        "hour": {"$hour": "$timestamp"}
                    },
                    "count": {"$sum": 1},
                    "first_attempt": {"$min": "$timestamp"},
                    "last_attempt": {"$max": "$timestamp"}
                }
            },
            {"$match": {"count": {"$gte": 5}}}
        ]
        
        if user_id:
            pipeline[0]["$match"]["user_id"] = user_id
        
        results = await self.storage.aggregate(pipeline)
        
        for r in results:
            count = r["count"]
            severity = "medium"
            if count >= 20:
                severity = "critical"
            elif count >= 10:
                severity = "high"
            
            anomalies.append({
                "type": "high_frequency_failures",
                "severity": severity,
                "user_id": r["_id"].get("user"),
                "source_ip": r["_id"].get("ip"),
                "description": f"高频失败尝试: {count} 次",
                "details": {
                    "count": count,
                    "time_window": "hour",
                    "first_attempt": r.get("first_attempt"),
                    "last_attempt": r.get("last_attempt")
                },
                "timestamp": datetime.utcnow().isoformat()
            })
        
        return anomalies
    
    async def _detect_geo_anomalies(
        self,
        user_id: Optional[str],
        hours: int
    ) -> List[Dict[str, Any]]:
        """检测地理位置异常（基于IP变化）"""
        anomalies = []
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        # 历史基线
        baseline_start = start_time - timedelta(days=30)
        
        target_users = [user_id] if user_id else await self._get_active_users(start_time)
        
        for uid in target_users:
            # 获取历史IP
            baseline_logs = await self.storage.query(
                user_id=uid,
                start_time=baseline_start,
                end_time=start_time,
                limit=1000
            )
            
            historical_ips = set()
            for log in baseline_logs:
                ip = log.get("ip_address")
                if ip:
                    historical_ips.add(ip)
            
            if len(historical_ips) < 1:
                continue
            
            # 检查当前IP
            current_logs = await self.storage.query(
                user_id=uid,
                start_time=start_time,
                limit=100
            )
            
            current_ips = set()
            for log in current_logs:
                ip = log.get("ip_address")
                if ip:
                    current_ips.add(ip)
            
            # 检测新IP
            new_ips = current_ips - historical_ips
            if new_ips:
                anomalies.append({
                    "type": "new_ip_detected",
                    "severity": "low",
                    "user_id": uid,
                    "description": f"用户从新IP地址登录",
                    "details": {
                        "new_ips": list(new_ips),
                        "historical_ips": list(historical_ips)[:5]
                    },
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        return anomalies
    
    async def _get_active_users(self, since: datetime, limit: int = 100) -> List[str]:
        """获取活跃用户列表"""
        pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": since},
                    "user_id": {"$exists": True}
                }
            },
            {"$group": {"_id": "$user_id"}},
            {"$limit": limit}
        ]
        
        results = await self.storage.aggregate(pipeline)
        return [r["_id"] for r in results if r["_id"]]
    
    async def build_baseline(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        为用户建立行为基线
        
        Args:
            user_id: 用户ID
            days: 基线数据天数
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        logs = await self.storage.query(
            user_id=user_id,
            start_time=start_time,
            limit=10000
        )
        
        if not logs:
            return {}
        
        # 动作分布
        action_dist = defaultdict(int)
        hour_dist = [0] * 24
        weekday_dist = [0] * 7
        durations = []
        
        for log in logs:
            action_dist[log.get("action", "unknown")] += 1
            
            ts = log.get("timestamp")
            if ts:
                if isinstance(ts, datetime):
                    hour_dist[ts.hour] += 1
                    weekday_dist[ts.weekday()] += 1
                else:
                    dt = datetime.fromisoformat(ts)
                    hour_dist[dt.hour] += 1
                    weekday_dist[dt.weekday()] += 1
            
            duration = log.get("duration_ms")
            if duration is not None:
                durations.append(duration)
        
        baseline = {
            "user_id": user_id,
            "period_days": days,
            "total_actions": len(logs),
            "action_distribution": dict(action_dist),
            "hourly_distribution": hour_dist,
            "weekday_distribution": weekday_dist,
            "usual_actions": list(action_dist.keys()),
            "active_hours": [h for h, c in enumerate(hour_dist) if c > sum(hour_dist) / 24 * 0.5],
            "avg_duration_ms": statistics.mean(durations) if durations else 0,
            "std_duration_ms": statistics.stdev(durations) if len(durations) > 1 else 0,
            "created_at": datetime.utcnow().isoformat()
        }
        
        self._baseline_stats[user_id] = baseline
        return baseline
    
    def detect_statistical_anomaly(
        self,
        value: float,
        mean: float,
        std: float,
        threshold: float = 3.0
    ) -> Tuple[bool, float]:
        """
        基于统计的异常检测（3-sigma原则）
        
        Returns:
            (是否异常, z-score)
        """
        if std == 0:
            return value != mean, 0
        
        z_score = abs(value - mean) / std
        return z_score > threshold, z_score
