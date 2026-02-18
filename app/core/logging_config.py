import sys
from loguru import logger
from app.core.config import settings

def setup_logging():
    logger.remove()
    
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
    )
    
    logger.add(
        "logs/enterprise_app.log",
        rotation="100 MB",
        retention="30 days",
        level="DEBUG",
        compression="zip"
    )

setup_logging()
