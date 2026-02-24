"""
日志统计模型
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class LogTrend(BaseModel):
    """日志趋势数据点"""
    timestamp: datetime = Field(..., description="时间戳")
    count: int = Field(0, description="日志数量")
    error_count: int = Field(0, description="错误数量")
    avg_duration_ms: Optional[float] = Field(None, description="平均耗时")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "timestamp": "2026-02-23T10:00:00",
                "count": 150,
                "error_count": 2,
                "avg_duration_ms": 45.5
            }
        }
    }


class LogStats(BaseModel):
    """日志统计基础模型"""
    period_days: int = Field(7, description="统计周期天数")
    total_logs: int = Field(0, description="总日志数")
    error_logs: int = Field(0, description="错误日志数")
    warning_logs: int = Field(0, description="警告日志数")
    info_logs: int = Field(0, description="信息日志数")
    
    # 分布统计
    level_distribution: Dict[str, int] = Field(default_factory=dict, description="级别分布")
    type_distribution: Dict[str, int] = Field(default_factory=dict, description="类型分布")
    hourly_distribution: List[int] = Field(default_factory=list, description="24小时分布")
    daily_distribution: Dict[str, int] = Field(default_factory=dict, description="每日分布")
    
    # 趋势
    trends: List[LogTrend] = Field(default_factory=list, description="趋势数据")
    
    # 计算属性
    error_rate: float = Field(0.0, description="错误率")
    avg_logs_per_day: float = Field(0.0, description="日均日志数")
    
    def calculate_derived(self):
        """计算派生指标"""
        if self.total_logs > 0:
            self.error_rate = round(self.error_logs / self.total_logs * 100, 2)
        if self.period_days > 0:
            self.avg_logs_per_day = round(self.total_logs / self.period_days, 2)


class UserActivityStats(BaseModel):
    """用户活动统计"""
    user_id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    period_days: int = Field(30, description="统计周期天数")
    
    # 活动指标
    total_actions: int = Field(0, description="总操作数")
    active_days: int = Field(0, description="活跃天数")
    avg_daily_actions: float = Field(0.0, description="日均操作数")
    
    # 分布
    action_distribution: Dict[str, int] = Field(default_factory=dict, description="操作类型分布")
    feature_usage: Dict[str, int] = Field(default_factory=dict, description="功能使用分布")
    hourly_distribution: List[int] = Field(default_factory=list, description="24小时活跃分布")
    
    # 偏好
    most_used_feature: Optional[str] = Field(None, description="最常用功能")
    most_active_hour: Optional[int] = Field(None, description="最活跃时段")
    
    # 质量
    success_rate: float = Field(100.0, description="操作成功率")
    avg_operation_duration_ms: float = Field(0.0, description="平均操作耗时")
    
    # 风险
    unusual_hours_count: int = Field(0, description="非常规时段操作次数")
    error_count: int = Field(0, description="错误次数")
    last_active: Optional[datetime] = Field(None, description="最后活跃时间")
    
    # 趋势
    daily_activity: List[Dict[str, Any]] = Field(default_factory=list, description="每日活动趋势")


class SecurityStats(BaseModel):
    """安全统计"""
    period_hours: int = Field(24, description="统计周期小时数")
    
    # 威胁概览
    total_threats: int = Field(0, description="威胁总数")
    critical_threats: int = Field(0, description="严重威胁数")
    high_threats: int = Field(0, description="高风险威胁数")
    medium_threats: int = Field(0, description="中风险威胁数")
    low_threats: int = Field(0, description="低风险威胁数")
    
    # 威胁类型分布
    threat_type_distribution: Dict[str, int] = Field(default_factory=dict, description="威胁类型分布")
    
    # 攻击来源
    top_source_ips: List[Dict[str, Any]] = Field(default_factory=list, description="Top攻击源IP")
    blocked_ips: int = Field(0, description="已阻止IP数")
    
    # 认证安全
    failed_login_attempts: int = Field(0, description="失败登录尝试")
    unique_ips_failed_login: int = Field(0, description="失败登录独立IP数")
    suspicious_accounts: List[str] = Field(default_factory=list, description="可疑账户列表")
    
    # 检测到的攻击
    detected_attacks: List[Dict[str, Any]] = Field(default_factory=list, description="检测到的攻击")
    
    # 趋势
    threat_trend: List[LogTrend] = Field(default_factory=list, description="威胁趋势")


class SystemHealthStats(BaseModel):
    """系统健康统计"""
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="统计时间")
    
    # 性能指标
    avg_response_time_ms: float = Field(0.0, description="平均响应时间")
    p95_response_time_ms: float = Field(0.0, description="P95响应时间")
    p99_response_time_ms: float = Field(0.0, description="P99响应时间")
    
    # 吞吐量
    requests_per_minute: float = Field(0.0, description="每分钟请求数")
    logs_per_minute: float = Field(0.0, description="每分钟日志数")
    
    # 错误率
    error_rate: float = Field(0.0, description="错误率")
    error_rate_trend: str = Field("stable", description="错误率趋势: up/down/stable")
    
    # 资源使用
    avg_cpu_percent: float = Field(0.0, description="平均CPU使用率")
    avg_memory_percent: float = Field(0.0, description="平均内存使用率")
    disk_usage_percent: float = Field(0.0, description="磁盘使用率")
    
    # 组件状态
    component_status: Dict[str, str] = Field(default_factory=dict, description="组件状态")
    unhealthy_components: List[str] = Field(default_factory=list, description="不健康组件")
    
    # 日志存储
    total_logs_stored: int = Field(0, description="存储的日志总数")
    storage_size_mb: float = Field(0.0, description="存储大小(MB)")
    archived_logs_count: int = Field(0, description="已归档日志数")
    
    # 队列状态
    log_queue_size: int = Field(0, description="日志队列大小")
    queue_processing_rate: float = Field(0.0, description="队列处理速率")
    
    # 健康评分
    health_score: int = Field(100, ge=0, le=100, description="健康评分")
    status: str = Field("healthy", description="状态: healthy/warning/critical")


class ExportResult(BaseModel):
    """日志导出结果"""
    success: bool = Field(True, description="是否成功")
    file_path: Optional[str] = Field(None, description="文件路径")
    file_name: Optional[str] = Field(None, description="文件名")
    file_size_bytes: int = Field(0, description="文件大小")
    record_count: int = Field(0, description="记录数")
    format: str = Field("csv", description="导出格式")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    download_url: Optional[str] = Field(None, description="下载链接")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
