"""
統一的 Log 管理
"""
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name: str, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Console Handler
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
    logger.addHandler(console)
    
    # File Handler
    file_handler = RotatingFileHandler("logs/bot.log", maxBytes=5*1024*1024, backupCount=3)
    file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(name)s - %(levelname)s: %(message)s"))

    logger.addHandler(file_handler)
    
    return logger