import logging

def setup_logger(name: str = "tg_ai") -> logging.Logger:
    logging.basicConfig(
        format="[%(levelname)s %(asctime)s] %(name)s: %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    return logging.getLogger(name)