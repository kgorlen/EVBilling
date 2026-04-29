'''
evsettings.py -- Initialize Config class from evbilling.toml file.

References:
    https://toml.io/en/ -- TOML: A config file format for humans

'''

__author__ = 'Keith Gorlen'
__all__: list[str] = [
    'LoginError',
    'Tou',
    'Config',
]

import os
import sys
from enum import StrEnum
from pathlib import Path
import tomllib
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
from evunits import Kilowatts

# pylint: enable=wrong-import-position


class LoginError(Exception):
    """Raised when login credentials are invalid."""


class Tou(StrEnum):
    """Time-Of-Use keys."""

    PEAK = 'Peak'
    OFF_PEAK = 'Off Peak'
    SUPER_OFF_PEAK = 'Super Off Peak'


# mypy: ignore-errors


def expand_path(path: str) -> Path:
    """Expand user ~ and environment variables in path.

    Parameters
    ----------
    path : str
        Path string possibly containing ~ or environment variables.

    Returns
    -------
    Path
        Expanded Path object.
    """
    return Path(os.path.expandvars(os.path.expanduser(path)))


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

    default_evmailbills_log: Path = (
        Path(user_log_dir('EVBilling', appauthor=False, ensure_exists=True)) / 'mailevbills.log'
    )
    """Default mailevbills log file."""

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

            cls.evbilling_log: Path = cls.default_evbilling_log
            """evbilling log file path."""
            cls.evtariffs_log: Path = cls.default_evtariffs_log
            """evtariffs log file path."""
            cls.evmailbills_log: Path = cls.default_evmailbills_log
            """mailevbills log file path."""
            if 'logging' in cls.config_data:
                if 'evbilling' in cls.config_data['logging']:
                    cls.evbilling_log = expand_path(cls.config_data['logging']['evbilling'])
                if 'evtariffs' in cls.config_data['logging']:
                    cls.evtariffs_log = expand_path(cls.config_data['logging']['evtariffs'])
                if 'mailevbills' in cls.config_data['logging']:
                    cls.evmailbills_log = expand_path(cls.config_data['logging']['mailevbills'])

            cls.ev_system: str = cls.config_data['credentials']['ev_system']
            """keyring system argument for the Emporia Vue server."""

            cls.ev_username: str = cls.config_data['credentials']['ev_username']
            """keyring username argument for the Emporia Vue server."""

            cls.contact_email: str = cls.config_data['contacts']['contact_email']
            """Email address to appear in submeter bill footer."""

            cls.billing_emails: list[str] = (
                _ if isinstance(_ := cls.config_data['contacts']['billing_emails'], list) else [_]
            )
            """ List of email addresses to which mailevbills sends NNNNcustbillMMDDYYYY.zip."""

            cls.smtp_server: str = cls.config_data['smtp']['smtp_server']
            """SMTP server hostname or IP address."""

            cls.smtp_port: int = cls.config_data['smtp']['smtp_port']
            """SMTP server port number."""

            cls.smtp_user: str = cls.config_data['smtp']['smtp_user']
            """SMTP server user name."""

            cls.tariffs: dict[str, str] = cls.config_data['tariffs']
            """Tariff settings."""

            cls.pge_bev_tariff_url: str = cls.tariffs['pge_bev_tariff_url']
            """URL of PG&E BEV PDF tariff file."""

            cls.pge_bev_tariff_dir: Path = expand_path(cls.tariffs['pge_bev_tariff_dir'])
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

            cls.power_rating_samples: int = 4
            """Number of EV charger power rating samples to use."""
            cls.power_rating_sample_min_kW: Kilowatts = Kilowatts(1.0)
            """Minimum kW for EV charger power rating samples."""
            cls.power_rating_tolerance_kW: Kilowatts = Kilowatts(0.25)
            """Maximum allowed difference between metered and 
            configured EV charger power ratings."""
            if 'power_rating' in cls.config_data:
                if 'samples' in cls.config_data['power_rating']:
                    cls.power_rating_samples = cls.config_data['power_rating']['samples']
                if 'sample_min_kW' in cls.config_data['power_rating']:
                    cls.power_rating_sample_min_kW = cls.config_data['power_rating'][
                        'sample_min_kW'
                    ]
                if 'tolerance_kW' in cls.config_data['power_rating']:
                    cls.power_rating_tolerance_kW = cls.config_data['power_rating']['tolerance_kW']

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
                f'{e} not found in configuration file {cls.config_file}, '
                f'see evbilling SETTINGS documentation in README.md.'
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
