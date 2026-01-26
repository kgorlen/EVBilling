'''
evbillitems.py -- Miscellaneous PG&E bill items.

'''

__author__ = 'Keith Gorlen'
__all__ = [
    'BillPeriod',
]

import sys
import logging
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

SCRIPT_DIR: Path = Path(__file__).absolute().parent
"""Path to directory containing this Python script."""
sys.path.append(str(SCRIPT_DIR))
"""Allow evbilling CLI to import modules from script directory."""

# pylint: disable=wrong-import-position

from __init__ import __version__
from evlogger import (
    # info_msg,
    warning_msg,
    error_msg,
)
from tzlocal import get_localzone

# pylint: enable=wrong-import-position

ONE_DAY: timedelta = timedelta(days=1)
"""timedelta instance for 1 day."""
TZ_LOCAL: ZoneInfo = get_localzone()
"""zoneinfo instance for local time zone."""

logger = logging.getLogger(f'evbilling.{__name__}')


class BillPeriod:
    """Bill or rate period from-to dates."""

    def __init__(self, fr_mmddyyyy: str, to_mmddyyyy: str | None = None) -> None:
        """Initialize billing period from - to dates.

        Parameters
        ----------
        fr_mmddyyyy : str
            Period start date mm/dd/yyyy.
        to_mmddyyyy : str | None, optional
                Period end date mm/dd/yyyy, by default fr_mmddyyyy

        Raises
        ------
        ValueError if Period.len() > 133 days.

        Notes
        -----
        The period length is limited to 133 days to avoid the occurrence of two
        DST transitions in the same period.

        """
        self.fr: date
        """First date of period."""
        self.to: date
        """Last date of period."""
        self.to_dst: bool | None = None
        """ True if transition to DST occurs during billing period,
        False if transition from DST,  None if no transition."""
        self.dst_hours: int | None = None
        """Number of hours from start of billing period to DST transition, None
        if no transition."""

        try:
            fr = list(map(int, fr_mmddyyyy.split('/')))
            self.fr = date(fr[2], fr[0], fr[1])
            if to_mmddyyyy is None:
                self.to = self.fr
            else:
                to = list(map(int, to_mmddyyyy.split('/')))
                self.to = date(to[2], to[0], to[1])

        except ValueError as err:
            warning_msg(logger, f'Date ValueError in {fr_mmddyyyy} - {to_mmddyyyy}: {err}')
            return

        if self.to < self.fr:
            error_msg(
                logger, f'{fr_mmddyyyy} - {to_mmddyyyy} Billing period end date before start date'
            )
            return

        if len(self) > 133:
            raise ValueError(f'Period {str(self)} length {len(self)} exceeds 133 days')

        if (mod24 := self.len_hours() % 24) == 0:
            return  # No transition to/from DST in period

        self.to_dst = (
            mod24 == 23
        )  # mod24 == 23 if transition to DST, mod24 == 1 if transition from DST
        logger.info(f'DST {"start" if self.to_dst else "end"} during billing period {self}.')
        start_dt = datetime.combine(self.fr, time.min, tzinfo=ZoneInfo(str(TZ_LOCAL)))

        # Count hours to DST transition.

        for hours in range(1, self.len_hours()):
            if (start_dt + timedelta(hours=hours)).dst() != start_dt.dst():
                self.dst_hours = hours
                break
        else:
            assert False, f'Failed to find DST transition in BillPeriod {self}'

        logger.info(
            f'DST {"start" if self.to_dst else "end"} at {self.dst_hours//24} days '
            f'{self.dst_hours%24} hours after {start_dt}.'
        )

    def __hash__(self) -> int:
        """Return hash of BillPeriod instance."""
        return hash((self.fr, self.to, self.to_dst, self.dst_hours))

    def __len__(self) -> int:
        """Return number of days in billing period, inclusive."""
        return (self.to - self.fr) // ONE_DAY + 1

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BillPeriod):
            return NotImplemented
        return self.fr == other.fr and self.to == other.to

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, BillPeriod):
            return NotImplemented
        return self.fr != other.fr or self.to != other.to

    def __str__(self) -> str:
        return f'{self.str_fr()} - {self.str_to()}'

    def str_fr(self) -> str:
        """Return BillPeriod from date as MM/DD/YYYY string."""
        return f'{self.fr.month}/{self.fr.day}/{self.fr.year}'

    def str_to(self) -> str:
        """Return BillPeriod to date as MM/DD/YYYY string."""
        return f'{self.to.month}/{self.to.day}/{self.to.year}'

    def len_hours(self) -> int:
        """Return the length of the billing period in hours."""
        start_utc, end_utc = self.to_datetime_utc()
        return (end_utc - start_utc) // timedelta(hours=1)

    def date_range(self) -> list[date]:
        """Return list of date instances in billing period range."""
        return [self.fr + timedelta(days=i) for i in range(len(self))]

    def to_datetime_utc(self) -> tuple[datetime, datetime]:
        """Return billing period start and end datetime instances in UTC.

        Notes
        -----
        End datetime includes midnight of date after self.to.  Do not include
        when calling PyEmVue functions.
        """
        return (
            datetime.combine(self.fr, time.min, tzinfo=TZ_LOCAL).astimezone(timezone.utc),
            datetime.combine(self.to + ONE_DAY, time.min, tzinfo=TZ_LOCAL).astimezone(timezone.utc)
        )
