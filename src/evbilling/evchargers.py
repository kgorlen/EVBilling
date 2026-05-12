'''
evchargers.py -- Emporia Vue EV chargers configuration.

'''

__author__ = 'Keith Gorlen'
__all__ = [
    'BillPeriod',
    'EVCharger',
]

import sys
import logging
from pathlib import Path
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import re
import json
from collections import defaultdict
from typing import NamedTuple, Optional

SCRIPT_DIR: Path = Path(__file__).absolute().parent
"""Path to directory containing this Python script."""
sys.path.append(str(SCRIPT_DIR))
"""Allow evbilling CLI to import modules from script directory."""

# pylint: disable=wrong-import-position

from __init__ import __version__
from evlogger import info_msg, warning_msg, error_msg
from evsettings import Config, LoginError
from evunits import RE_DATE, Kilowatts
from evbillperiod import BillPeriod
import keyring
from tzlocal import get_localzone
import numpy as np
import numpy.typing as npt
from pyemvue import PyEmVue  # type: ignore[import-untyped]
from pyemvue.device import VueDeviceChannel, VueDevice  # type: ignore[import-untyped]
from pyemvue.enums import Scale, Unit  # type: ignore[import-untyped]

# pylint: enable=wrong-import-position


ONE_DAY: timedelta = timedelta(days=1)
"""timedelta instance for 1 day."""
TZ_LOCAL: ZoneInfo = get_localzone()
"""zoneinfo instance for local time zone."""

logger = logging.getLogger(f'evbilling.{__name__}')


class EVCharger(NamedTuple):
    """EV charger service start date, power rating, Emporia Vue data channel, and Owner email."""

    evse_id: str
    """Electric Vehicle Service Equipment (EVSE) ID."""
    on_dt: date
    """Date EV charger was placed into service."""
    kW: Kilowatts
    """EV charger power rating."""
    channel: VueDeviceChannel
    """EV charger channel."""
    owner_emails: list[str] = []
    """List of owner email addresses."""


class EnergyMonitor:
    """Energy monitor configuration."""

    def __init__(self) -> None:
        """Log into Emporia Vue AWS server.

        Raises
        ------
        LookupError
            Emporia Vue password not found.
        LoginError
            Login to Emporia Vue server failed.
        LookupError
            No Emporia Vue devices found.
        LookupError
            No Emporia Vue channels found.
        """
        self.vue = PyEmVue()
        """Emporia Vue instance."""
        self.device_info: dict[str, str | int] = {}
        """Device name, firmware, gid, manufacturer ID, model."""
        self.period_end_date: date
        """PG&E bill period end date."""
        self.evse_file: Path | None
        """EV service equipment (charger) configuration .json file."""
        self.channels: dict[str, VueDeviceChannel] = {}
        """self.channels[channel_num] = VueDeviceChannel object."""
        self.chargers: dict[str, EVCharger] = {}
        """self.chargers[evse_id] = EVCharger object."""
        self.merged_channels: dict[str, list[VueDeviceChannel]] = defaultdict(list)
        """self.merged_channels[parent_channel_number] = [child VueDeviceChannel objects]."""
        self.total_evse_kW: Kilowatts = Kilowatts(0.0)
        """Total EV charger power rating."""

        info_msg(logger, 'Logging into Emporia Vue AWS server ...')
        logger.info('Getting password from keyring ...')
        password = keyring.get_password(Config.ev_system, Config.ev_username)
        if not password:
            if password is None:
                error_msg(
                    logger,
                    f'keyring.get_password("{Config.ev_system}", '
                    f'"{Config.ev_username}") Failed.\n',
                )
            else:
                error_msg(
                    logger,
                    f'keyring.get_password("{Config.ev_system}", '
                    f'"{Config.ev_username}") Returned empty password.\n',
                )
            info_msg(
                logger,
                f'Set Emporia Vue password with the command:\n'
                f'\tkeyring set {Config.ev_system} {Config.ev_username}',
            )
            raise LookupError(f'{Config.ev_system} {Config.ev_username} password not found.')

        logger.info(f'Logging into {Config.ev_system} as {Config.ev_username} ...')
        tokenfile = tempfile.TemporaryFile(delete_on_close=False)
        try:
            self.vue.login(
                username=Config.ev_username, password=password, token_storage_file=tokenfile.name
            )
        except Exception as e:
            raise LoginError(f'Login to {Config.ev_system} failed: {e}') from e

        logger.info('Getting Emporia Vue details ...')
        devices: list[VueDevice] = self.vue.get_devices()
        vdev: VueDevice | None = next((d for d in devices if d.device_name), None)
        if not vdev:
            raise LookupError('No Emporia Vue devices found.')

        setattr(
            self,
            'device_info',
            {
                key: getattr(vdev, key)
                for key in (
                    'device_name',
                    'firmware',
                    'device_gid',
                    'manufacturer_id',
                    'model',
                )
            },
        )

        vdev = next((d for d in devices if not d.device_name and d.channels), None)
        if not vdev:
            raise LookupError('No Emporia Vue channels found.')

        self.channels: dict[str, VueDeviceChannel] = {
            chnl.channel_num: chnl for chnl in vdev.channels
        }

        info_msg(
            logger,
            f'Log in OK, current Emporia Vue details for device '
            f'{self.device_info["device_name"]} loaded.',
        )

    def discover_chargers(self, period_end_date: date, evse_file: Optional[Path] = None) -> None:
        """Obtain EV charger configuration from Emporia Vue server or from .json file.

        Parameters
        ----------
        period_end_date : date
            PG&E bill period end date.
        evse_file: Path
            EV charger configuration .json file or None to force use of current
            configuration.

        Raises
        ------
        ValueError
            Invalid device name.
            Invalid service start date in device name.
        LookupError
            No EV charging devices found.
        """
        self.period_end_date = period_end_date
        """PG&E bill period end date."""
        self.evse_file = evse_file
        """EV charger configuration .json file."""

        self.chargers = {}
        """self.chargers[evse_id] = EVCharger object."""
        self.merged_channels = defaultdict(list)
        """self.merged_channels[parent_channel_number] = [child VueDeviceChannel objects]."""
        self.total_evse_kW = Kilowatts(0.0)
        """Total EV charger power rating."""

        if evse_file and evse_file.exists():
            info_msg(
                logger,
                f'Using restored EV charger configuration as of ' f'{self.period_end_date}.',
            )
            self.restore()
            return

        if date.today() - period_end_date > timedelta(days=31):
            warning_msg(
                logger,
                'Current EV charger configuration more than 31 days old; may be out of date.',
            )

        logger.info('Discovering EV charging devices ...')
        device_usage_dict = self.vue.get_device_list_usage(
            deviceGids=str(self.device_info['device_gid']),
            instant=None,
            scale=Scale.MINUTES_15.value,
            unit=Unit.KWH.value,
        )

        for device in device_usage_dict[int(self.device_info['device_gid'])].channels.values():
            if device.name[0:3] == 'OFF':
                logger.info(f'{device.name} skipped.')
                continue

            if device.name in ('Main', 'Balance'):
                continue

            if m := re.match(
                rf'\s*([^\s]+)\s+(\d+.\d+)\s*kW\s+{RE_DATE}[^[]*(?:\[(.*)\])?', device.name
            ):
                evsid, kW_str, on_mmddyyy, email_str = m.groups()

                try:
                    on_dt: date = datetime.strptime(on_mmddyyy, '%m/%d/%Y').date()
                except ValueError as e:
                    raise ValueError(
                        f'Invalid service start date "{on_mmddyyy}" '
                        f'in device name: "{device.name}"'
                    ) from e

                kW: Kilowatts = Kilowatts(kW_str)
                owner_emails: list[str] = re.split(r'[\s,]+', email_str) if email_str else []

                self.chargers[evsid] = EVCharger(
                    evsid,
                    on_dt,
                    kW,
                    self.channels[device.channel_num],
                    owner_emails,
                )

                metered_kW_rating: Kilowatts | None = self.get_peak_kW(evsid, period_end_date)

                if metered_kW_rating is not None:
                    tolerance: Kilowatts = self.chargers[evsid].kW * Config.power_rating_tolerance
                    logger.info(
                        f'Charger {evsid} metered power rating: {metered_kW_rating:.2f} kW, '
                        f'configured: {kW:.1f} kW, tolerance: {tolerance:.2f} kW '
                        f'({Config.power_rating_tolerance:.0%}).'
                    )

                    if abs(metered_kW_rating - kW) > tolerance:
                        warning_msg(
                            logger,
                            f'Charger {evsid} metered power rating {metered_kW_rating:.2f} kW '
                            f'differs from the nominal rating in the circuit name ({kW:.1f} kW) '
                            f'by more than {Config.power_rating_tolerance:.0%}; '
                            f'using nominal rating {kW:.1f} kW; check charger and circuit name.',
                        )

                    # To use metered_kW_rating instead of nominal kW rating:
                    # else:
                    #     self.chargers[evsid] = EVCharger(
                    #         evsid,
                    #         on_dt,
                    #         metered_kW_rating,
                    #         self.channels[device.channel_num],
                    #         owner_emails,
                    #     )

            else:
                raise ValueError(f'Invalid device name: "{device.name}".')

        if len(self.chargers) == 0:
            raise LookupError('No EV charging devices found.')

        self.total_evse_kW = sum((charger.kW for charger in self.chargers.values()), Kilowatts(0.0))

        merged: set[str] = set(
            charger.channel.channel_num
            for charger in self.chargers.values()
            if charger.channel.type == 'Merged'
        )
        for chnl in self.channels.values():
            if chnl.parent_channel_num and chnl.parent_channel_num in merged:
                self.merged_channels[chnl.parent_channel_num].append(chnl)

        self.log_chargers()
        self.save()
        info_msg(logger, 'Current EV charger configuration loaded.')

    def log_chargers(self) -> None:
        """Log discovered or restored EV chargers."""
        logger.info('EV chargers found:')
        for evse_id, charger in self.chargers.items():
            logger.info(
                f'   {evse_id} {charger.kW:5.2f}kW on channel {charger.channel.channel_num} '
                f'owner_emails: {", ".join(charger.owner_emails)}'
            )

        logger.info('Merged channels:')
        for parent_chnl_num, child_chnls in self.merged_channels.items():
            logger.info(
                f'   {parent_chnl_num}: {", ".join(chnl.channel_num for chnl in child_chnls)}'
            )

    def download_usage_data(
        self, evse_id: str, period: BillPeriod, zero_fill: bool = False
    ) -> npt.NDArray[np.float32] | None:
        """Download raw usage data from Emporia server.

        Parameters
        ----------
        evse_id : str
            Electric Vehicle Service Equipment (EVSE) ID.
        period : BillPeriod
            Usage period.
        zero-fill : bool
            Return zero-filled array if no data, otherwise None.

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
        """Rate period start in local time."""
        len_hours: int = period.len_hours()
        """Length of rate period in hours."""
        hourly_kWh = np.zeros((len(period), 24), dtype=np.float32)
        """Hourly usage for all channels in kWh."""
        chnl: VueDeviceChannel = self.chargers[evse_id].channel
        """EV charger channel."""
        chnl_kWh: list[float] = []
        """Data returned by get_chart_usage()."""
        chunk_start_utc: datetime = start_utc
        """Start time in UTC of data chunk."""

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
            chunk_kWh, start_time = self.vue.get_chart_usage(
                chnl,
                chunk_start_utc,
                chunk_end_utc,
                scale=Scale.HOUR.value,
                unit=Unit.KWH.value,
            )

            assert len(chunk_kWh) > 0, 'get_chart_usage() returned no data.'
            assert isinstance(
                start_time, datetime
            ), f'get_chart_usage() start_time {start_time} is not a datetime object.'

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
                logger.info(f'DST started at {start_utc.astimezone(TZ_LOCAL)
                                        + timedelta(hours=dst_hours)}.')
            else:  # DST ended during billing period: the hour from 1 to 2 AM occurs twice
                if chnl_kWh[dst_hours - 1] is not None:
                    chnl_kWh[dst_hours] += chnl_kWh[
                        dst_hours - 1
                    ]  # Add the first 1 to 2 AM usage to the second
                del chnl_kWh[dst_hours - 1]  # and delete the first 1 to 2 AM usage
                logger.info(f'DST ended at {end_utc.astimezone(TZ_LOCAL)
                                        + timedelta(hours=dst_hours)}.')

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
                if not zero_fill:
                    return None

                hourly_kWh.fill(0)
                hourly_kWh.setflags(write=False)
                return hourly_kWh

        np.nan_to_num(hourly_kWh, copy=False)
        logger.debug(
            f'{evse_id} channel: {chnl.channel_num} '
            f'data:\n{np.array2string(hourly_kWh, precision=4, suppress_small=True)}'
        )

        hourly_kWh.setflags(write=False)
        return hourly_kWh

    def get_peak_kW(self, evse_id: str, end_date: date) -> Kilowatts | None:
        """Get peak kW for EV charger during billing period.

        Parameters
        ----------
        evse_id : str
            Electric Vehicle Service Equipment (EVSE) ID.
        end_date : date
            End date for the billing period.

        Returns
        -------
        Peak 15-minute average kW for EV charger or None if insufficient usage data.
        """
        peak_kW: Kilowatts = Kilowatts(0.0)
        """Peak kW for EV charger."""
        samples: int = 0
        """Number of 15-minute samples with usage data > threshold."""
        on_utc: datetime = datetime.combine(
            self.chargers[evse_id].on_dt, time.min, tzinfo=TZ_LOCAL
        ).astimezone(timezone.utc)
        """UTC time EV charger was placed into service."""
        chnl: VueDeviceChannel = self.chargers[evse_id].channel
        """EV charger channel."""
        end_utc: datetime = datetime.combine(
            end_date + ONE_DAY, time.min, tzinfo=TZ_LOCAL
        ).astimezone(timezone.utc)
        chunk_len: timedelta = timedelta(days=7)
        """get_chart_usage() time period length limit."""
        chunk_end_utc: datetime = end_utc
        """End time in UTC of data chunk."""
        chunk_start_utc: datetime = max(chunk_end_utc - chunk_len, on_utc)
        """Start time in UTC of data chunk."""
        threshold: Kilowatts = self.chargers[evse_id].kW * Config.power_rating_sample_threshold
        """Minimum kW for valid EV charger power rating samples."""
        logger.info(
            f'Getting peak kW for {evse_id}, '
            f'nominal power rating: {self.chargers[evse_id].kW:.2f} kW, '
            f'threshold: {threshold:.2f} kW ({Config.power_rating_sample_threshold:.0%}) ...'
        )

        # Step backwards from end_date in 7-day chunks until we have at least 4
        # samples over the minimum kWh.

        while (
            # Require at least 4 (default) samples to consider peak_kW valid.
            samples < Config.power_rating_samples
            # Don't consider readings before charger was placed into service.
            and chunk_start_utc > on_utc
            # Don't exceed Emporia 15-minute data retention limit of 1 year.
            and datetime.now(timezone.utc) - chunk_end_utc < timedelta(days=360)
        ):
            logger.info(
                f'get_chart_usage(channel={chnl.channel_num}, '
                f'{chunk_start_utc=}, {chunk_end_utc=}, '
                f'scale={Scale.MINUTES_15.value}, unit={Unit.KWH.value})'
            )
            chunk_kWh, start_time = self.vue.get_chart_usage(
                chnl,
                chunk_start_utc,
                chunk_end_utc - timedelta(seconds=1),  # Exclude midnight
                scale=Scale.MINUTES_15.value,
                unit=Unit.KWH.value,
            )

            assert len(chunk_kWh) > 0, 'get_chart_usage() returned no data.'
            assert isinstance(
                start_time, datetime
            ), f'get_chart_usage() start_time {start_time} is not a datetime object.'
            assert start_time == chunk_start_utc, (
                f'Start time of Emporia usage data {start_time.astimezone(TZ_LOCAL)} '
                f'is not equal to chunk start time {chunk_start_utc.astimezone(TZ_LOCAL)}'
            )

            if all(kWh is None for kWh in chunk_kWh):
                logger.info(
                    f'{evse_id} channel {chnl.channel_num} has no readings from '
                    f'{chunk_start_utc.astimezone(TZ_LOCAL)} to '
                    f'{chunk_end_utc.astimezone(TZ_LOCAL)}.'
                )
                break

            # Reject small readings as likely idle power usage or noise.
            good_samples: list[Kilowatts] = [
                Kilowatts(kWh * 4)  # Convert kWh per 15 minutes to kW, i.e. multiply by 4
                for kWh in chunk_kWh
                if kWh is not None
                and abs(Kilowatts(kWh * 4) - self.chargers[evse_id].kW) <= threshold
            ]

            peak_kW = max(peak_kW, Kilowatts(max(good_samples, default=Kilowatts(0.0))))
            samples += len(good_samples)

            chunk_end_utc = chunk_start_utc
            chunk_start_utc = max(chunk_start_utc - chunk_len, on_utc)

        logger.info(
            f'{chnl.name} '
            f'channel: {chnl.channel_num} '
            f'multipier: {chnl.channel_multiplier} '
            f'peak_kW: {peak_kW:.2f} kW'
        )

        return round(peak_kW, 2) if peak_kW > Kilowatts(0.0) else None

    def save(self) -> None:
        """Save EV charger configuration to .json file."""
        if not self.evse_file:
            return

        logger.info(f'Saving EV charger configuration to "{self.evse_file}" ...')

        evse_config: dict[str, dict[str, str | dict | list]] = {}
        for evse_id, charger in self.chargers.items():
            evse_config[evse_id] = {
                'kW': str(charger.kW),
                'service_start_date': charger.on_dt.strftime('%m/%d/%Y'),
                'channel': charger.channel.as_dictionary(),
            }

            if charger.owner_emails:
                evse_config[evse_id]['owner_emails'] = charger.owner_emails

        merged_channels: dict[str, list[dict]] = {}
        for parent_chnl_num, child_chnls in self.merged_channels.items():
            merged_channels[parent_chnl_num] = [chnl.as_dictionary() for chnl in child_chnls]

        config = {
            'period_end_date': self.period_end_date.strftime('%Y-%m-%d'),
            'total_evse_kW': f'{self.total_evse_kW:.2f}',
            'device_info': self.device_info,
            'chargers': evse_config,
        }
        if merged_channels:
            config['merged_channels'] = merged_channels

        with open(self.evse_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, sort_keys=True)

    def update_json(self, js: dict) -> dict:
        """Update EV charger configuration json structure from older version.

        Parameters
        ----------
        js : dict
            EV charger configuration json structure.

        Returns
        -------
        Updated EV charger configuration json structure.
        """
        info_msg(logger, f'Updating EV charger configuration structure of {self.evse_file} ...')

        service_start_dates: dict[str, str] = {
            'PWS-HOA': '6/13/2024',
            'PWS-203-P07': '4/23/2025',
            'PWS-204-P26': '5/27/2025',
            'PWS-403-P20': '2/21/2025',
            'PWS-404-P06': '6/13/2024',
            'PWS-405-P14': '2/21/2025',
        }

        js['EVE_version'] = '2.0'  # New EV service equipment configuration version
        chargers: dict = js['chargers']
        new_chargers = {}

        for evse_id in chargers.keys():
            new_chargers[evse_id] = {
                'kW': round(float(chargers[evse_id][0]), 2),
                'service_start_date': service_start_dates[evse_id],
                'channel': chargers[evse_id][1],
            }

        js['chargers'] = new_chargers
        js['total_evse_kW'] = round(float(js["total_evse_kW"]), 2)

        assert self.evse_file is not None
        with open(self.evse_file, 'w', encoding='utf-8') as f:
            json.dump(js, f, indent=4, sort_keys=True)
        return js

    def restore(self) -> None:
        """Restore saved EV charger configuration from .json file.

        Raises
        ------
        ValueError
            Restore EV charger configuration from "{evse_file}" failed
        """
        if not self.evse_file:
            return

        logger.info(f'Restoring EV charger configuration from "{self.evse_file}" ...')
        with open(self.evse_file, 'r', encoding='utf-8') as f:
            js = json.load(f)

        if js['device_info']['device_gid'] != self.device_info['device_gid']:
            raise ValueError(
                f'Restore EV charger configuration from "{self.evse_file}" failed: '
                f'Emporia Vue device ID {self.device_info['device_gid']} '
                f'not equal saved ID {js['device_info']['device_gid']}'
            )

        # Detect old json structure and update
        evse_id = next(iter(js['chargers'].keys()))
        if isinstance(js['chargers'][evse_id], list):
            js = self.update_json(js)

        self.period_end_date = datetime.strptime(js['period_end_date'], '%Y-%m-%d').date()
        self.total_evse_kW = Kilowatts(js['total_evse_kW'])

        chargers: dict = js['chargers']
        for evse_id in chargers.keys():
            self.chargers[evse_id] = EVCharger(
                evse_id,
                datetime.strptime(chargers[evse_id]['service_start_date'], '%m/%d/%Y').date(),
                Kilowatts(chargers[evse_id]['kW']),
                self.channels[chargers[evse_id]['channel']['channelNum']],
                chargers[evse_id]['owner_emails'] if 'owner_emails' in chargers[evse_id] else [],
            )

        if 'merged_channels' not in js:
            self.log_chargers()
            return

        for parent_chnl_num, child_chnls in js['merged_channels'].items():
            self.merged_channels[parent_chnl_num] = [
                self.channels[chnl['channelNum']] for chnl in child_chnls
            ]

        self.log_chargers()
