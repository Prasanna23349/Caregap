"""
bcs_logger.py — Centralized logging for BCS Care Gap Engine
Logs to both console (colored) and a rotating log file.
Usage: from bcs_logger import get_logger; logger = get_logger(__name__)
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

# ── Log directory ──────────────────────────────────────────────────────────
LOG_DIR  = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "bcs_pipeline.log")
os.makedirs(LOG_DIR, exist_ok=True)

# ── ANSI color codes for console ───────────────────────────────────────────
class Colors:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"
    GREY    = "\033[90m"

class ColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG:    Colors.GREY,
        logging.INFO:     Colors.CYAN,
        logging.WARNING:  Colors.YELLOW,
        logging.ERROR:    Colors.RED,
        logging.CRITICAL: Colors.MAGENTA + Colors.BOLD,
    }

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelno, Colors.RESET)
        levelname = f"{color}{record.levelname:<8}{Colors.RESET}"
        time_str  = f"{Colors.GREY}{self.formatTime(record, '%H:%M:%S')}{Colors.RESET}"
        name_str  = f"{Colors.BOLD}{record.name}{Colors.RESET}"
        msg       = record.getMessage()

        # Highlight success/failure keywords
        if any(k in msg for k in ("✅", "PASS", "CLOSED", "matched", "Complete")):
            msg = f"{Colors.GREEN}{msg}{Colors.RESET}"
        elif any(k in msg for k in ("❌", "FAIL", "ERROR", "REJECTED")):
            msg = f"{Colors.RED}{msg}{Colors.RESET}"
        elif any(k in msg for k in ("⚠️", "PENDING", "WARNING")):
            msg = f"{Colors.YELLOW}{msg}{Colors.RESET}"

        return f"{time_str} {levelname} [{name_str}] {msg}"

class PlainFormatter(logging.Formatter):
    """Plain formatter for file output (no ANSI codes)."""
    def format(self, record):
        return (f"{self.formatTime(record, '%Y-%m-%d %H:%M:%S')} "
                f"{record.levelname:<8} [{record.name}] {record.getMessage()}")

def get_logger(name: str, level=logging.DEBUG) -> logging.Logger:
    """
    Get a named logger with console + rotating file handlers.
    Call once per module: logger = get_logger(__name__)
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(level)

    # ── Console handler ──
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(ColorFormatter())

    # ── File handler (rotating: 5 MB x 3 backups) ──
    fh = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(PlainFormatter())

    logger.addHandler(ch)
    logger.addHandler(fh)
    logger.propagate = False

    return logger


def log_step_start(logger: logging.Logger, step: int, title: str):
    """Log a standardized step header."""
    logger.info("=" * 60)
    logger.info(f"STEP {step} START — {title}")
    logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)


def log_step_end(logger: logging.Logger, step: int, title: str, stats: dict = None):
    """Log a standardized step footer with optional stats."""
    logger.info("-" * 60)
    logger.info(f"✅ STEP {step} COMPLETE — {title}")
    if stats:
        for k, v in stats.items():
            logger.info(f"   {k}: {v}")
    logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)


def log_member(logger: logging.Logger, mid: str, name: str, result: str, detail: str = ""):
    """Log a per-member processing result."""
    symbol = "✅" if "PASS" in result or "matched" in result.lower() or "✅" in result else \
             "⚠️" if "PENDING" in result or "PARTIAL" in result else \
             "❌" if "FAIL" in result or "ERROR" in result else "→"
    logger.info(f"{symbol} {mid} | {name:<22} | {result}{' | ' + detail if detail else ''}")


def log_validation(logger: logging.Logger, check: str, passed: bool, detail: str = ""):
    """Log a HEDIS validation check result."""
    if passed:
        logger.info(f"✅ PASS — {check}")
    else:
        logger.error(f"❌ FAIL — {check}{' | ' + detail if detail else ''}")
