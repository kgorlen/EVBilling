'''
Created on September 22, 2024

@author: Keith Gorlen kgorlen@gmail.com

Downloads PG&E tariffs and organizes them by effective date.

References:
    https://healthchecks.io/docs/

'''

__author__ = 'Keith Gorlen'
__version__ = '0.4.0'

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
pgebev1tariff.logger=logging.getLogger('evtariffs.pgebev1tariffs')


class ParsedArgs(NamedTuple):
    """Parsed command line options and arguments."""

    debug: Optional[bool]
    """Log debugging information; default --no-debug."""
    quiet: Optional[bool]
    """Do not print INFO, WARNING, ERROR, or CRITICAL messages to `stderr`;
    default --no-quiet."""
    version: Optional[bool]
    """Display the version number and exit."""
    outdir: str
    """Output directory, default Config.pge_bev_tariff_dir."""


ARGS: ParsedArgs
"""Arguments parsed by argparse() in main()."""


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
        action=argparse.BooleanOptionalAction,
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

    if ARGS.version:
        info_msg(logger, f'{SCRIPT_NAME} version {__version__}')
        sys.exit(0)

    if ARGS.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        rotating_handler.setLevel(logging.DEBUG)

    # Set arguments also used by imported modules.
    evargs.Args.debug = ARGS.debug
    evargs.Args.quiet = ARGS.quiet

    tariff_path = Path(ARGS.outdir)
    if not tariff_path.is_dir():
        raise FileNotFoundError(f'No such directory: "{tariff_path}"')

    url = urllib3.util.parse_url(Config.pge_bev_tariff_url).path
    if not url:
        raise RuntimeError(f'urllib3.util.parse_url({Config.pge_bev_tariff_url}).path failed')

    url_path = Path(url)

    info_msg(logger, f'Downloading tariff from {Config.pge_bev_tariff_url} ...')
    response = requests.get(Config.pge_bev_tariff_url, timeout=60)
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
    requests.get(Config.healthchecks_url, timeout=20).raise_for_status()
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

if __name__ == '__main__':
    try:
        main()
    except requests.exceptions.RequestException as e:
        fatal_error(str(e))
    except Exception as e:  # pylint: disable=broad-exception-caught
        info_msg(logger, 'Pinging healthchecks.io ...')
        requests.post(Config.healthchecks_url + '/fail', data=str(e), timeout=20)
        info_msg(logger, 'Failure ping sent.')
        fatal_error(str(e))
