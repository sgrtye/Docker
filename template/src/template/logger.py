import logging
from logging.handlers import TimedRotatingFileHandler

console_logger = logging.getLogger("my_app")
console_logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter(
    fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
console_logger.addHandler(console_handler)
console_logger.propagate = False


file_logger = logging.getLogger("custom_logger")
file_logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler("log.log", when="W0", backupCount=4)
formatter = logging.Formatter("%(asctime)s - %(message)s", "%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
file_logger.addHandler(handler)
file_logger.propagate = False


def some_function() -> None:
    pass


__all__ = ["some_function"]

if __name__ == "__main__":
    file_logger.info("This record should only be written to the log file.")
