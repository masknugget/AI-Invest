"""
性能分析器
分析系统性能指标
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict
import statistics
import logging

from app.services.logging.models import SystemHealthStats, LogTrend

logger = logging.getLogger("webapi")


class PerformanceAnalyzer:
    """性能分析器"""
    
    def __init__(self, storage):
        self.storage = storage
    
    async def analyze_system_health(
        self,
        hours: int = 24
    ) -> SystemHealthStats:
        """分析系统健康状态"""
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        # 查询系统日志和访问日志
        logs = await self.storage.query(
            log_type="access",
            start_time=start_time,
            limit=50000
        )
        
        if not logs:
            return SystemHealthStats()
        
        # 响应时间分析
        durations = []
        status_codes = defaultdict(int)
        hourly_counts = defaultdict(int)
        path_durations = defaultdict(list)
        error_logs = []
        
        for log in logs:
            # 响应时间
            duration = log.get("duration_ms")
            if duration is not None:
                durations.append(duration)
            
            # 状态码
            status = log.get("status_code") or log.get("details", {}).get("status_code")
            if status:
                status_codes[status] += 1
            
            # 小时分布
            ts = log.get("timestamp")
            if ts:
                hour = ts.hour if isinstance(ts, datetime) else datetime.fromisoformat(ts).hour
                hourly_counts[hour] += 1
            
            # 路径耗时
            path = log.get("path")
            if path and duration is not None:
                path_durations[path].append(duration)
            
            # 错误日志
            if status and status >= 400:
                error_logs.append(log)
        
        # 计算统计指标
        avg_duration = statistics.mean(durations) if durations else 0
        p95_duration = self._percentile(durations, 95) if durations else 0
        p99_duration = self._percentile(durations, 99) if durations else 0
        
        # 错误率
        total_requests = len(logs)
        error_count = sum(1 for log in logs if log.get("status_code", 200) >= 400)
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
        
        # 吞吐量
        requests_per_minute = total_requests / (hours * 60)
        
        # 慢查询分析
        slow_paths = [
            {
                "path": path,
                "avg_duration_ms": round(statistics.mean(times), 2),
                "p95_duration_ms": round(self._percentile(times, 95), 2),
                "count": len(times)
            }
            for path, times in path_durations.items()
            if len(times) >= 5
        ]
        slow_paths.sort(key=lambda x: x["avg_duration_ms"], reverse=True)
        
        # 健康评分
        health_score = self._calculate_health_score(
            error_rate=error_rate,
            avg_duration=avg_duration,
            p95_duration=p95_duration
        )
        
        status = "healthy"
        if health_score < 60:
            status = "critical"
        elif health_score < 80:
            status = "warning"
        
        return SystemHealthStats(
            timestamp=datetime.utcnow(),
            avg_response_time_ms=round(avg_duration, 2),
            p95_response_time_ms=round(p95_duration, 2),
            p99_response_time_ms=round(p99_duration, 2),
            requests_per_minute=round(requests_per_minute, 2),
            logs_per_minute=round(total_requests / (hours * 60), 2),
            error_rate=round(error_rate, 2),
            status_code_distribution=dict(status_codes),
            hourly_distribution=[hourly_counts.get(h, 0) for h in range(24)],
            top_slow_paths=slow_paths[:10],
            health_score=health_score,
            status=status
        )
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """计算百分位数"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def _calculate_health_score(
        self,
        error_rate: float,
        avg_duration: float,
        p95_duration: float
    ) -> int:
        """计算健康评分 (0-100)"""
        score = 100
        
        # 错误率扣分
        if error_rate > 5:
            score -= 30
        elif error_rate > 1:
            score -= 15
        elif error_rate > 0.1:
            score -= 5
        
        # 响应时间扣分
        if avg_duration > 1000:
            score -= 20
        elif avg_duration > 500:
            score -= 10
        
        if p95_duration > 2000:
            score -= 20
        elif p95_duration > 1000:
            score -= 10
        
        return max(0, score)
    
    async def get_performance_trends(
        self,
        days: int = 7
    ) -> List[LogTrend]:
        """获取性能趋势"""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": start_time},
                    "log_type": "access"
                }
            },
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}}
                    },
                    "count": {"$sum": 1},
                    "avg_duration": {"$avg": "$duration_ms"},
                    "error_count": {
                        "$sum": {
                            "$cond": [
                                {"$gte": [{"$ifNull": ["$status_code", 200]}, 400]},
                                1,
                                0
                            ]
                        }
                    }
                }
            },
            {"$sort": {"_id.date": 1}}
        ]
        
        results = await self.storage.aggregate(pipeline)
        
        return [
            LogTrend(
                timestamp=datetime.strptime(r["_id"]["date"], "%Y-%m-%d"),
                count=r["count"],
                error_count=r.get("error_count", 0),
                avg_duration_ms=round(r.get("avg_duration", 0), 2)
            )
            for r in results
        ]
    
    async def analyze_endpoint_performance(
        self,
        path_pattern: Optional[str] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """分析端点性能"""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        match_stage = {
            "timestamp": {"$gte": start_time},
            "log_type": "access"
        }
        
        if path_pattern:
            match_stage["path"] = {"$regex": path_pattern}
        
        pipeline = [
            {"$match": match_stage},
            {
                "$group": {
                    "_id": "$path",
                    "count": {"$sum": 1},
                    "avg_duration_ms": {"$avg": "$duration_ms"},
                    "min_duration_ms": {"$min": "$duration_ms"},
                    "max_duration_ms": {"$max": "$duration_ms"},
                    "error_count": {
                        "$sum": {
                            "$cond": [
                                {"$gte": [{"$ifNull": ["$status_code", 200]}, 400]},
                                1,
                                0
                            ]
                        }
                    },
                    "p95_duration_ms": {
                        "$percentile": {
                            "input": "$duration_ms",
                            "p": [0.95]
                        }
                    }
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 50}
        ]
        
        # 注意：MongoDB 5.0+ 才支持 $percentile，这里需要适配
        # 简化版本
        pipeline = [
            {"$match": match_stage},
            {
                "$group": {
                    "_id": "$path",
                    "count": {"$sum": 1},
                    "avg_duration_ms": {"$avg": "$duration_ms"},
                    "min_duration_ms": {"$min": "$duration_ms"},
                    "max_duration_ms": {"$max": "$duration_ms"},
                    "error_count": {
                        "$sum": {
                            "$cond": [
                                {"$gte": [{"$ifNull": ["$status_code", 200]}, 400]},
                                1,
                                0
                            ]
                        }
                    },
                    "durations": {"$push": "$duration_ms"}
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 50}
        ]
        
        results = await self.storage.aggregate(pipeline)
        
        # 计算P95
        analyzed = []
        for r in results:
            durations = [d for d in r.get("durations", []) if d is not None]
            p95 = self._percentile(durations, 95) if durations else 0
            
            analyzed.append({
                "path": r["_id"],
                "request_count": r["count"],
                "avg_duration_ms": round(r.get("avg_duration_ms", 0), 2),
                "min_duration_ms": r.get("min_duration_ms"),
                "max_duration_ms": r.get("max_duration_ms"),
                "p95_duration_ms": round(p95, 2),
                "error_count": r.get("error_count", 0),
                "error_rate": round(r.get("error_count", 0) / r["count"] * 100, 2) if r["count"] > 0 else 0
            })
        
        return analyzed
    
    async def get_error_analysis(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """错误分析"""
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        # 查询错误日志
        error_logs = await self.storage.query(
            level="error",
            start_time=start_time,
            limit=1000
        )
        
        if not error_logs:
            return {
                "total_errors": 0,
                "error_types": [],
                "top_errors": []
            }
        
        # 按错误类型分组
        error_types = defaultdict(lambda: {"count": 0, "latest": None})
        
        for log in error_logs:
            error_type = log.get("error_type") or log.get("action", "unknown")
            error_types[error_type]["count"] += 1
            
            ts = log.get("timestamp")
            if ts and (error_types[error_type]["latest"] is None or ts > error_types[error_type]["latest"]):
                error_types[error_type]["latest"] = ts
        
        # 排序
        sorted_errors = sorted(
            [{"type": k, **v} for k, v in error_types.items()],
            key=lambda x: x["count"],
            reverse=True
        )
        
        return {
            "period_hours": hours,
            "total_errors": len(error_logs),
            "error_types": sorted_errors[:20],
            "top_errors": error_logs[:10]
        }
    
    async def get_resource_usage_trends(
        self,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """获取资源使用趋势"""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        logs = await self.storage.query(
            log_type="system",
            start_time=start_time,
            limit=10000
        )
        
        # 按天聚合
        daily_stats = defaultdict(lambda: {
            "cpu_values": [],
            "memory_values": [],
            "disk_values": []
        })
        
        for log in logs:
            ts = log.get("timestamp")
            if not ts:
                continue
            
            date = ts.date() if isinstance(ts, datetime) else datetime.fromisoformat(ts).date()
            date_str = date.isoformat()
            
            cpu = log.get("cpu_percent")
            memory = log.get("memory_percent")
            disk = log.get("disk_usage_percent")
            
            if cpu is not None:
                daily_stats[date_str]["cpu_values"].append(cpu)
            if memory is not None:
                daily_stats[date_str]["memory_values"].append(memory)
            if disk is not None:
                daily_stats[date_str]["disk_values"].append(disk)
        
        # 计算平均值
        trends = []
        for date, values in sorted(daily_stats.items()):
            trends.append({
                "date": date,
                "avg_cpu_percent": round(statistics.mean(values["cpu_values"]), 2) if values["cpu_values"] else None,
                "avg_memory_percent": round(statistics.mean(values["memory_values"]), 2) if values["memory_values"] else None,
                "avg_disk_percent": round(statistics.mean(values["disk_values"]), 2) if values["disk_values"] else None,
                "max_cpu_percent": max(values["cpu_values"]) if values["cpu_values"] else None,
                "max_memory_percent": max(values["memory_values"]) if values["memory_values"] else None
            })
        
        return trends
