
import logging as log
import config
import sys

logger = {
    "handler": None
}

LOG_LEVEL = config.LOG_LEVEL

def setup_logger():
    root = log.getLogger()
    root.setLevel(LOG_LEVEL)

    ch = log.StreamHandler(sys.stdout)
    ch.setLevel(LOG_LEVEL)
    log_format = '%(asctime)s - %(levelname)s - %(filename)s - %(funcName)s - %(message)s'

    formatter = log.Formatter(log_format)
    ch.setFormatter(formatter)
    old_handler = logger.get("handler")
    if old_handler:
        root.removeHandler(old_handler)
    logger['handler'] = ch
    root.addHandler(ch)
    log.debug("Logger setup complete.")

setup_logger()
