"""
Настройка логирования через Loguru
Замена для color_utils.py
"""

import sys
from pathlib import Path
from loguru import logger


def setup_logging():
    """Инициализация логирования"""
    
    # Удаляем дефолтный handler
    logger.remove()
    
    # ===== Консоль с цветами =====
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    # ===== Файлы логов =====
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Обычный лог
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # Новый файл каждый день
        retention="30 days",  # Храним 30 дней
        compression="zip",  # Сжимаем старые
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",  # В файл пишем всё
        backtrace=True,
        diagnose=True
    )
    
    # Только ошибки
    logger.add(
        log_dir / "errors_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="90 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        backtrace=True,
        diagnose=True
    )
    
    logger.info("✅ Logging initialized")
    return logger


# ===== Backward compatibility с color_utils.py =====
def print_success(message: str):
    """Замена для print_success"""
    logger.success(message)


def print_error(message: str):
    """Замена для print_error"""
    logger.error(message)


def print_warning(message: str):
    """Замена для print_warning"""
    logger.warning(message)


def print_info(message: str):
    """Замена для print_info"""
    logger.info(message)


def print_debug(message: str):
    """Для отладки"""
    logger.debug(message)


# Инициализируем при импорте
setup_logging()


if __name__ == "__main__":
    # Тестирование
    print_info("This is info")
    print_success("This is success")
    print_warning("This is warning")
    print_error("This is error")
    print_debug("This is debug")
