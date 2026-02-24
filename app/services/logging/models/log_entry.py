"""
日志条目数据模型
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_serializer
from bson import ObjectId

from .log_types import LogLevel, LogType


class LogEntry(BaseModel):
    """统一日志条目模型 - 基础类"""
    
    # 主键
    id: Optional[str] = Field(None, description="日志ID")
    
    # 日志分类
    log_type: LogType = Field(..., description="日志类型")
    level: LogLevel = Field(LogLevel.INFO, description="日志级别")
    
    # 用户标识
    user_id: Optional[str] = Field(None, description="用户ID")
    username: Optional[str] = Field(None, description="用户名")
    session_id: Optional[str] = Field(None, description="会话ID")
    
    # 请求上下文
    request_id: Optional[str] = Field(None, description="请求ID")
    trace_id: Optional[str] = Field(None, description="追踪ID（分布式追踪）")
    ip_address: Optional[str] = Field(None, description="IP地址")
    user_agent: Optional[str] = Field(None, description="User-Agent")
    
    # 内容
    action: str = Field(..., description="操作/事件名称")
    message: str = Field(..., description="日志消息")
    details: Dict[str, Any] = Field(default_factory=dict, description="详细信息")
    tags: List[str] = Field(default_factory=list, description="标签")
    
    # 性能指标
    duration_ms: Optional[int] = Field(None, description="耗时(毫秒)")
    memory_mb: Optional[float] = Field(None, description="内存使用(MB)")
    
    # 代码位置
    service: str = Field("tradingagents", description="服务名称")
    module: Optional[str] = Field(None, description="模块名")
    function: Optional[str] = Field(None, description="函数名")
    line_no: Optional[int] = Field(None, description="行号")
    
    # 时间戳
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="事件发生时间")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="记录创建时间")
    
    # 归档状态
    archived: bool = Field(False, description="是否已归档")
    archive_date: Optional[datetime] = Field(None, description="归档日期")
    
    @field_serializer('timestamp', 'created_at', 'archive_date')
    def serialize_datetime(self, dt: Optional[datetime], _info) -> Optional[str]:
        """序列化 datetime 为 ISO 8601 格式"""
        if dt:
            return dt.isoformat()
        return None
    
    def to_mongo_doc(self) -> Dict[str, Any]:
        """转换为 MongoDB 文档格式"""
        data = self.model_dump(exclude={'id'})
        # 移除 None 值以节省存储空间
        return {k: v for k, v in data.items() if v is not None}
    
    @classmethod
    def from_mongo_doc(cls, doc: Dict[str, Any]) -> "LogEntry":
        """从 MongoDB 文档创建实例"""
        if doc and "_id" in doc:
            doc["id"] = str(doc.pop("_id"))
        return cls(**doc)
    
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "log_type": "operation",
                "level": "info",
                "user_id": "admin",
                "username": "admin",
                "action": "stock_analysis",
                "message": "创建股票分析任务成功",
                "details": {"stock_code": "000001.SZ"},
                "timestamp": "2026-02-23T10:00:00"
            }
        }
    }


class AuditLogEntry(LogEntry):
    """审计日志条目"""
    
    log_type: LogType = Field(LogType.AUDIT, description="日志类型")
    
    audit_type: str = Field(..., description="审计类型")
    resource_type: Optional[str] = Field(None, description="资源类型")
    resource_id: Optional[str] = Field(None, description="资源ID")
    old_value: Optional[Dict[str, Any]] = Field(None, description="变更前值")
    new_value: Optional[Dict[str, Any]] = Field(None, description="变更后值")
    compliance_tags: List[str] = Field(default_factory=list, description="合规标签")
    
    # 审计类型常量
    class AuditType:
        LOGIN = "login"
        LOGOUT = "logout"
        CREATE = "create"
        UPDATE = "update"
        DELETE = "delete"
        VIEW = "view"
        EXPORT = "export"
        IMPORT = "import"
        CONFIG_CHANGE = "config_change"
        PERMISSION_CHANGE = "permission_change"


class ErrorLogEntry(LogEntry):
    """错误日志条目"""
    
    log_type: LogType = Field(LogType.ERROR, description="日志类型")
    level: LogLevel = Field(LogLevel.ERROR, description="日志级别")
    
    error_type: str = Field(..., description="错误类型")
    error_code: Optional[str] = Field(None, description="错误代码")
    stack_trace: Optional[str] = Field(None, description="堆栈跟踪")
    exception_class: Optional[str] = Field(None, description="异常类名")
    context: Dict[str, Any] = Field(default_factory=dict, description="错误上下文")
    
    # 解决状态
    is_resolved: bool = Field(False, description="是否已解决")
    resolved_at: Optional[datetime] = Field(None, description="解决时间")
    resolved_by: Optional[str] = Field(None, description="解决人")
    resolution_notes: Optional[str] = Field(None, description="解决方案备注")
    
    @field_serializer('resolved_at')
    def serialize_resolved_at(self, dt: Optional[datetime], _info) -> Optional[str]:
        if dt:
            return dt.isoformat()
        return None


class AccessLogEntry(LogEntry):
    """访问日志条目"""
    
    log_type: LogType = Field(LogType.ACCESS, description="日志类型")
    
    method: str = Field(..., description="HTTP方法")
    path: str = Field(..., description="请求路径")
    query_params: Optional[Dict[str, Any]] = Field(None, description="查询参数")
    status_code: int = Field(..., description="HTTP状态码")
    response_size: Optional[int] = Field(None, description="响应大小(字节)")
    
    # 认证信息
    auth_type: Optional[str] = Field(None, description="认证类型")
    token_fingerprint: Optional[str] = Field(None, description="Token指纹(脱敏)")


class BehaviorLogEntry(LogEntry):
    """行为日志条目"""
    
    log_type: LogType = Field(LogType.BEHAVIOR, description="日志类型")
    
    behavior_type: str = Field(..., description="行为类型")
    element_id: Optional[str] = Field(None, description="页面元素ID")
    page_url: Optional[str] = Field(None, description="页面URL")
    referrer: Optional[str] = Field(None, description="来源页面")
    
    # 行为数据
    click_count: Optional[int] = Field(None, description="点击次数")
    hover_duration_ms: Optional[int] = Field(None, description="悬停时长")
    scroll_depth: Optional[float] = Field(None, description="滚动深度(%)")
    
    # 客户端信息
    screen_resolution: Optional[str] = Field(None, description="屏幕分辨率")
    viewport_size: Optional[str] = Field(None, description="视口大小")
    device_type: Optional[str] = Field(None, description="设备类型")


class SystemLogEntry(LogEntry):
    """系统日志条目"""
    
    log_type: LogType = Field(LogType.SYSTEM, description="日志类型")
    
    # 系统指标
    cpu_percent: Optional[float] = Field(None, description="CPU使用率")
    memory_percent: Optional[float] = Field(None, description="内存使用率")
    disk_usage_percent: Optional[float] = Field(None, description="磁盘使用率")
    
    # 进程信息
    process_id: Optional[int] = Field(None, description="进程ID")
    thread_id: Optional[int] = Field(None, description="线程ID")
    
    # 组件状态
    component: Optional[str] = Field(None, description="组件名称")
    component_status: Optional[str] = Field(None, description="组件状态")
    health_check: Optional[bool] = Field(None, description="健康检查结果")


class SecurityLogEntry(LogEntry):
    """安全日志条目"""
    
    log_type: LogType = Field(LogType.SECURITY, description="日志类型")
    level: LogLevel = Field(LogLevel.WARNING, description="日志级别")
    
    threat_type: str = Field(..., description="威胁类型")
    severity: str = Field(..., description="严重程度: low/medium/high/critical")
    source_ip: Optional[str] = Field(None, description="来源IP")
    target_resource: Optional[str] = Field(None, description="目标资源")
    
    # 攻击详情
    attack_vector: Optional[str] = Field(None, description="攻击向量")
    payload_sample: Optional[str] = Field(None, description="攻击载荷样本(脱敏)")
    
    # 响应措施
    action_taken: Optional[str] = Field(None, description="已采取的措施")
    blocked: Optional[bool] = Field(None, description="是否已阻止")
    alert_sent: bool = Field(False, description="是否已发送告警")
