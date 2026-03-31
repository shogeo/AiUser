import logging

class ColorFormatter(logging.Formatter):
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    RED = "\x1b[31m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"
    
    BASE_FORMAT = "[%(levelname)s %(asctime)s] %(name)s: %(message)s"

    def __init__(self, datefmt="%Y-%m-%d %H:%M:%S"):
        super().__init__()
        self.datefmt = datefmt
        self.FORMATS = {
            logging.INFO: self.GREEN + self.BASE_FORMAT + self.RESET,
            logging.WARNING: self.YELLOW + self.BASE_FORMAT + self.RESET,
            logging.ERROR: self.RED + self.BASE_FORMAT + self.RESET,
            logging.CRITICAL: self.BOLD_RED + self.BASE_FORMAT + self.RESET,
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.BASE_FORMAT)
        formatter = logging.Formatter(log_fmt, datefmt=self.datefmt)
        return formatter.format(record)

def configure_logging():
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter())
    root_logger.addHandler(handler)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
