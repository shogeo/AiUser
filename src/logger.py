import logging

def setup_logger(name: str = "tg_ai") -> logging.Logger:
    """
    Настраивает и возвращает логгер с базовой конфигурацией.
    """
    logging.basicConfig(
        format="[%(levelname)s %(asctime)s] %(name)s: %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    return logging.getLogger(name)
