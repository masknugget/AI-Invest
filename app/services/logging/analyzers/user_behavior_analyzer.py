"""
用户行为分析器
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import statistics
import logging

from app.services.logging.models import UserActivityStats, LogTrend

logger = logging.getLogger("webapi")


class UserBehaviorAnalyzer:
    """用户行为分析器"""
    
    def __init__(self, storage):
        self.storage = storage
    
    async def analyze_user_activity(
        self,
        user_id: str,
        username: Optional[str] = None,
        days: int = 30
    ) -> UserActivityStats:
        """
        分析用户活动
        
        Args:
            user_id: 用户ID
            username: 用户名（可选）
            days: 分析周期天数
        """
        start_time = datetime.utcnow() - timedelta(days=days)
        
        # 查询用户日志
        logs = await self.storage.query(
            user_id=user_id,
            start_time=start_time,
            limit=10000
        )
        
        if not logs:
            return UserActivityStats(
                user_id=user_id,
                username=username or user_id,
                period_days=days
            )
        
        # 基础统计
        total_actions = len(logs)
        active_days_set = set()
        action_dist = defaultdict(int)
        feature_usage = defaultdict(int)
        hourly_dist = [0] * 24
        error_count = 0
        success_count = 0
        durations = []
        daily_actions = defaultdict(int)
        unusual_hours_count = 0
        last_active = None
        
        # 非常规时段定义（凌晨0-6点）
        unusual_hours = set(range(0, 6))
        
        for log in logs:
            ts = log.get("timestamp")
            if not ts:
                continue
            
            # 日期统计
            log_date = ts.date() if isinstance(ts, datetime) else datetime.fromisoformat(ts).date()
            active_days_set.add(log_date)
            daily_actions[log_date.isoformat()] += 1
            
            # 时间统计
            hour = ts.hour if isinstance(ts, datetime) else datetime.fromisoformat(ts).hour
            hourly_dist[hour] += 1
            
            # 非常规时段
            if hour in unusual_hours:
                unusual_hours_count += 1
            
            # 动作统计
            action = log.get("action", "unknown")
            action_dist[action] += 1
            
            # 功能使用
            details = log.get("details", {})
            feature = details.get("feature") or details.get("module")
            if feature:
                feature_usage[feature] += 1
            
            # 成功/失败
            if log.get("success", True):
                success_count += 1
            else:
                error_count += 1
            
            # 耗时
            duration = log.get("duration_ms")
            if duration is not None:
                durations.append(duration)
            
            # 最后活跃时间
            if last_active is None or (isinstance(ts, datetime) and ts > last_active):
                last_active = ts
        
        # 计算最活跃时段
        most_active_hour = max(range(24), key=lambda h: hourly_dist[h]) if any(hourly_dist) else None
        
        # 计算最常用功能
        most_used_feature = max(feature_usage.keys(), key=lambda k: feature_usage[k]) if feature_usage else None
        
        # 计算成功率
        total_with_status = success_count + error_count
        success_rate = (success_count / total_with_status * 100) if total_with_status > 0 else 100.0
        
        # 计算平均耗时
        avg_duration = statistics.mean(durations) if durations else 0.0
        
        # 计算日均操作数
        avg_daily = total_actions / days if days > 0 else 0
        
        # 生成每日活动趋势
        daily_activity = [
            {"date": date, "count": count}
            for date, count in sorted(daily_actions.items())
        ]
        
        return UserActivityStats(
            user_id=user_id,
            username=username or user_id,
            period_days=days,
            total_actions=total_actions,
            active_days=len(active_days_set),
            avg_daily_actions=round(avg_daily, 2),
            action_distribution=dict(action_dist),
            feature_usage=dict(feature_usage),
            hourly_distribution=hourly_dist,
            most_used_feature=most_used_feature,
            most_active_hour=most_active_hour,
            success_rate=round(success_rate, 2),
            avg_operation_duration_ms=round(avg_duration, 2),
            unusual_hours_count=unusual_hours_count,
            error_count=error_count,
            last_active=last_active,
            daily_activity=daily_activity
        )
    
    async def compare_users(
        self,
        user_ids: List[str],
        days: int = 30
    ) -> Dict[str, Any]:
        """对比多个用户的行为"""
        stats_list = []
        
        for user_id in user_ids:
            stats = await self.analyze_user_activity(user_id, days=days)
            stats_list.append(stats)
        
        # 计算排名
        rankings = {
            "by_activity": sorted(stats_list, key=lambda s: s.total_actions, reverse=True),
            "by_success_rate": sorted(stats_list, key=lambda s: s.success_rate, reverse=True),
            "by_active_days": sorted(stats_list, key=lambda s: s.active_days, reverse=True),
        }
        
        # 统计汇总
        summary = {
            "total_users": len(user_ids),
            "total_actions": sum(s.total_actions for s in stats_list),
            "avg_actions_per_user": round(sum(s.total_actions for s in stats_list) / len(user_ids), 2) if user_ids else 0,
            "most_active_user": rankings["by_activity"][0].user_id if rankings["by_activity"] else None,
            "highest_success_rate_user": rankings["by_success_rate"][0].user_id if rankings["by_success_rate"] else None,
        }
        
        return {
            "summary": summary,
            "rankings": {
                name: [{"user_id": s.user_id, "value": getattr(s, {
                    "by_activity": "total_actions",
                    "by_success_rate": "success_rate",
                    "by_active_days": "active_days"
                }[name])} for s in ranking]
                for name, ranking in rankings.items()
            },
            "details": [s.model_dump() for s in stats_list]
        }
    
    async def get_active_users(
        self,
        days: int = 7,
        min_actions: int = 1
    ) -> List[Dict[str, Any]]:
        """获取活跃用户列表"""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        # 使用聚合查询
        pipeline = [
            {"$match": {"timestamp": {"$gte": start_time}}},
            {"$group": {
                "_id": "$user_id",
                "action_count": {"$sum": 1},
                "last_active": {"$max": "$timestamp"},
                "username": {"$first": "$username"}
            }},
            {"$match": {"action_count": {"$gte": min_actions}}},
            {"$sort": {"action_count": -1}}
        ]
        
        results = await self.storage.aggregate(pipeline)
        
        return [
            {
                "user_id": r["_id"],
                "username": r.get("username"),
                "action_count": r["action_count"],
                "last_active": r["last_active"]
            }
            for r in results
        ]
    
    async def get_user_session_analysis(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """分析用户会话模式"""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        logs = await self.storage.query(
            user_id=user_id,
            start_time=start_time,
            limit=10000
        )
        
        if not logs:
            return {"user_id": user_id, "sessions": []}
        
        # 按会话ID分组
        sessions = defaultdict(list)
        for log in logs:
            session_id = log.get("session_id") or "unknown"
            sessions[session_id].append(log)
        
        # 分析每个会话
        session_stats = []
        for session_id, session_logs in sessions.items():
            if not session_logs:
                continue
            
            timestamps = [
                log["timestamp"] for log in session_logs
                if log.get("timestamp")
            ]
            
            if not timestamps:
                continue
            
            start = min(timestamps)
            end = max(timestamps)
            duration_minutes = (end - start).total_seconds() / 60 if isinstance(start, datetime) else 0
            
            session_stats.append({
                "session_id": session_id,
                "start_time": start,
                "end_time": end,
                "duration_minutes": round(duration_minutes, 2),
                "action_count": len(session_logs),
                "actions": list(set(log.get("action") for log in session_logs))
            })
        
        # 排序
        session_stats.sort(key=lambda s: s["start_time"], reverse=True)
        
        # 计算会话统计
        durations = [s["duration_minutes"] for s in session_stats]
        
        return {
            "user_id": user_id,
            "total_sessions": len(session_stats),
            "avg_session_duration_minutes": round(statistics.mean(durations), 2) if durations else 0,
            "max_session_duration_minutes": round(max(durations), 2) if durations else 0,
            "sessions": session_stats[:50]  # 限制返回数量
        }


class CohortAnalyzer:
    """用户群组分析（留存分析）"""
    
    def __init__(self, storage):
        self.storage = storage
    
    async def analyze_retention(
        self,
        cohort_days: int = 7,
        periods: int = 4
    ) -> Dict[str, Any]:
        """
        分析用户留存
        
        Args:
            cohort_days: 群组周期天数
            periods: 分析多少个周期
        """
        now = datetime.utcnow()
        cohorts = []
        
        for i in range(periods):
            cohort_start = now - timedelta(days=(i + 1) * cohort_days)
            cohort_end = now - timedelta(days=i * cohort_days)
            
            # 获取该群组的新用户（简化处理：在此期间首次活跃的用户）
            pipeline = [
                {
                    "$match": {
                        "timestamp": {"$gte": cohort_start, "$lt": cohort_end},
                        "user_id": {"$exists": True}
                    }
                },
                {
                    "$group": {
                        "_id": "$user_id",
                        "first_seen": {"$min": "$timestamp"}
                    }
                }
            ]
            
            users = await self.storage.aggregate(pipeline)
            user_ids = [u["_id"] for u in users]
            
            if not user_ids:
                continue
            
            # 计算后续周期的留存
            retention = []
            for p in range(1, periods + 1):
                period_start = cohort_end
                period_end = cohort_end + timedelta(days=cohort_days * p)
                
                # 统计在后续周期活跃的用户
                active_pipeline = [
                    {
                        "$match": {
                            "timestamp": {"$gte": period_start, "$lt": period_end},
                            "user_id": {"$in": user_ids}
                        }
                    },
                    {"$group": {"_id": "$user_id"}}
                ]
                
                active_users = await self.storage.aggregate(active_pipeline)
                retention_rate = len(active_users) / len(user_ids) * 100 if user_ids else 0
                
                retention.append({
                    "period": p,
                    "active_users": len(active_users),
                    "retention_rate": round(retention_rate, 2)
                })
            
            cohorts.append({
                "cohort_start": cohort_start.isoformat(),
                "cohort_end": cohort_end.isoformat(),
                "user_count": len(user_ids),
                "retention": retention
            })
        
        return {
            "cohort_days": cohort_days,
            "periods": periods,
            "cohorts": cohorts
        }
