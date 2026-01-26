'''
evchargers.py -- Emporia Vue EV chargers configuration.

'''

__author__ = 'Keith Gorlen'
__all__ = [
    'BillPeriod',
    'EVChargers',
]

import sys
import logging
from pathlib import Path
import tempfile
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import re
import json
from typing import NamedTuple

SCRIPT_DIR: Path = Path(__file__).absolute().parent
"""Path to directory containing this Python script."""
sys.path.append(str(SCRIPT_DIR))
"""Allow evbilling CLI to import modules from script directory."""

# pylint: disable=wrong-import-position

from __init__ import __version__
from evlogger import info_msg, warning_msg, error_msg
from evsettings import Config
from evunits import Kilowatts
from evbillperiod import BillPeriod
import keyring
from tzlocal import get_localzone
import numpy as np
import numpy.typing as npt
from pyemvue import PyEmVue
from pyemvue.device import VueDeviceChannel
from pyemvue.enums import Scale, Unit

# pylint: enable=wrong-import-position


ONE_DAY: timedelta = timedelta(days=1)
"""timedelta instance for 1 day."""
TZ_LOCAL: ZoneInfo = get_localzone()
"""zoneinfo instance for local time zone."""

logger = logging.getLogger(f'evbilling.{__name__}')


class EVChargerInfo(NamedTuple):
    """EV charger power rating and Emporia Vue data channels."""

    kW: Kilowatts
    channels: list[VueDeviceChannel]


class UsageData(NamedTuple):
    """Emporia Vue usage data"""

    data: npt.NDArray[np.float32]
    """data[day, hour] = sum of kWh for all device channels."""
    empty_channels: list[VueDeviceChannel]
    """List of channels with no data (all NaN or None)."""


class EnergyMonitor:
    """Energy monitor configuration."""

    def __init__(self) -> None:
        """Log into Emporia Vue AWS server.

        Raises
        ------
        LookupError
            Emporia Vue password not found.
        """
        self.vue = PyEmVue()
        """Emporia Vue instance."""
        self.device_info: dict[str, str | int]
        """Device name, firmware, gid, manufacturer ID, model."""

        info_msg(logger, 'Logging into Emporia Vue AWS server ...')
        logger.info('Getting password from keyring ...')
        password = keyring.get_password(Config.ev_system, Config.ev_username)
        if password is None:
            error_msg(
                logger,
                f'keyring.get_password("{Config.ev_system}", '
                f'"{Config.ev_username}") Failed\n'
                f'Set Emporia Vue password with the command:\n'
                f'\tkeyring set {Config.ev_system} {Config.ev_username}',
            )
            raise LookupError(f'{Config.ev_system} {Config.ev_username} password not found.')

        logger.info(f'Logging into {Config.ev_system} as {Config.ev_username} ...')
        tokenfile = tempfile.TemporaryFile(delete=True, delete_on_close=False)
        self.vue.login(
            username=Config.ev_username, password=password, token_storage_file=tokenfile.name
        )

        logger.info('Getting Emporia Vue details ...')
        devices = self.vue.get_devices()
        for device in devices:
            if device.device_name:
                setattr(
                    self,
                    'device_info',
                    {
                        key: getattr(device, key)
                        for key in (
                            'device_name',
                            'firmware',
                            'device_gid',
                            'manufacturer_id',
                            'model',
                        )
                    },
                )

        info_msg(logger, 'Log in OK, current Emporia Vue details loaded.')


class EVChargers:
    """EV charger configuration."""

    def __init__(
        self, energy_monitor: EnergyMonitor, period_end_date: date, eve_file: Path
    ) -> None:
        """Obtain EV charger configuration from Emporia Vue server or from .json file.

        Parameters
        ----------
        energy_monitor : EnergyMonitor
            EnergyMonitor instance.
        period_end_date : date
            PG&E bill period end date.
        eve_file: Path
            EV charger configuration .json file.


        Raises
        ------
        LookupError
            No EV charging devices found.
        """
        self.energy_monitor: EnergyMonitor = energy_monitor
        self.period_end_date: date = period_end_date
        """PG&E bill statement date,YYYY/MM/DD."""
        self.eve_file: Path = eve_file
        """EV charger configuration .json file."""
        self.chargers: dict[str, EVChargerInfo] = {}
        """EV charger configuration."""
        self.total_evse_kW = Kilowatts(0)
        """Total EV charger power (kW) ratings."""

        if self.eve_file.exists():
            info_msg(
                logger,
                f'Using restored EV charger configuration as of ' f'{self.period_end_date}.',
            )
            self.restore()
            return

        if date.today() - self.period_end_date > timedelta(days=31):
            warning_msg(logger, 'Current EV charger configuration may be out of date.')

        logger.info('Discovering EV charging devices ...')
        devices = energy_monitor.vue.get_devices()
        for device in devices:
            if not device.device_name:
                for chnl in sorted(device.channels, key=lambda ch: ch.channel_num):
                    if chnl.name is not None:
                        if m := re.match(r'(.+)\s(\d+.\d+)\s*kW\b', chnl.name):
                            charger_name, kW = m.groups()
                        else:
                            raise ValueError(
                                f'Invalid charger name: {chnl.name}, '
                                f'must be like "my-name 8.32kW"'
                            )

                        if charger_name[0:3] != 'OFF':
                            if charger_name not in self.chargers:
                                self.chargers[charger_name] = EVChargerInfo(Kilowatts(kW), [])
                                self.total_evse_kW += self.chargers[charger_name].kW
                            self.chargers[charger_name].channels.append(chnl)
                        else:
                            logger.info(f'{charger_name} skipped.')

        if len(self.chargers) == 0:
            raise LookupError('No EV charging devices found.')

        self.log_chargers()
        self.save()
        info_msg(logger, 'Current EV charger configuration loaded.')

    def log_chargers(self) -> None:
        """Log discovered or restored EV chargers."""
        logger.info('EV chargers found:')
        for evse_id, info in self.chargers.items():
            logger.info(
                f'   {evse_id} {info.kW:5.2f}kW on channel(s) '
                f'{",".join(chnl.channel_num for chnl in info.channels)}'
            )

    def download_usage_data(self, evse_id: str, period: BillPeriod) -> UsageData:
        """Download raw usage data from Emporia server.

        Parameters
        ----------
        evse_id : str
            Electric Vehicle Service Equipment (EVSE) ID.
        period : BillPeriod
            Usage period.

        Returns
        -------
        UsageData(ndarray((len(period, 24), dtype=np.float32), int),
            [VueDeviceChannel objects that are all None])

        """
        logger.info(f'Downloading data for period {period} for EV charger {evse_id} ...')

        chunk_len: timedelta = timedelta(days=32)
        """get_chart_usage() time period length limit."""
        start_utc, end_utc = period.to_datetime_utc()
        """Rate period start and end datetime in UTC."""
        start_local: datetime = start_utc.astimezone(TZ_LOCAL)
        """Rate period start in UTC."""
        len_hours: int = period.len_hours()
        """Length of rate period in hours."""
        hourly_kWh = np.zeros((len(period), 24), dtype=np.float32)
        """Hourly usage for all channels in kWh."""
        channels: list[VueDeviceChannel] = self.chargers[evse_id].channels
        """List of charger channels."""
        empty_channels: list[VueDeviceChannel] = []
        """List of channels with no data."""
        chnl: VueDeviceChannel
        """Single phase FiftyAmp or multi-phase Merged channel."""
        chnl_kWh: list[float] = []
        """Data returned by get_chart_usage()."""
        chunk_start_utc: datetime = start_utc
        """Start time in UTC of data chunk."""

        if len(channels) == 1:
            chnl = channels[0]
            assert chnl.type == 'FiftyAmp', f'FiftyAmp channel for {evse_id} not found, '
            'check nnnncustbillmmddyyyy-EVE.json file.'
        else:
            chnl = next((ch for ch in channels if ch.type == 'Merged'), None)
            assert (
                chnl is not None
            ), f'Merged channel for {evse_id} not found, check nnnncustbillmmddyyyy-EVE.json file.'

        while len(chnl_kWh) < len_hours:
            chunk_end_utc: datetime = (
                chunk_start_utc
                + min(end_utc - chunk_start_utc, chunk_len)
                - timedelta(seconds=1)  # Exclude midnight
            )

            logger.info(
                f'get_chart_usage(channel={chnl.channel_num}, '
                f'{chunk_start_utc=}, {chunk_end_utc=}, '
                f'scale={Scale.HOUR.value}, unit={Unit.KWH.value})'
            )
            chunk_kWh, start_time = self.energy_monitor.vue.get_chart_usage(
                chnl,
                chunk_start_utc,
                chunk_end_utc,
                scale=Scale.HOUR.value,
                unit=Unit.KWH.value,
            )

            assert len(chunk_kWh) > 0, 'get_chart_usage() returned no data.'

            chnl_kWh.extend(chunk_kWh)
            assert start_time == chunk_start_utc, (
                f'Start time of Emporia usage data {start_time.astimezone(TZ_LOCAL)} '
                f'is not equal to chunk start time {chunk_start_utc.astimezone(TZ_LOCAL)}'
            )

            chunk_start_utc = start_utc + timedelta(hours=len(chnl_kWh))

        logger.info(
            f'{chnl.name} '
            f'channel: {chnl.channel_num} '
            f'multipier: {chnl.channel_multiplier} '
            f'start: {start_local} {len(chnl_kWh)} hours.'
        )
        assert (
            len(chnl_kWh) == len_hours
        ), f'len(chnl_kWh) {len(chnl_kWh)} not equal to hours in period {len_hours}'

        # Handle DST transition during period

        dst_hours = period.dst_hours  # Hours until DST transition

        if dst_hours is not None:  # DST began or ended during billing period
            if period.to_dst:  # DST began: the hour from 2 to 3 AM is skipped
                chnl_kWh.insert(dst_hours - 1, 0.0)  # insert an hour of zero usage at 2 AM
                logger.info(
                    f'DST started at {start_utc.astimezone(TZ_LOCAL)
                                        + timedelta(hours=dst_hours)}.'
                )
            else:  # DST ended during billing period: the hour from 1 to 2 AM occurs twice
                if chnl_kWh[dst_hours - 1] is not None:
                    chnl_kWh[dst_hours] += chnl_kWh[
                        dst_hours - 1
                    ]  # Add the first 1 to 2 AM usage to the second
                del chnl_kWh[dst_hours - 1]  # and delete the first 1 to 2 AM usage
                logger.info(
                    f'DST ended at {end_utc.astimezone(TZ_LOCAL)
                                        + timedelta(hours=dst_hours)}.'
                )

        # get_chart_usage() returns None for hours with missing data
        # np.array() converts None to nan, np.nan_to_num converts nan to zero
        hourly_kWh = np.array(chnl_kWh, dtype=np.float32).reshape((len(period), 24))

        # Check for no data

        if nans := np.count_nonzero(np.isnan(hourly_kWh)):
            logger.info(
                f'{evse_id} channel {chnl.channel_num} is missing readings for '
                f'{nans} of {hourly_kWh.size} hours.'
            )
            if nans == hourly_kWh.size:
                logger.info(f'{evse_id} channel {chnl.channel_num} has no readings.')
                empty_channels.append(chnl)

        np.nan_to_num(hourly_kWh, copy=False)
        logger.debug(
            f'{evse_id} channel: {chnl.channel_num} '
            f'data:\n{np.array2string(hourly_kWh, precision=4, suppress_small=True)}'
        )

        hourly_kWh.setflags(write=False)
        return UsageData(hourly_kWh, empty_channels)

    def save(self) -> None:
        """Save EV charger configuration to .json file."""
        logger.info(f'Saving EV charger configuration to "{self.eve_file}" ...')

        evse_config: dict[str, tuple[str, list[dict]]] = {}
        for evse_id, info in self.chargers.items():
            evse_config[evse_id] = (
                str(info.kW),
                [chnl.as_dictionary() for chnl in info.channels],
            )

        with open(self.eve_file, 'w', encoding="utf-8") as f:
            json.dump(
                {
                    'period_end_date': self.period_end_date.strftime("%Y-%m-%d"),
                    'total_evse_kW': str(self.total_evse_kW),
                    'device_info': self.energy_monitor.device_info,
                    'chargers': evse_config,
                },
                f,
                indent=4,
                sort_keys=True,
            )

    def restore(self) -> None:
        """Restore saved EV charger configuration from .json file.

        Raises
        ------
        ValueError
            Restore EV charger configuration from "{eve_file}" failed
        """
        logger.info(f'Restoring EV charger configuration from "{self.eve_file}" ...')
        with open(self.eve_file, 'r', encoding="utf-8") as f:
            js = json.load(f)

        if js['device_info']['device_gid'] != self.energy_monitor.device_info['device_gid']:
            raise ValueError(
                f'Restore EV charger configuration from "{self.eve_file}" failed: '
                f'Emporia Vue device ID {self.energy_monitor.device_info['device_gid']} '
                f'not equal saved ID {js['device_info']['device_gid']}'
            )

        self.period_end_date = datetime.strptime(js['period_end_date'], "%Y-%m-%d").date()
        self.total_evse_kW = Kilowatts(js['total_evse_kW'])

        for evse_id, (kW, chnls) in js['chargers'].items():
            self.chargers[evse_id] = EVChargerInfo(
                Kilowatts(kW),
                [VueDeviceChannel().from_json_dictionary(chnl) for chnl in chnls],
            )

        self.log_chargers()
