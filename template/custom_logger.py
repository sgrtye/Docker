import logging
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger("custom_logger")
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler("log.log", when="W0", backupCount=4)
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(message)s", "%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.propagate = False


def some_function() -> None:
    pass


__all__ = ["some_function"]

if __name__ == "__main__":
    logger.info("This record should only be written to the log file.")
