from pathlib import Path
import logging
import sys
from typing import Optional
from datetime import datetime


def setup_logging(logs_dir: Optional[str | Path] = None, log_file_name: str = "server.log") -> logging.Logger:
    """Configure root logging to stdout and a file under `logs_dir`.

    Idempotent: calling multiple times won't add duplicate handlers.
    Ensures a file handler writing to logs/<log_file_name> and a StreamHandler to stdout.
    Returns a module-level logger for callers to use.
    """
    if logs_dir is None:
        logs_dir = Path(__file__).resolve().parent.parent / "logs"
    else:
        logs_dir = Path(logs_dir)

    # Ensure logs directory exists
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # best-effort: continue if it cannot create logs dir
        pass

    # Add timestamp to the logfile name so each run writes to a timestamped file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(log_file_name).stem
    ext = Path(log_file_name).suffix or ".log"
    log_file_name = f"{base}_{timestamp}{ext}"
    log_file = logs_dir / log_file_name

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # formatter used by both handlers
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    # Add a FileHandler for the server log if not already present writing to the same file
    file_handler_exists = False
    for h in list(root_logger.handlers):
        if isinstance(h, logging.FileHandler):
            try:
                # check handler's baseFilename if available
                if hasattr(h, 'baseFilename') and Path(h.baseFilename).resolve() == log_file.resolve():
                    file_handler_exists = True
                    break
            except Exception:
                continue

    if not file_handler_exists:
        try:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(formatter)
            fh.setLevel(logging.INFO)
            root_logger.addHandler(fh)
        except Exception:
            # If file handler cannot be created (permissions, etc), fall back to stdout only
            pass

    # Ensure a StreamHandler to stdout exists (don't duplicate)
    stream_stdout_exists = False
    for h in root_logger.handlers:
        if isinstance(h, logging.StreamHandler):
            # compare the stream object to sys.stdout
            if getattr(h, 'stream', None) is sys.stdout:
                stream_stdout_exists = True
                break

    if not stream_stdout_exists:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        sh.setLevel(logging.INFO)
        root_logger.addHandler(sh)

    # Return a logger for the current module
    return logging.getLogger(__name__)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Helper to get a logger by name; falls back to module logger."""
    logger = logging.getLogger(name) if name else logging.getLogger(__name__)
    return logger
