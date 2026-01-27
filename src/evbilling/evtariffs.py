'''
Created on September 22, 2024

@author: Keith Gorlen kgorlen@gmail.com

Downloads PG&E tariffs and organizes them by effective date.

References:
    https://healthchecks.io/docs/

'''

__author__ = 'Keith Gorlen'
__version__ = '1.0.0'

import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import re
from typing import NamedTuple, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
"""Path to directory containing this Python script."""
sys.path.append(SCRIPT_DIR)
"""Allow evbilling CLI to import evsettings from script directory."""

# pylint: disable=wrong-import-position

from evsettings import Config
from evlogger import DATE_FMT, info_msg
from evbillperiod import BillPeriod
import pgebev1tariff
from pgebev1tariff import PGEBEV1Tariff
import evargs
import urllib3
import requests  # type: ignore
from requests.models import Response
import pdfplumber

# pylint: enable=wrong-import-position

# Global Constants

SCRIPT_NAME: str = Path(__file__).stem
"""Name of this script without .py extension."""

MONTH_NAMES = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
]


ONE_DAY: timedelta = timedelta(days=1)
"""timedelta instance for 1 day."""

# Global Variables

# Initialize logger

logger = logging.getLogger(SCRIPT_NAME)
"""Logging facility."""
logger.setLevel(logging.INFO)
rotating_handler = RotatingFileHandler(
    Config.evtariffs_log, maxBytes=1 * 1024 * 1024, backupCount=3
)
"""Rotating log file handler."""
rotating_handler.setLevel(logging.INFO)
rotating_handler.setFormatter(
    logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt=DATE_FMT,  # Custom date format
    )
)
logger.addHandler(rotating_handler)
pgebev1tariff.logger = logging.getLogger('evtariffs.pgebev1tariffs')

# Suppress pdfminer warnings: 2025-04-18 13:21:17 - pdfminer.pdfpage - WARNING -
# CropBox missing from /Page, defaulting to MediaBox
logging.getLogger("pdfminer").setLevel(logging.ERROR)


class ParsedArgs(NamedTuple):
    """Parsed command line options and arguments."""

    debug: bool
    """Log debugging information; default --no-debug."""
    quiet: bool
    """Do not print INFO, WARNING, ERROR, or CRITICAL messages to `stderr`;
    default --no-quiet."""
    version: bool
    """Display the version number and exit."""
    outdir: str
    """Output directory, default Config.pge_bev_tariff_dir."""


ARGS: ParsedArgs
"""Arguments parsed by argparse() in main()."""


def request(url: str, msg: str = "", get=False) -> requests.Response:
    """Send HTTP POST or GET to URL with retries on timeout.

    Args:
        url (str): healthchecks.io URL
        msg (str): message to send (default: "")
        op (bool): True for GET request, False for POST request (default: False)

    Returns:
        requests.Response: The response object from the POST request.

    Raises:
        requests.RequestException: If the request fails or returns a bad status code.
        requests.exceptions.Timeout: If the request times out after retries.
    """
    # url = "https://httpstat.us/504?sleep=60000" # For testing, simulates a 504 Gateway Timeout
    op = requests.get if get else requests.post
    logger.info(f'Sending request to {url} data="{msg}" ...')
    for timeout in (5, 10, 15):
        try:
            response = op(url, timeout=timeout, data=msg)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx, 5xx)
            return response
        except requests.exceptions.Timeout:
            logger.info(f"Request to {url} timed out after {timeout}s, retrying ...")
    raise requests.exceptions.Timeout(f"Request to {url} timed out after multiple retries")


def ping(url: str, msg: str = "") -> Response:
    """Ping healthchecks.io with an optional message.

    Args:
        url (str): healthchecks.io URL
        msg (str): message to log (default: "")

    Returns:
        requests.Response: The response object from the POST request.
    """
    return request(url, msg)


def main() -> None:
    """Process PG&E bill, get Emporia Vue data, and write submeter bills.

    Raises
    ------
    FileNotFoundError
        No such directory: "{tariff_path}".
    RuntimeError
        urllib3.util.parse_url({Config.pge_bev_tariff_url}).path failed.
    LookupError
        "UNBUNDLING OF TOTAL RATES" page not found.
    LookupError
        "Effective Date" not found.
    """
    global ARGS  # pylint: disable=global-statement
    logger.info(f'{"=" * 60}')
    logger.info(f'{SCRIPT_NAME} version {__version__} starting ...')
    logger.info(f'Configuration loaded from "{Config.config_file}".')

    # Parse command line arguments

    parser = argparse.ArgumentParser(
        description='Download PG&E BEV tariffs and order by effective date'
    )
    parser.add_argument(
        '-d',
        '--debug',
        action=argparse.BooleanOptionalAction,
        default=False,
        help='Log debug info; default --no-debug',
    )
    parser.add_argument(
        '-q',
        '--quiet',
        action=argparse.BooleanOptionalAction,
        default=True,
        help='Do not print verbose output; default --quiet',
    )
    parser.add_argument(
        '-v',
        '--version',
        action='version',
        version=f'{SCRIPT_NAME} {__version__}',
        default=False,
        help='Display the version number and exit',
    )
    parser.add_argument(
        'outdir',
        metavar='DIRECTORY',
        type=str,
        nargs='?',
        default=Config.pge_bev_tariff_dir,
        help=f'Output directory; default "{Config.pge_bev_tariff_dir}"',
    )
    args_dict: dict[str, Optional[bool | str | int]] = vars(parser.parse_args())
    ARGS = ParsedArgs(**args_dict)  # type: ignore
    logger.info(f'{SCRIPT_NAME} arguments: {ARGS}.')

    if ARGS.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        rotating_handler.setLevel(logging.DEBUG)

    # Set arguments also used by imported modules.
    evargs.Args.debug = ARGS.debug
    evargs.Args.quiet = ARGS.quiet

    tariff_path = Path(ARGS.outdir)
    if not tariff_path.is_dir():
        raise FileNotFoundError(f'No such directory: "{tariff_path}"')

    url = urllib3.util.parse_url(Config.pge_bev_tariff_url).path  # type: ignore
    if not url:
        raise RuntimeError(f'urllib3.util.parse_url({Config.pge_bev_tariff_url}).path failed')

    url_path = Path(url)

    info_msg(logger, f'Downloading tariff from {Config.pge_bev_tariff_url} ...')
    response = request(Config.pge_bev_tariff_url, get=True)
    info_msg(logger, f'{Config.pge_bev_tariff_url} downloaded.')

    tariff_file = tariff_path.joinpath(url_path.name)
    info_msg(logger, f'Saving tariff to "{tariff_file}" ...')
    with open(tariff_file, 'wb') as f:
        f.write(response.content)

    info_msg(logger, 'Looking for "UNBUNDLING OF TOTAL RATES" page ...')

    with pdfplumber.open(tariff_file) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            # Replace multiple spaces and tabs with single space
            text = re.sub(r'[ \t]+', ' ', text)
            if re.search(r'UNBUNDLING OF TOTAL RATES', text):
                break
        else:
            raise LookupError('"UNBUNDLING OF TOTAL RATES" page not found')

    if not (
        m := re.search(
            rf'Effective ({"|".join(MONTH_NAMES)}) (\d?\d), (\d{{4}})', text, re.MULTILINE
        )
    ):
        raise LookupError(f'"Effective Date" not found on page {page_num + 1}')

    effective_month = MONTH_NAMES.index(m.group(1)) + 1
    effective_date = f'{m.group(3)}-{effective_month:02d}-{int(m.group(2)):02d}'
    info_msg(logger, f'Tariff effective date is {effective_date}.')

    target = tariff_path.joinpath(f'{effective_date}_{url_path.name}')
    if target.is_file():
        info_msg(logger, f'"{target}" already downloaded.')
        tariff_file.unlink(missing_ok=True)
        info_msg(logger, f'"{tariff_file}" deleted.')
    else:
        info_msg(logger, f'Renaming "{tariff_file}" to "{target}" ...')
        tariff_file.rename(target)

    # Test tariff parsing

    PGEBEV1Tariff.init()
    PGEBEV1Tariff.effective_rates(
        BillPeriod(re.sub(r'(\d{4})-(\d\d)-(\d\d)', r'\2/\3/\1', effective_date))
    )

    info_msg(logger, 'Pinging healthchecks.io ...')
    # Raise an exception for bad status codes (4xx, 5xx)
    ping(Config.healthchecks_url)
    info_msg(logger, 'Successful ping sent.')

    info_msg(logger, f'{SCRIPT_NAME} finished.')
    logger.info(f'{"=" * 60}')
    logging.shutdown()
    sys.exit(0)


def fatal_error(msg: str) -> None:
    """Log a CRITICAL message and sys.exit(1)."""
    print(f'{datetime.now().strftime(DATE_FMT)} - CRITICAL - {msg}; exiting.', file=sys.stderr)
    logger.critical(f'{msg}; exiting.')
    logger.info(f'{"=" * 60}')
    logging.shutdown()
    sys.exit(1)


def cli() -> None:
    """Command line interface for evtariffs."""
    try:
        main()
    except requests.exceptions.RequestException as e:
        fatal_error(str(e))
    except Exception as e:  # pylint: disable=broad-exception-caught
        info_msg(logger, 'Pinging healthchecks.io ...')
        ping(Config.healthchecks_url + '/fail', str(e))
        info_msg(logger, 'Failure ping sent.')
        fatal_error(str(e))


if __name__ == '__main__':
    cli()
