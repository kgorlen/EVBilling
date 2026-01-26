'''
evlogger.py -- EVBilling message logger.


'''

__author__ = 'Keith Gorlen'
__all__: list[str] = []

import sys
import logging
from datetime import datetime
from pathlib import Path

SCRIPT_DIR: Path = Path(__file__).absolute().parent
"""Path to directory containing this Python script."""
sys.path.append(str(SCRIPT_DIR))
"""Allow evbilling CLI to import modules from script directory."""

# pylint: disable=wrong-import-position

from __init__ import __version__
from evargs import Args

# pylint: enable=wrong-import-position

# Global Constants

DATE_FMT = '%Y-%m-%d %H:%M:%S'
"""Format for dates in messages."""

Warning_Count: int = 0
"""Count of warning conditions found."""
Error_Count: int = 0
"""Count of errors found since last reset()."""
Total_Error_Count: int = 0
"""Total count of error conditions found."""

logging.basicConfig(
    handlers=[],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)


def info_msg(logger: logging.Logger, msg: str) -> None:
    """Log and print an INFO message to stdout."""
    logger.info(msg)
    if not Args.quiet:
        print(f'{datetime.now().strftime(DATE_FMT)} - INFO - {msg}', file=sys.stderr)


def warning_msg(logger: logging.Logger, msg: str) -> None:
    """Log a WARNING message and increment Warning_Count."""
    global Warning_Count  # pylint: disable=global-statement
    Warning_Count += 1
    logger.warning(msg)
    if not Args.quiet:
        print(f'{datetime.now().strftime(DATE_FMT)} - WARNING - {msg}', file=sys.stderr)


def error_msg(logger: logging.Logger, msg: str) -> None:
    """Log an ERROR message and increment Error_Count."""
    global Error_Count, Total_Error_Count  # pylint: disable=global-statement
    Error_Count += 1
    Total_Error_Count += 1
    logger.error(msg)
    if not Args.quiet:
        print(f'{datetime.now().strftime(DATE_FMT)} - ERROR - {msg}', file=sys.stderr)


def reset_errors() -> None:
    """Reset Warning_Count and Error_Count to zero."""
    global Warning_Count  # pylint: disable=global-statement
    global Error_Count  # pylint: disable=global-statement
    Warning_Count = 0
    Error_Count = 0


def warning_count() -> int:
    """Return the current value of Warning_Count."""
    return Warning_Count


def error_count() -> int:
    """Return the current value of Error_Count."""
    return Error_Count


def total_error_count() -> int:
    """Return the current value of Total_Error_Count."""
    return Total_Error_Count
