'''
pgebevtariff -- PG&E Electric Schedule BEV data.

'''
__author__ = 'Keith Gorlen'

import os
import sys
import logging
from datetime import date
from pathlib import Path
from collections import defaultdict
import functools
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
"""Path to directory containing this Python script."""
sys.path.append(SCRIPT_DIR)
"""Allow evbilling CLI to import evsettings from script directory."""

# pylint: disable=wrong-import-position

from evsettings import Config, Tou
from evunits import DollarsPerKilowattHour
from evbillperiod import BillPeriod
import pdfplumber

# pylint: enable=wrong-import-position

# Global Constants

RE_RATES = r'\$(\d{1,3}\.\d{5})'
"""Regular expression for $nnn.nnnnn dollars/kWh."""

logger = logging.getLogger(__name__)


class PGEBEV1Tariff:
    """PG&E Electric Schedule BEV data."""

    rates: dict[str, dict[str, DollarsPerKilowattHour]] = defaultdict(dict)
    """RATES[effective_date][key] = DollarsPerKilowattHour(rate)"""

    # BEV-1 Unbundled Time-Of-Use (TOU) Generation Credit and Power Charge
    # Indifference Adjustment (PCIA) rates from PG&E Electric Schedule BEV.

    @classmethod
    def init(cls) -> None:
        """Initializes cls.rate from PG&E Electric Schedule BEV.

        Raises
        ------
        LookupError
            No tariff files found
        ValueError
            Invalid tariff filename
        LookupError
            "UNBUNDLING OF TOTAL RATES" page not found
        KeyError
            Keys not found in tariff file

                    Notes
        -----
        Bundled Power Charge Indifference Adjustment (PCIA) may be negative.
        """

        # pylint: disable=line-too-long
        fields: dict[str, str] = {
            'Bundled PCIA': rf'Bundled Power Charge Indifference[^($]+(\(?){RE_RATES}(\)?)',
            Tou.PEAK: rf'TOTAL BUNDLED(?:.*\n)+^ ?Peak[^$]+{RE_RATES}(?:.*\n)+?UNBUNDLING',
            Tou.OFF_PEAK: rf'TOTAL BUNDLED(?:.*\n)+^ ?Off-Peak[^$]+{RE_RATES}(?:.*\n)+?UNBUNDLING',
            Tou.SUPER_OFF_PEAK: rf'TOTAL BUNDLED(?:.*\n)+^ ?Super Off-Peak[^$]+{RE_RATES}(?:.*\n)+?UNBUNDLING',
            f'Credit/{Tou.PEAK}': rf'Generation:(?:.*\n)+^ ?Peak[^$]+{RE_RATES}(?:.*\n)+?Distribution',
            f'Credit/{Tou.OFF_PEAK}': rf'Generation:(?:.*\n)+^ ?Off-Peak[^$]+{RE_RATES}(?:.*\n)+?Distribution',
            f'Credit/{Tou.SUPER_OFF_PEAK}': rf'Generation:(?:.*\n)+^ ?Super Off-Peak[^$]+{RE_RATES}(?:.*\n)+?Distribution',
        }
        # pylint: enable=line-too-long

        tariff_files: list[Path] = list(Config.pge_bev_tariff_dir.glob('????-??-??_*.pdf'))
        if not tariff_files:
            raise LookupError(f'No tariff files found in "{Config.pge_bev_tariff_dir}"')

        for tariff_file in tariff_files:
            if not (m := re.match(r'(\d{4}-\d\d-\d\d)_', tariff_file.name)):
                raise ValueError(f'"{tariff_file}": Invalid tariff filename')

            effective_date = m.group(1)

            with pdfplumber.open(tariff_file) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    text = re.sub(
                        r'[ \t]+', ' ', text
                    )  # Replace multiple spaces and tabs with single space
                    if re.search(r'UNBUNDLING OF TOTAL RATES', text):
                        break
                else:
                    raise LookupError(
                        f'"UNBUNDLING OF TOTAL RATES" page not found in tariff "{tariff_file}"'
                    )

            logger.debug(f'PG&E tariff rates effective {effective_date}:')
            text = re.sub(r'\(all usage\)', '', text)
            missing_keys: set[str] = set()
            for key, regex in fields.items():
                if not (m := re.search(regex, text, re.MULTILINE)):
                    missing_keys.add(key)
                    continue

                cls.rates[effective_date][key] = DollarsPerKilowattHour(''.join(m.groups('')))
                logger.debug(f'  {key:<25}  {cls.rates[effective_date][key]}')

            if missing_keys:
                raise KeyError(f'Keys not found in tariff "{tariff_file}": {missing_keys}')

    @classmethod
    @functools.lru_cache
    def effective_rates(cls, period: BillPeriod) -> dict[str, DollarsPerKilowattHour]:
        """Return rates for specified BillPeriod.

        Parameters
        ----------
        period : BillPeriod
            Bill period for which tariff is effective.

        Returns
        -------
        dict
            Rates for effective date of bill period.

        Raises
        ------
        LookupError
            PG&E rate period tariff rates not found
        """
        frdate: str = date.isoformat(period.fr)
        for effective_date in sorted(cls.rates.keys(), reverse=True):
            if frdate >= effective_date:
                logger.info(f'PG&E rate period {period} tariff rates effective {effective_date}:')
                for key, rate in cls.rates[effective_date].items():
                    logger.info(f'  {key:<25}  {rate:8.5f}')
                return cls.rates[effective_date]

        raise LookupError(f'PG&E rate period {period} {frdate} tariff rates not found')
