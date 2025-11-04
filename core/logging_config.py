from pathlib import Path
import logging
import sys
from typing import Optional
from datetime import datetime


def setup_logging(logs_dir: Optional[str | Path] = None, log_file_name: str = "server.log") -> logging.Logger:
    """Configure root logging to stdout and a file under `logs_dir`.

    This is idempotent: if handlers already exist on the root logger, it won't reconfigure.
    Returns a module-level logger for callers to use.
    """
    if logs_dir is None:
        logs_dir = Path(__file__).resolve().parent.parent / "logs"
    else:
        logs_dir = Path(logs_dir)

    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass  # best-effort: continue if cannot create logs dir

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name, ext = Path(log_file_name).stem, Path(log_file_name).suffix or ".log"
    log_file_name = f"{name}_{timestamp}{ext}"

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        log_file = logs_dir / log_file_name
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)

        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception:
            pass  # continue with console logging if file handler fails

        root_logger.addHandler(stream_handler)
        root_logger.setLevel(logging.INFO)

    return logging.getLogger(__name__)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name) if name else logging.getLogger(__name__)
    return logger

