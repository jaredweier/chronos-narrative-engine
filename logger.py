import logging
import logging.handlers
import json
import sys
import os
import time
import traceback
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logger = logging.getLogger(__name__)

_human_log_file = os.path.join(LOG_DIR, "chronos.log")
_json_log_file = os.path.join(LOG_DIR, "chronos.jsonl")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": "".join(traceback.format_tb(record.exc_info[2])),
            }
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data
        return json.dumps(log_entry, default=str)


_human_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_human_handler = logging.handlers.TimedRotatingFileHandler(
    _human_log_file, when="midnight", backupCount=30, encoding="utf-8"
)
_human_handler.setFormatter(_human_formatter)

_json_handler = logging.handlers.TimedRotatingFileHandler(
    _json_log_file, when="midnight", backupCount=90, encoding="utf-8"
)
_json_handler.setFormatter(JsonFormatter())

_console_handler = logging.StreamHandler(sys.stderr)
_console_handler.setFormatter(_human_formatter)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.addHandler(_human_handler)
        logger.addHandler(_json_handler)
        logger.addHandler(_console_handler)
    return logger


class ChronosLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        if "extra" in kwargs:
            kwargs["extra"] = {"extra_data": kwargs["extra"]}
        return msg, kwargs


def get_chronos_logger(name: str) -> ChronosLoggerAdapter:
    return ChronosLoggerAdapter(get_logger(name), extra=None)


def archive_logs() -> int:
    import shutil
    from config import LOG_ARCHIVE_ENABLED, LOG_ARCHIVE_DIR, LOG_ARCHIVE_RETENTION_DAYS
    if not LOG_ARCHIVE_ENABLED:
        return 0
    os.makedirs(LOG_ARCHIVE_DIR, exist_ok=True)
    archived = 0
    now = time.time()
    for fname in os.listdir(LOG_DIR):
        fpath = os.path.join(LOG_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        fage_days = (now - os.path.getmtime(fpath)) / 86400
        if fage_days > 1:
            ts = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y%m%d')
            arc_name = f"{ts}_{fname}"
            shutil.move(fpath, os.path.join(LOG_ARCHIVE_DIR, arc_name))
            archived += 1
    for fname in os.listdir(LOG_ARCHIVE_DIR):
        fpath = os.path.join(LOG_ARCHIVE_DIR, fname)
        if os.path.isfile(fpath):
            fage_days = (now - os.path.getmtime(fpath)) / 86400
            if fage_days > LOG_ARCHIVE_RETENTION_DAYS:
                os.remove(fpath)
    if archived:
        logger.info("Archived %d old log files", archived)
    return archived


def download_logs_zip() -> bytes:
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(LOG_DIR):
            fpath = os.path.join(LOG_DIR, fname)
            if os.path.isfile(fpath):
                zf.write(fpath, arcname=fname)
    return buf.getvalue()
