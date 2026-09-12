import logging
import json
import sys
from datetime import datetime, timezone
from src.core.config import settings

class JSONFormatter(logging.Formatter):
    """Formats log entries as structured JSON objects."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "component": getattr(record, "component", "pipeline"),
        }
        
        # Include extra contextual fields
        for key, value in record.__dict__.items():
            if key not in {
                "args", "asctime", "created", "filename", "funcName", "levelname",
                "levelno", "lineno", "module", "msecs", "msg", "name", "pathname",
                "process", "processName", "relativeCreated", "stack_info", "thread",
                "threadName", "component"
            } and not key.startswith("_"):
                log_data[key] = value

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)

def setup_logger(name: str = "pipeline") -> logging.Logger:
    """Configures and returns a structured JSON logger instance."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        
    return logger

logger = setup_logger()
