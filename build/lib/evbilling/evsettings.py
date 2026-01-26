'''
evsettings.py -- Initialize Config class from evbilling.toml file.

References:
    https://toml.io/en/ -- TOML: A config file format for humans

'''

__author__ = 'Keith Gorlen'
__all__: list[str] = [
    'Tou',
    'Config',
]

import os
import sys
from enum import StrEnum
from pathlib import Path
import tomllib
from collections import namedtuple
from itertools import chain
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
"""Path to directory containing this Python script."""
sys.path.append(SCRIPT_DIR)
"""Allow evbilling CLI to import evsettings from script directory."""

# pylint: disable=wrong-import-position

from __init__ import __version__  # pylint: disable=no-name-in-module
from platformdirs import user_config_dir, user_log_dir
import numpy as np
import numpy.typing as npt

# pylint: enable=wrong-import-position


class Tou(StrEnum):
    """Time-Of-Use keys."""

    PEAK = 'Peak'
    OFF_PEAK = 'Off Peak'
    SUPER_OFF_PEAK = 'Super Off Peak'


# mypy: ignore-errors


class Config:
    """EVBilling configuration and settings.

    Raises
    ------
    FileNotFoundError
        Configuration file evbilling.toml not found.
    ValueError
        Error reading configuration file.
    KeyError
        Table key not found
    KeyError
        Key not found in configuration file
    ValueError
        Gaps or overlaps in time_of_use table
    """

    config_dir: Path = Path(user_config_dir('EVBilling', appauthor=False, roaming=True))
    """Configuration directory."""

    config_file: Path = config_dir / 'evbilling.toml'
    """User-specific configuration file."""

    default_evbilling_log: Path = (
        Path(user_log_dir('EVBilling', appauthor=False, ensure_exists=True)) / 'evbilling.log'
    )
    """Default evbilling log file."""

    default_evtariffs_log: Path = (
        Path(user_log_dir('EVBilling', appauthor=False, ensure_exists=True)) / 'evtariffs.log'
    )
    """Default evbilling log file."""

    default_thumbnail: Path = Path(SCRIPT_DIR) / 'no-image-icon-23488.png'
    """Default thumbnail .jpg or .png file."""

    config_data: dict[str, Any]
    """Data from evbilling.toml file."""

    if not config_file.exists():
        raise FileNotFoundError(f'Configuration file not found: "{config_file}"')

    try:
        with config_file.open('rb') as f:
            config_data = tomllib.load(f)
    except Exception as e:
        raise ValueError(
            f'Error reading configuration file {
                            config_file}: {e}'
        ) from e

    @classmethod
    def namedtuple_from_dict(cls, typename: str, key: str) -> tuple[str | float, ...]:
        """Create a namedtuple from a dictionary."""
        try:
            ntpl = namedtuple(typename, cls.config_data[key].keys())(**cls.config_data[key])
        except KeyError as e:
            raise KeyError(f'Table "{key}" not found') from e

        return ntpl

    @classmethod
    def init(cls) -> None:
        """Initialize configuration from .toml configuration file."""
        try:
            cls.title: str = 'YOUR TITLE HERE'
            """Submeter bill PDF page header title."""
            cls.thumbnail: Path = cls.default_thumbnail
            """Submeter bill PDF page header thumbnail, .jpg or .png."""
            if 'header' in cls.config_data:
                if 'title' in cls.config_data['header']:
                    cls.title = cls.config_data['header']['title']
                if 'thumbnail' in cls.config_data['header']:
                    cls.thumbnail = cls.config_dir / cls.config_data['header']['thumbnail']
                    if not cls.thumbnail.exists():
                        cls.thumbnail = cls.default_thumbnail

            cls.evbilling_log: Path
            """evbilling log file path."""
            cls.evtariffs_log: Path
            """evtariffs log file path."""
            if 'logging' in cls.config_data:
                cls.evbilling_log = (
                    Path(cls.config_data['logging']['evbilling'])
                    if 'evbilling' in cls.config_data['logging']
                    else cls.default_evbilling_log
                )
                cls.evtariffs_log = (
                    Path(cls.config_data['logging']['evtariffs'])
                    if 'evtariffs' in cls.config_data['logging']
                    else cls.default_evtariffs_log
                )

            cls.credentials: tuple[str | float, ...] = cls.namedtuple_from_dict(
                'Credentials', 'credentials'
            )
            """contact_email and keyring arguments for the Emporia Vue server."""

            cls.contact_email: str = cls.credentials.contact_email
            """Email address to appear in submeter bill footer."""

            cls.ev_system: str = cls.credentials.ev_system
            """keyring system argument for the Emporia Vue server."""

            cls.ev_username: str = cls.credentials.ev_username
            """keyring username argument for the Emporia Vue server."""

            cls.tariffs: dict[str, str] = cls.config_data['tariffs']
            """Tariff settings."""

            cls.pge_bev_tariff_url: str = cls.tariffs['pge_bev_tariff_url']
            """URL of PG&E BEV PDF tariff file."""

            cls.pge_bev_tariff_dir: Path = Path(cls.tariffs['pge_bev_tariff_dir'])
            """PG&E BEV tariff download directory."""

            cls.healthchecks_url: str = cls.tariffs['healthchecks_url']
            """URL for pinging https://healthchecks.io/."""

            cls.links: dict[str, str] = cls.config_data['links']
            """Further information links."""

            cls.links['evbilling_source'] = cls.links['evbilling_source'].replace(
                '{__version__}', __version__
            )

            cls.pge_reference_urls: tuple[str, ...] = tuple(
                cls.links[url] for url in cls.links['pge_reference_urls']
            )
            """'Further information' PG&E links in submeter bill PDF files"""

            cls.cpsf_reference_urls: tuple[str, ...] = tuple(
                cls.links[url] for url in cls.links['cpsf_reference_urls']
            )
            """'Further information' CleanPowerSF links in submeter bill PDF files"""

            cls.rate_info = cls.namedtuple_from_dict('RateInfo', 'rate_info')
            """cpsf_rate_change: Date mm/dd of CleanPowerSF annual rate change."""

            cls.tou_hours_mask: dict[Tou, npt.NDArray[np.bool_]] = {}
            """Time-Of-Use hour Boolean masks calculated from tou_hours ranges."""

            # Calculate tou_hours_mask[Tou.OFF_PEAK] as all other hours
            not_off_peak: npt.NDArray[np.bool_] = np.zeros(24, np.bool_)
            for tou in (Tou.PEAK, Tou.SUPER_OFF_PEAK):
                ranges = [range(start, stop) for start, stop in cls.config_data['time_of_use'][tou]]
                mask: npt.NDArray[np.bool_] = np.zeros(24, np.bool_)
                mask[list(chain(*ranges))] = True
                assert len(mask) == 24
                cls.tou_hours_mask[tou] = mask
                cls.tou_hours_mask[tou].setflags(write=False)
                not_off_peak |= mask

            cls.tou_hours_mask[Tou.OFF_PEAK] = ~not_off_peak
            cls.tou_hours_mask[Tou.OFF_PEAK].setflags(write=False)

        except KeyError as e:
            raise KeyError(
                f'{e} not found in configuration file {
                            cls.config_file}'
            ) from e

        if (sum(cls.tou_hours_mask[tou] for tou in Tou) != 1).any():  # type: ignore
            raise ValueError(
                f'Gaps or overlaps in time_of_use table ' f'in configuration file {cls.config_file}'
            )


Config.init()

if __name__ == "__main__":
    print(
        f'EVBilling configuration file {Config.config_file} successfully loaded.', file=sys.stderr
    )
