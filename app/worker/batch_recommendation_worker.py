"""
推荐批处理后台任务

每天定时执行，生成股票推荐数据
"""

import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# 全局调度器
_scheduler: Optional[BackgroundScheduler] = None


def generate_daily_recommendations_task(max_stocks: Optional[int] = None):
    """
    生成每日推荐数据的任务
    
    Args:
        max_stocks: 最大处理数量（测试用）
    """
    try:
        logger.info("=" * 60)
        logger.info("开始执行每日推荐批处理任务")
        logger.info(f"时间: {datetime.now()}")
        
        from recommender import run_daily_batch
        
        result = run_daily_batch(max_stocks=max_stocks)
        
        logger.info(f"批处理结果: {result}")
        logger.info("=" * 60)
        
        return result
        
    except Exception as e:
        logger.error(f"批处理任务执行失败: {e}", exc_info=True)
        raise


def init_batch_recommendation_scheduler(
    hour: int = 2,
    minute: int = 0,
    max_stocks: Optional[int] = None
):
    """
    初始化批处理调度器
    
    Args:
        hour: 执行小时（默认凌晨2点）
        minute: 执行分钟
        max_stocks: 最大处理数量
    """
    global _scheduler
    
    if _scheduler is not None:
        logger.warning("调度器已经初始化")
        return _scheduler
    
    _scheduler = BackgroundScheduler()
    
    # 添加定时任务：每天凌晨执行
    _scheduler.add_job(
        func=generate_daily_recommendations_task,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="daily_recommendation_batch",
        name="每日股票推荐批处理",
        replace_existing=True,
        kwargs={"max_stocks": max_stocks},
    )
    
    _scheduler.start()
    logger.info(f"批处理调度器已启动，每天 {hour:02d}:{minute:02d} 执行")
    
    return _scheduler


def shutdown_scheduler():
    """关闭调度器"""
    global _scheduler
    
    if _scheduler:
        _scheduler.shutdown()
        _scheduler = None
        logger.info("批处理调度器已关闭")


def run_once(max_stocks: Optional[int] = None):
    """
    立即执行一次批处理（手动触发）
    
    Args:
        max_stocks: 最大处理数量
    """
    return generate_daily_recommendations_task(max_stocks=max_stocks)


# 如果直接运行此文件，执行一次批处理
if __name__ == "__main__":
    import sys
    
    # 解析参数
    max_stocks = None
    if len(sys.argv) > 1:
        try:
            max_stocks = int(sys.argv[1])
        except ValueError:
            pass
    
    print(f"手动执行批处理，max_stocks={max_stocks}")
    result = run_once(max_stocks=max_stocks)
    print(f"结果: {result}")
