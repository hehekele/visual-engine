import sys
from pathlib import Path
from loguru import logger
from app.core.config import settings

def setup_logging():
    """
    配置 Loguru 日志系统
    - 控制台输出: 彩色、简洁
    - 文件输出: 详细、按天滚动
    """
    # 移除默认处理器
    logger.remove()

    # 日志格式
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # 1. 控制台输出
    logger.add(
        sys.stderr,
        format=log_format,
        level="INFO",
        colorize=True
    )

    # 2. 文件输出
    log_dir = settings.DATA_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "visual_engine.log"
    
    logger.add(
        str(log_file),
        format=log_format,
        level="DEBUG",  # 文件记录更详细
        rotation="10 MB",  # 超过 10MB 自动轮转
        retention="1 week",  # 保留一周
        compression="zip",  # 压缩旧日志
        encoding="utf-8"
    )

    logger.info(f"Logging initialized. Logs are saved to: {log_file}")

# 导出 logger 实例供全局使用
__all__ = ["logger", "setup_logging"]
