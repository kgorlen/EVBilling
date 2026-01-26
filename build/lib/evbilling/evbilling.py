"""
evbilling:
- Reads and extracts billing data from PG&E/BEV-1 CleanPowerSF (CPSF) B-EV bill
  PDF files.
- Downloads hourly energy usage data for the billing period from the Emporia Vue
  server.
- Generates bills for submetered EV chargers, a.k.a Electric Vehicle Service
  Equipment (EVSE).

Copyright (C) 2024, 2025 Keith Gorlen kgorlen@gmail.com

Created on May 19, 2024

@author: Keith Gorlen kgorlen@gmail.com


References:

    Emporia Vue Gen 3 Energy Monitor:

        https://shop.emporiaenergy.com/products/emporia-vue-3-3-phase-energy-management-hub-monitor-with-8-sensors
        https://help.emporiaenergy.com/en/ https://web.emporiaenergy.com/login
        https://pypi.org/project/pyemvue/ https://github.com/magico13/PyEmVue
        https://github.com/magico13/PyEmVue/blob/master/api_docs.md

    python-docTR OCR:
        https://mindee.github.io/doctr/latest/index.html
        https://mindee.github.io/doctr/latest/modules/io.html
        https://source.opennews.org/articles/our-search-best-ocr-tool-2023

        Other:
        https://py-pdf.github.io/fpdf2/index.html -- PDF document generation
        https://apps.openei.org/USURDB -- US Utility Rate Database
        https://github.com/jbms/finance-dl/blob/master/finance_dl/pge.py --
        Retrieve PG&E PDF bills
        https://www.geeksforgeeks.org/convert-pdf-to-image-using-python/
            -- Convert PDF to Image using Python, pdf2image and poppler
        https://www.tutorialspoint.com/python-ndash-reading-contents-of-pdf-using-ocr-optical-character-recognition
            -- Using tesseract
        https://medium.com/social-impact-analytics/extract-text-from-unsearchable-pdfs-for-data-analysis-using-python-a6a2ca0866dd
            -- Using OCRmyPDF
        https://www.xpdfreader.com/about.html -- Xpdf utilities
        https://chatgpt.com/share/3e8d60a5-781e-48ec-81a3-41f5b462852c -- OCR
        Tools Comparison

Optical Character Recognitiion (OCR) errors can occur when extracting data from
PG&E/CPSF bills.  The following checks are performed to detect these errors:

    - PG&E billing period must equal CPSF billing period
    - Billing rate periods must exactly cover total billing period
    - Subscription and energy charge quantity*rate must equal $ charge
    - Total PG&E kWh and CPSF kWh must equal Total Usage kWh
    - Sum of all charges for all PG&E rate periods must equal Total PG&E
      Electric Delivery Charges
    - Sum of all charges for all CPSF rate periods must equal Total CPSF
      Electric Generation Charges

The following fields are not checked except for correct formatting:

    Account No Meter # Statement Date Due Date

Class Structure:

PGEBEV1Tariff -- PG&E Electric Schedule BEV data

Bill -- PG&E main or submeter bill
 ├─> pge_bill: PGEBillDetails
 ├─> cpsf_bill: CPSFBillDetails

BillDetails -- PG&E Electric Delivery or CleanPowerSF Electric Generation bill
 ├─> period: BillPeriod
 ├─> rate_periods: RatePeriod (multiple)
 ├── PGEBillDetails -- PG&E main or submeter bill delivery details
 ├── CPSFBillDetails -- CLeanPowerSF main or submeter bill generation details

RatePeriod -- PG&E or CPSF main or submeter charges for a rate period
 ├─> bill: Bill
 ├─> period: Period
 ├─> energy_charges: EnergyCharge (multiple)
 ├─> other_charges: OtherCharge (multiple)
 ├── PGERatePeriod -- PG&E main or submeter charges for a rate period
 │    ├─> subscription: SubscriptionCharge
 │    ├─> overage_fee: OverageFee
 │    ├─> pcia: OtherCharge
 │    ├─> energy_credits: EnergyCredit (multiple)
 ├── CPSFRatePeriod -- CPSF main or submeter charges for a rate period

Submeter -- Submeter bill
 ├─> main_bill: Bill
 ├─> submeter_bill: Bill

BillPeriod -- Bill or rate period from-to dates

SubscriptionCharge -- PG&E subscription (demand) charge, 10 kW blocks

OverageFee -- Subscription Level Overage Fee, $/kW

EnergyCharge -- Time Of Use Energy (kWh) Usage Charges

EnergyCredit -- Energy (kWh) Credit
 ├── TOUGenerationCredit -- Time Of Use Energy (kWh) Generation Credit
 ├── PCIACredit -- Bundled Power Charge Indifference Adjustment Credit

OtherCharge -- Generation credit, PCIA charge, taxes, and surcharges
 ├── OtherEnergyCharge -- Other charge based on energy (kWh) usage
 ├── OtherPctNetCharge -- Other charge based on percentage of net charges
 ├── OtherPctEnergyCharge -- Other charge based on percentage of energy usage charges

PDF -- FPDF subclass to generate submeter bill headers and footers

Dependencies (See setup.cfg for details):
    pip install fpdf2
    pip install keyring
    pip install pdfplumber
    pip install platformdirs
    pip install pyemvue
    pip install python-doctr[torch]
    pip install tzlocal

Resources:
    fonts.conf
    palace_thumbnail.jpg

Package:
    https://pybit.es/articles/how-to-package-and-deploy-cli-apps/

    pip install build
    python -m build


TODO:
    Try pdfminer or PyMuPDF instead of OCR?
    Default tou_rates to NaN instead of zero?
"""

__author__ = 'Keith Gorlen'

import os
import sys
import re
from pathlib import Path
import tempfile
import logging
from logging.handlers import RotatingFileHandler
from enum import IntEnum
from collections import namedtuple
from decimal import getcontext, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from datetime import date, datetime, time, timedelta
from itertools import groupby
from abc import ABC, abstractmethod
import functools
import copy
import shutil
import subprocess
import glob
import zipfile
from typing import NamedTuple, Optional, Generator

SCRIPT_DIR: Path = Path(__file__).absolute().parent
"""Path to directory containing this Python script."""
sys.path.append(str(SCRIPT_DIR))
"""Allow evbilling CLI to import modules from script directory."""

# pylint: disable=wrong-import-position
from __init__ import __version__
from evsettings import Config, Tou
from evunits import (
    Percent,
    SubscriptionMonths,
    Kilowatts,
    KilowattHours,
    DollarsPerKilowatt,
    DollarsPerKilowattHour,
    Dollars,
)
from evargs import Args
import evlogger
from evlogger import (
    DATE_FMT,
    info_msg,
    warning_msg,
    error_msg,
    reset_errors,
    warning_count,
    error_count,
    total_error_count,
)
from tzlocal import get_localzone
import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt
from fpdf import FPDF, XPos, YPos  # pylint: disable=unused-import
from evchargers import EnergyMonitor, EVChargers, UsageData
from pgebev1tariff import PGEBEV1Tariff
from evbillperiod import BillPeriod
from evbillocr import extract_text

# pylint: enable=wrong-import-position


# Global Constants


SCRIPT_NAME: str = Path(__file__).stem
"""Name of this script without .py extension."""

ONE_DAY: timedelta = timedelta(days=1)
"""timedelta instance for 1 day."""
TZ_LOCAL: ZoneInfo = get_localzone()
"""zoneinfo instance for local time zone."""
TOU_STR: list[str] = [tou.value for tou in Tou]
"""List of TOU rate periods."""

RE_DATE = r'((?:0[1-9]|1[012])/(?:0[1-9]|[12]\d|3[01])/(?:19\d\d|20\d\d))'
"""Regular expression for mm/dd/yyyy dates."""
RE_PERIOD = rf'(?m)^{RE_DATE}(?: (?:\W )?{RE_DATE})?'
"""Regular expression for mm/dd/yyy - mm/dd/yyy date range."""
RE_DOLLARS = r'\$?(-?\d{1,3}(?:,?\d{3})*\.\d{2})'
"""Regular expression for nnn,nnn.nn dollars, optional $ sign."""
RE_kWh = r'(\d{1,3}(?:,?\d{3})*\.\d{6})'
"""Regular expression for for nnn,nnn.nnnnnn kWh."""
RE_RATES = r'\$(\d{1,3}\.\d{5})'
"""Regular expression for $nnn.nnnnn dollars/kWh."""

# Global Variables

logger = logging.getLogger(SCRIPT_NAME)
"""Logging facility."""
rotating_handler = RotatingFileHandler(
    Config.evbilling_log, maxBytes=5 * 1024 * 1024, backupCount=3
)
"""Rotating log file handler."""
rotating_handler.setLevel(logging.INFO)
rotating_handler.setFormatter(
    logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log format
        datefmt=DATE_FMT,  # Custom date format
    )
)
logging.getLogger().addHandler(rotating_handler)


def initial_caps(s: str) -> str:
    """Convert words in string to Initial Caps."""
    return ' '.join(w[:1].upper() + w[1:] for w in s.split(' '))


class Provider(IntEnum):
    """PG&E/CleanPowerSF rate table indexes."""

    PGE, CPSF = range(2)


class DailyUsageCostBreakdown(NamedTuple):
    """Daily usage (kWh)-based costs for charts."""

    tou: Tou
    """Time Of Use."""
    kWh_cost: npt.NDArray[np.float32]
    """kWh_cost[day] = kWh $"""
    gen_pcia: npt.NDArray[np.float32]
    """gen_pcia[day] = Generation Credit $ + PCIA $"""
    tax_fees: npt.NDArray[np.float32]
    """tax_fees[day] = Energy Taxes and Fees $"""
    adjustment: npt.NDArray[np.float32]
    """adjustment[day] = Metering Adjustment $"""


class DailySubscriptionCostBreakdown(NamedTuple):
    """Daily power (kW)-based costs for charts."""

    subscription: npt.NDArray[np.float32]
    """subscription[day] = Subscription Charges $"""
    tax_fees: npt.NDArray[np.float32]
    """tax_fees[day] = Subscription Taxes and Fees $"""


class Bill:
    """PG&E main or submeter bill."""

    FIELDS = (
        ('account_no', r'(Account No): (\d{10}-\d)'),
        ('meter_no', r'(Meter #) (\d{10})'),
        ('total_usage', rf'(Total Usage) {RE_kWh}'),
        ('statement_date', rf'(Statement Date): {RE_DATE}'),
        ('due_date', rf'(Due Date): {RE_DATE}'),
    )

    LABELS = {
        field[0]: re.search(r"\(([^)]+)\)", field[1]).group(1) for field in FIELDS  # type: ignore
    }

    def __init__(self, ocrpages: tuple[str, str]) -> None:
        """Initialize bill from OCR text.

        Parameters
        ----------
        ocrpages : (str, str)
            (PGE details page, CPSF details page)

        """
        self.account_no: str
        """PG&E account number."""
        self.meter_no: str
        """PG&E electric meter number or submeter EVSE ID."""
        self.total_usage_ocr: str = ''
        """Total usage kWh or empty string if submeter bill."""
        self.total_usage: KilowattHours
        """Total usage kWh."""
        self.statement_date: str
        """PG&E statement date mm/dd/yyyy."""
        self.due_date: str
        """PG&E due date mm/dd/yyyy."""
        self.amount_due: Dollars
        """PG&E Electric Delivery Charges + CleanPowerSF Electric Generation
        Charges."""
        self.pge_bill_details: PGEBillDetails
        """PG&E bill details."""
        self.cpsf_bill_details: CPSFBillDetails
        """CleanPowerSF bill details."""
        self.out_subdir: Path
        """ Path to submeter bill output directory."""
        self.adjustment = Dollars('0.00')
        """Submetering difference adjustment charge allocation to match PG&E
        bill."""
        self.found: set[str] = set()
        """Set of found field attribute names."""

        logger.info('Parsing bill ...')

        for var, pattern in self.FIELDS:
            if m := re.search(pattern, ocrpages[0], re.IGNORECASE):
                setattr(self, var, m.group(2))
                self.found.add(var)

        logger.info(f'Found fields: {self.found}.')

        if self.total_usage:
            self.total_usage_ocr = self.total_usage
            self.total_usage = KilowattHours(self.total_usage_ocr)
        else:
            error_msg(logger, 'Total Usage not found.')

        self.pge_bill_details = PGEBillDetails(self, ocrpages[0])
        self.cpsf_bill_details = CPSFBillDetails(self, ocrpages[1])
        self.amount_due = self.pge_bill_details.total_charges + self.cpsf_bill_details.total_charges

        self.out_subdir = Args.outdir.joinpath(
            datetime.strptime(self.statement_date, '%m/%d/%Y').strftime('%Y-%m-%d')
        )

    def __str__(self) -> str:
        """Return PG&E main or submeter bill as formatted string."""
        s = '\n'.join(
            f'{self.LABELS[var]+":":16}{getattr(self, var):>12}'
            for var, _ in self.FIELDS
            if getattr(self, var) is not None
        )
        s += f'\nAmount Due     ${self.total_amount_due:>12,.02f}\n'
        s += f'\n{self.pge_bill_details}\n'
        s += f'\n{self.cpsf_bill_details}\n'
        return s

    @property
    def is_main_bill(self) -> bool:
        """Return True if main PG&E bill, not submeter bill."""
        return self.total_usage_ocr != ''

    def submeter_bill(self, submeter: 'Submeter') -> 'Bill':
        """Make a copy of the panel meter bill and update with Emporia Vue usage
        data for a submeter.

        Parameters
        ----------
        submeter : Submeter
            Submeter instance with Emporia Vue usage data.

        Returns
        -------
        Bill
            Bill instance for the specified Submeter instance.

        """
        subbill: Bill = copy.deepcopy(self)
        subbill.meter_no = submeter.evse_id
        subbill.total_usage_ocr = ''

        # Update attributes specific to a submeter
        subbill.pge_bill_details.submeter_bill_details(submeter)
        subbill.cpsf_bill_details.submeter_bill_details(submeter)

        subbill.total_usage = subbill.pge_bill_details.total_kWh
        subbill.amount_due = (
            subbill.pge_bill_details.total_charges + subbill.cpsf_bill_details.total_charges
        )

        # Set due_date to first day of next month
        d: datetime = (
            datetime.strptime(self.statement_date, '%m/%d/%Y').replace(day=1) + timedelta(days=32)
        ).replace(day=1)
        subbill.due_date = f'{d.month}/{d.day}/{d.year}'

        return subbill

    @property
    def period(self) -> BillPeriod:
        """Return the full bill period."""
        return self.pge_bill_details.period  # verified to be equal to self.cpsf_bill_details.period

    @property
    def total_amount_due(self) -> Dollars:
        """Return total amount due."""
        return self.amount_due + self.adjustment

    def tou_rates(self) -> npt.NDArray[np.float32]:
        """Return Time-Of-Use (TOU) rate table.

        Returns
        -------
        ndarray
            ndarray[Provider, day of rate period, hour] = TOU rate ($/kWh)

        """
        tourates = np.zeros((2, len(self.period), 24), dtype=np.float32)
        self.pge_bill_details.tou_rates(tourates[Provider.PGE, :, :])
        self.cpsf_bill_details.tou_rates(tourates[Provider.CPSF, :, :])
        tourates.setflags(write=False)
        return tourates

    def valid(self) -> bool:
        """Validate a Bill.

        Returns
        -------
        bool
            True if bill is valid, else False.

        """
        ok = True

        # Check for valid dates
        for var in ('self.statement_date', 'self.due_date'):
            if var in self.found:
                mmddyyyy = getattr(self, var)

                try:
                    datetime.strptime(mmddyyyy, "%m/%d/%Y")
                except ValueError:
                    ok = False
                    warning_msg(logger, f'{self.LABELS[var]} {mmddyyyy} is not a valid date')

        statement_dt = datetime.strptime(self.statement_date, '%m/%d/%Y').date()
        due_dt = datetime.strptime(self.due_date, '%m/%d/%Y').date()

        if statement_dt <= self.period.to:
            warning_msg(
                logger,
                f'Statement Date {self.statement_date} is not after '
                f'end of billing period {self.period.to}.',
            )
        elif (statement_dt - self.period.to) // ONE_DAY > 30:
            warning_msg(
                logger,
                f'Statement Date {self.statement_date} is more than 30 days '
                f'after end of billing period {self.period.to}.',
            )

        if due_dt <= statement_dt:
            warning_msg(
                logger,
                f'Due Date {self.due_date} is not after ' f'Statement Date {self.statement_date}.',
            )
        elif (due_dt - statement_dt) // ONE_DAY > 30:
            warning_msg(
                logger,
                f'Due Date {self.due_date} is less than 30 days '
                f'after Statement Date {self.statement_date}.',
            )

        # Check for missing fields
        for var, _ in self.FIELDS:
            if var not in self.found:
                warning_msg(logger, f'PG&E {self.LABELS[var]} not found')
                ok = False

        # Check for PG&E billing period equal to CPSF billing period
        if self.pge_bill_details.period != self.cpsf_bill_details.period:
            error_msg(
                logger,
                f'PG&E billing period {self.pge_bill_details.period} '
                f'not equal to CleanPowerSF billing period {self.cpsf_bill_details.period}.',
            )
            ok = False

        # Check for PG&E total kWh usage equal to CPSF total kWh usage
        if self.pge_bill_details.total_kWh != self.cpsf_bill_details.total_kWh:
            if self.pge_bill_details.all_missing_tou or self.cpsf_bill_details.all_missing_tou:
                warning_msg(
                    logger,
                    f'PG&E total kWh {self.pge_bill_details.total_kWh} '
                    f'not equal to CleanPowerSF total kWh {self.cpsf_bill_details.total_kWh}.',
                )
            else:
                error_msg(
                    logger,
                    f'PG&E total kWh {self.pge_bill_details.total_kWh} '
                    f'not equal to CleanPowerSF total kWh {self.cpsf_bill_details.total_kWh}.',
                )
                ok = False

        # Check for PG&E total usage equal to OCR Total Usage
        if self.total_usage is not None:
            if self.pge_bill_details.total_kWh != self.total_usage:
                warning_msg(
                    logger,
                    f'Calculated PG&E total usage {self.pge_bill_details.total_kWh} '
                    f'not equal to OCR total usage {self.total_usage}',
                )
                ok = False

        # Check for valid PG&E and CPSF bills
        ok = self.pge_bill_details.valid() and ok
        ok = self.cpsf_bill_details.valid() and ok

        return ok

    def summary(self) -> str:
        """Electric bill summary.

        Returns
        -------
        str
            Bill summary as a string.
        """
        s = (
            '\n'.join(
                [
                    f'{"Total Usage":<40} {self.total_usage:>12} kWh',
                    f'{"PG&E Electric Delivery Charges":<40}  '
                    f'${self.pge_bill_details.total_charges:>10}',
                    f'{"CleanPowerSF Electric Generation Charges":<40}  '
                    f'${self.cpsf_bill_details.total_charges:>10}',
                ]
            )
            + '\n'
        )
        if not self.is_main_bill:
            s += f'{f"Metering Difference Adjustment":<40}  ${self.adjustment:>10}\n'
        s += f'{f"Total Amount Due by {self.due_date}":<40}  ${self.total_amount_due:>10}'
        return s

    def effective_rate(self) -> str:
        """Return effective $/kWh rate as a formatted string.

        Returns
        -------
        str
            Effective $/kWh rate if total_usage > 0, else ''
        """
        return (
            f'Effective rate (Total Amount Due/Usage):  '
            f'${(self.amount_due + self.adjustment)/self.total_usage}/kWh'
            if self.total_usage > 0
            else ''
        )

    def as_text(self) -> str:
        """Return PG&E main bill as formatted string for print()."""
        return f'{str(self)}\nSummary for Meter # {self.meter_no}\n{self.summary()}'


class RatePeriod(ABC):
    """PG&E or CPSF main or submeter charges for a rate period."""

    @abstractmethod
    def __init__(self, bill: Bill, period: BillPeriod, text: str) -> None:
        """Initialize a PG&E or CPSF rate period from PG&E bill OCR text.

        Parameters
        ----------
        bill : Bill
            Main or submeter Bill instance.
        period : BillPeriod
            A Period instance; may be multiple periods if rates change during billing period.
        text : str
            Bill OCR text covering the specified rate period.

        Raises
        ------
        LookupError
            Missing charges.
        """
        self.bill: Bill = bill
        """Main or submeter Bill instance."""
        self.period: BillPeriod = period
        """Period covered by charges; may be multiple periods if rates change
        during billing period."""
        self.energy_charges: list[EnergyCharge] = []
        self.missing_tou: set[Tou]
        """Missing tou energy charges."""
        self.other_charges: dict[str, OtherCharge] = {}
        """other_charges[name] = OtherEnergyCharge, OtherPctNet, or
        OtherPctEnergyCharge instance."""

        logger.info(
            f'Parsing {self.bill.meter_no} {self.provider} bill details '
            f'for rate period {self.period} ...'
        )

        # Energy Charges:
        self.energy_charges = [
            EnergyCharge(tou, kWh, rate, charge)
            for tou, kWh, rate, charge in re.findall(
                rf'(Peak|Off Peak|Super Off Peak)\D+' rf'{RE_kWh} kWh @ ?{RE_RATES} {RE_DOLLARS}',
                text,
                re.IGNORECASE,
            )
        ]

        self.missing_tou = set(Tou) - {energy_charge.tou for energy_charge in self.energy_charges}
        if self.missing_tou:
            warning_msg(
                logger,
                f'Missing {self.bill.meter_no} {self.provider} energy charges: '
                f'{", ".join(tou for tou in Tou if tou in self.missing_tou)}.',
            )

        # Other Charges:
        missing: set[str] = set()
        for pattern, charge_class in self.other_charges_REs:
            if m := re.search(pattern, text, flags=re.IGNORECASE):
                self.other_charges[m.group(1)] = charge_class(*m.group(1, 2))
            else:
                # Extract charge name from RE
                name = re.search(r'\(([^)]+)\)', pattern).group(1)  # type: ignore
                missing.add(name)
                if charge_class is OtherPctNetCharge:
                    info_msg(
                        logger,
                        f'{self.bill.meter_no} {self.provider} '
                        f'rate period {self.period} {name}: charge not found.',
                    )

        if self.total_energy_charges > 0 and missing:
            raise LookupError(f'Missing {self.bill.meter_no} {self.provider} charges: {missing}.')

    @abstractmethod
    def __str__(self) -> str:
        """Return rate period as a formatted string."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Return provider name."""

    @property
    @abstractmethod
    def other_charges_REs(self) -> tuple[tuple[str, type['OtherCharge']], ...]:
        """Return tuple of REs for instantiating OtherCharge instances."""

    @property
    @abstractmethod
    def net_charges(self) -> Dollars:
        """Return net charges for this rate period."""

    def other_energy_rates(self) -> DollarsPerKilowattHour:
        """Return sum of OtherEnergyCharge rates."""
        return sum(
            other_charge.rate
            for other_charge in self.other_charges.values()
            if isinstance(other_charge, OtherEnergyCharge)
        )

    def other_pct_net_rates(self) -> Percent:
        """Return sum of OtherPctNetCharge rates."""
        return sum(
            other_charge.rate
            for other_charge in self.other_charges.values()
            if isinstance(other_charge, OtherPctNetCharge)
        )

    def other_pct_energy_rates(self) -> Percent:
        """Return sum of OtherPctEnergyCharge rates."""
        return sum(
            other_charge.rate
            for other_charge in self.other_charges.values()
            if isinstance(other_charge, OtherPctEnergyCharge)
        )

    def __len__(self) -> int:
        """Return length of rate period in days."""
        return len(self.period)

    @property
    @functools.lru_cache
    def total_kWh(self) -> KilowattHours:
        """Return total energy kWh for a rate period.

        Returns
        -------
        KilowattHours
            Total energy kWh for a rate period.

        Notes
        -----
        lru_cache OK because self.energy_charges does not change after
        initialization.
        lru_cache prevents multiple INFO messages for the same RatePeriod.

        """
        if len(self.energy_charges) > 0:
            return sum((energy.kWh for energy in self.energy_charges), KilowattHours(0))

        info_msg(
            logger,
            f'{self.bill.meter_no} {self.provider} rate period {self.period}: '
            f'No energy charges found.',
        )
        return KilowattHours(0)

    @property
    @functools.lru_cache
    def total_energy_charges(self) -> Dollars:
        """Return total energy charges for a rate period.

        Returns
        -------
        Dollars
            Total energy charges for a rate period.

        Notes
        -----
        lru_cache OK because self.energy_charges does not change after
        initialization.

        """
        return sum((energy.charge for energy in self.energy_charges), Dollars('0.00'))

    @property
    @functools.lru_cache
    def total_charges(self) -> Dollars:
        """Return total charges for a rate period.

        Returns
        -------
        Dollars
            Total charges for a rate period.

        Notes
        -----
        lru_cache OK because self.other_charges does not change after
        initialization.

        """
        return self.net_charges + sum(other.charge for other in self.other_charges.values())

    def set_rates(self) -> None:
        """Set rates for other charges."""
        for other_charge in self.other_charges.values():
            other_charge.set_rate(self)

    def set_other_charges(self) -> None:
        """Set charges for other charges."""
        for other in self.other_charges.values():
            other.set_charge(self)

    def submeter_rate_period(self, submeter: 'Submeter') -> None:
        """Update PG&E or CPSF rate period attributes for a submeter with Emporia Vue usage data.

        Parameters
        ----------
        submeter : Submeter
            Submeter instance with Emporia Vue usage data.

        """
        start_day: int = (self.period.fr - submeter.main_bill.period.fr) // ONE_DAY

        for energy in self.energy_charges:
            energy.kWh = KilowattHours(
                str(
                    submeter.hourly_kWh[
                        start_day : start_day + len(self.period), Config.tou_hours_mask[energy.tou]
                    ].sum()
                )
            )
            energy.charge = energy.kWh * energy.rate

    def valid(self) -> bool:
        """Return True if all energy usage charges in a rate period are valid.

        Returns
        -------
        bool
            True if all energy usage charges are valid, else False.

        """
        ok = True

        for charge in self.energy_charges:
            if not charge.valid():
                error_msg(
                    logger,
                    f'Invalid {self.bill.meter_no} {self.provider} '
                    f'charge: {' '.join(str(charge).split())}',
                )
                ok = False

        return ok


class PGERatePeriod(RatePeriod):
    """PG&E main or submeter charges for a rate period."""

    def __init__(self, bill: Bill, period: BillPeriod, text: str) -> None:
        """Initialize PG&E rate period from PG&E bill OCR text.

        Parameters
        ----------
        bill : Bill
            Bill instance
        period : BillPeriod
            A Period instance; may be multiple periods if rates change during billing period
        text : str
            Bill OCR text covering the specified rate period.

        Raises
        ------
        LookupError
            PG&E Subscription Level not found
        LookupError
            PG&E Overage Fees not found
        LookupError
            PG&E Generation Credit not found
        LookupError
            PG&E Power Charge Indifference Adjustment not found
        """
        self.subscription: SubscriptionCharge
        """Subscription charge."""
        self.overage_fee: OverageFee
        """Subscription Level Overage fee."""
        self.generation_credit: Dollars
        """Generation Credit, a negative amount."""
        self.pcia: OtherCharge
        """Power Charge Indifference Adjustment."""
        self.energy_credits: dict[Tou | str, EnergyCredit] = {}
        """energy_credits[tou] = EnergyCredit instance."""

        # Subscription Level, 10 kW blocks
        if m := re.search(
            rf'Subscription Level \(10kW/block\) (\d+) blocks? '
            rf'@ ([01]\.\d\d\d\d) month @ {RE_DOLLARS} {RE_DOLLARS}',
            text,
            re.IGNORECASE,
        ):
            self.subscription = SubscriptionCharge(*m.group(1, 2, 3, 4))
        else:
            raise LookupError('PG&E Subscription Level not found')

        # Overage Fees
        if m := re.search(rf'Overage Fees (\d+) kW @ {RE_RATES} {RE_DOLLARS}', text, re.IGNORECASE):
            self.overage_fee = OverageFee(*m.group(1, 2, 3))
        else:
            raise LookupError('PG&E Overage Fees not found')

        super().__init__(bill, period, text)

        # Set energy Time Of Use Generation Credits
        self.energy_credits = {
            energy.tou: TOUGenerationCredit(self.period, energy.tou, energy.kWh)
            for energy in self.energy_charges
        }

        bundled_pcia = PCIACredit(period, self.total_kWh)
        self.energy_credits[bundled_pcia.name] = bundled_pcia

        if self.total_energy_charges > 0:
            # Generation Credit
            if m := re.search(rf'(Generation Credit) {RE_DOLLARS}', text, re.IGNORECASE):
                self.generation_credit = Dollars(m.group(2))
            else:
                raise LookupError('PG&E Generation Credit not found')

            # Power Charge Indifference Adjustment
            if m := re.search(
                rf'(Power Charge Indifference Adjustment) ' f'{RE_DOLLARS}', text, re.IGNORECASE
            ):
                self.pcia = OtherEnergyCharge(*m.group(1, 2))
            else:
                raise LookupError('PG&E Power Charge Indifference Adjustment not found')

        else:  # Set Generation Credit and PCIA to 0 if no energy used
            self.generation_credit = Dollars('0.00')
            self.pcia = OtherEnergyCharge('Power Charge Indifference Adjustment')

        # Set $/kWh rate Power Charge Indifference Adjustment (PCIA)
        self.pcia.set_rate(self)

        # Set percentage rates for other charges
        self.set_rates()

    def __str__(self) -> str:
        """Return PG&E rate period as a formatted string."""
        s = '\n'.join([f'{self.period}', f'{self.subscription}', f'{self.overage_fee}']) + '\n'
        if self.total_energy_charges > 0:
            s += f'\n{self.provider} Energy Charges\n'
            s += '\n'.join(str(charge) for charge in self.energy_charges)
            s += f'\n{self.provider} Energy Credits\n'
            s += '\n'.join(str(credit) for credit in self.energy_credits.values())
            s += f'\n{'Total Generation Credit':<60}  ${self.generation_credit:8,.02f}\n'
            s += f'{self.pcia}\n'
        s += f'{"Net Charges":<50} ${self.net_charges:8,.02f}\n'
        s += '\n'.join(str(ch) for ch in self.other_charges.values())
        return s

    @property
    def provider(self) -> str:
        """Return provider name."""
        return 'PG&E'

    @property
    def other_charges_REs(self) -> tuple[tuple[str, type['OtherCharge']], ...]:
        """Return tuple of REs for instantiating OtherCharge instances."""
        return (
            (rf'(Franchise Fee Surcharge) {RE_DOLLARS}', OtherPctEnergyCharge),
            (rf"(San Francisco Utility Users' Tax) \(\d+\.\d+%\) {RE_DOLLARS}", OtherPctNetCharge),
            (rf'(SF Prop C Tax Surcharge) {RE_DOLLARS}', OtherPctNetCharge),
        )

    def submeter_rate_period(self, submeter: 'Submeter') -> None:
        """Update PG&E rate period attributes for a submeter with Emporia Vue usage data.

        Parameters
        ----------
        submeter : Submeter
            Submeter instance with Emporia Vue usage data.

        """
        self.subscription.submeter_subscription_charge(
            submeter.evse_kW_rating, submeter.total_evse_kW
        )
        self.overage_fee.submeter_overage_fee(submeter.evse_kW_rating, submeter.total_evse_kW)

        # Invalidate these so they are not used by accident
        del self.generation_credit
        del self.pcia.charge

        super().submeter_rate_period(submeter)

        self.generation_credit = Dollars('0.00')
        for energy_credit in self.energy_credits.values():
            energy_credit.submeter_energy_credit(self)
            self.generation_credit += energy_credit.credit

        self.pcia.charge = self.total_kWh * self.pcia.rate
        self.set_other_charges()

    @property
    def net_charges(self) -> Dollars:
        """Return net charges for this PG&E rate period.

        Returns
        -------
        Dollars
            Net charges for this PG&E rate period.

        """
        net: Dollars = self.subscription.charge + self.overage_fee.charge
        if self.total_energy_charges > 0:
            net += self.total_energy_charges + self.generation_credit + self.pcia.charge
        return net

    def tou_gen_credit_pcia_rates(self, tou: Tou) -> DollarsPerKilowattHour:
        """Return sum of generation credit and pcia rates."""
        return (
            (
                self.energy_credits[tou].rate
                if tou in self.energy_credits
                else DollarsPerKilowattHour(0)
            )
            + self.energy_credits['Bundled PCIA'].rate
            + self.pcia.rate
        )

    def valid(self) -> bool:
        """Return True if PG&E subscription charge and all energy charges and
        credits are valid.

        Returns
        -------
        bool
            True if PG&E subscription charge and energy credits are valid, else False.

        """
        ok = True

        for charge in (self.subscription, self.overage_fee):
            if not charge.valid():
                error_msg(logger, f'PG&E rate period {self.period} invalid {charge}.')
                ok = False

        credit = sum((gc.credit for gc in self.energy_credits.values()), Dollars('0.00'))
        if abs(credit - self.generation_credit) > Dollars('0.01'):
            msg = f'PG&E rate period {self.period} calculated generation credit {credit} '
            msg += f'not equal to OCR generation credit {self.generation_credit}; '
            msg += 'check BEV-1 tariff UNBUNDLING OF TOTAL RATES, Generation and Bundled PCIA.'
            if abs((credit - self.generation_credit) / self.generation_credit) > 0.01:
                error_msg(logger, msg)
                ok = False
            else:
                warning_msg(logger, msg)

        return super().valid() and ok


class CPSFRatePeriod(RatePeriod):
    """CPSF main or submeter charges for a rate period."""

    def __init__(self, bill: Bill, period: BillPeriod, text: str) -> None:
        """Initialize CleanPowerSF rate period from PG&E bill OCR text.

        Parameters
        ----------
        bill : Bill
            Bill instance
        period : BillPeriod
            A Period instance; may be multiple periods if rates change during
            billing period
        text : str
            Bill OCR text covering the specified rate period.
        bill_details : CPSFBillDetails instance

        """
        super().__init__(bill, period, text)
        self.set_rates()

    def __str__(self) -> str:
        """Return CPSF rate period as a formatted string."""
        s = '\n'.join([f'{self.period}', f'{self.provider} Energy Charges\n'])
        s += '\n'.join(str(charge) for charge in self.energy_charges)
        s += f'\n{"Net Charges":<50} ${self.net_charges:8,.02f}'
        if self.net_charges > 0:
            s += (
                f'\n{self.other_charges["Local Utility Users Tax"]}\n'
                f'{self.other_charges["Energy Commission Surcharge"]}'
            )
        return s

    @property
    def provider(self) -> str:
        """Return provider name."""
        return 'CleanPowerSF'

    @property
    def other_charges_REs(self) -> tuple[tuple[str, type['OtherCharge']], ...]:
        """Return tuple of REs for instantiating OtherCharge instances."""
        return (
            (rf'(Local Utility Users Tax) {RE_DOLLARS}', OtherPctNetCharge),
            (rf'(Energy Commission Surcharge) {RE_DOLLARS}', OtherEnergyCharge),
        )

    def submeter_rate_period(self, submeter: 'Submeter') -> None:
        """Update CPSF rate period attributes for a submeter with Emporia Vue usage data.

        Parameters
        ----------
        submeter : Submeter
            Submeter instance with Emporia Vue usage data.

        """
        super().submeter_rate_period(submeter)
        self.set_other_charges()

    @property
    def net_charges(self) -> Dollars:
        """Return net charges for this CPSF rate period."""
        return self.total_energy_charges


class BillDetails:
    """PG&E Electric Delivery or CleanPowerSF Electric Generation bill details."""

    def __init__(self, bill: Bill, text: str) -> None:
        """_summary_

        Parameters
        ----------
        bill : Bill
            _description_
        text : str
            _description_

        """
        """Initialize PG&E Electric Delivery or CleanPowerSF Electric Generation
        bill details from OCR text.

        Parameters
        ----------
        bill : Bill
            Main or submeter Bill instance.
        text : str
            OCR text of PG&E Electric Delivery or CleanPowerSF
            Electric Generation bill details page.

        Raises
        ------
        LookupError
            Failed to find total charges
        LookupError
            Failed to find any rate periods

        """
        self.bill: Bill = bill
        """Main or submeter Bill instance."""
        self.text: str = text
        """OCR text of PG&E or CPSF page of bill."""
        self.total_charges_ocr: Dollars
        """OCR Total PG&E Electric Delivery or CleanPowerSF Electric charge."""
        self.period: BillPeriod
        """Entire billing period."""
        self.rate_periods: list[RatePeriod]
        """PG&E or CleanPowerSF rate periods."""
        self.total_charges: Dollars
        """Total PG&E Electric Delivery or CleanPowerSF Electric charge."""
        self.total_kWh: KilowattHours
        """Total PG&E Electric Delivery or CleanPowerSF Electric kWh."""
        self.all_missing_tou: set[Tou] = set()
        """Missing tou energy charges in all rate periods."""

        logger.info(f'Parsing {self.provider} bill details ...')

        # Find total PG&E or CPSF charges
        m = re.search(self.re_total_charges, self.text, re.IGNORECASE)
        if not m:
            raise LookupError(f'Failed to find {self.provider} total charges')

        self.total_charges_ocr = Dollars(m.group(1))

        # Find charges for all rate periods on page
        pos: list[re.Match[str]] = list(re.finditer(RE_PERIOD, self.text))
        if len(pos) < 2 or any(period is None for period in pos):
            raise LookupError(f'Failed to find any {self.provider} rate periods')

        pos.append(m)
        self.period = BillPeriod(*pos[0].group(1, 2))
        self.rate_periods = [
            self.create_rate_period(
                bill,
                BillPeriod(*pos[i].groups()),
                self.text[pos[i].start() : pos[i + 1].start()],
            )
            for i in range(1, len(pos) - 1)
        ]

        self.total_charges = sum(
            (rate_period.total_charges for rate_period in self.rate_periods), Dollars('0.00')
        )
        self.total_kWh = sum(
            (rate_period.total_kWh for rate_period in self.rate_periods), KilowattHours(0)
        )
        for rate_period in self.rate_periods:
            self.all_missing_tou |= rate_period.missing_tou

        logger.info(f'{self.provider} bill details parsed.')

    @abstractmethod
    def __str__(self) -> str:
        """Return PG&E Electric Delivery or CleanPowerSF Electric Generation
        bill details as a formatted string."""
        s = f'Billing period {self.period} ({len(self.period)} billing days)\n'
        s += f'Rate Schedule: {self.rate_schedule}\n\n'
        s += '\n\n'.join(str(rp) for rp in self.rate_periods) + '\n'
        return s

    @property
    @abstractmethod
    def provider(self) -> str:
        """Return provider name."""

    @property
    @abstractmethod
    def re_total_charges(self) -> str:
        """Return RE to parse total charges."""

    @property
    @abstractmethod
    def rate_schedule(self) -> str:
        """Return rate schedule."""

    @abstractmethod
    def create_rate_period(self, bill: Bill, period: BillPeriod, text: str) -> RatePeriod:
        """Create rate period."""

    def submeter_bill_details(self, submeter: 'Submeter') -> None:
        """Update bill details for a submeter with Emporia Vue usage data.

        Parameters
        ----------
        submeter : Submeter
            Submeter instance with Emporia Vue usage data.

        """
        self.total_kWh = submeter.total_kWh  # Total PG&E/CPSF Electric Delivery/Generation kWh

        for rate_period in self.rate_periods:
            rate_period.submeter_rate_period(submeter)

        self.total_charges = sum(
            (rate_period.total_charges for rate_period in self.rate_periods), Dollars('0.00')
        )
        self.total_charges_ocr = (
            self.total_charges
        )  # No OCR for submeter bills; suppress errors from valid()

    def tou_rates(
        self, tourates: Optional[npt.NDArray[np.float32]] = None
    ) -> npt.NDArray[np.float32]:
        """Return Time-Of-Use rate table for billing period.

        Parameters
        ----------
        tourates : ndarray((len(self.period), 24))
            Optional ndarray to store Time-Of-Use rate table

        Returns
        -------
        ndarray((len(self.period), 24))
            ndarray[day-of-period, hour] = $/kWh rate

        Notes
        -----
        TOU rate will be zero if no usage during a TOU.

        """
        if tourates is None:
            tourates = np.zeros(
                (len(self.period), 24), dtype=np.float32
            )  # rates[day, hour] = TOU rate

        start = 0

        for rp in self.rate_periods:  # iterate over rate periods in bill
            for ch in rp.energy_charges:  # iterate over energy charges in rate period
                # Set the $/kWh rate for all days in rate period and TOU hours
                tourates[start : start + len(rp), Config.tou_hours_mask[ch.tou]] = ch.rate
            start += len(rp)  # advance start day of next rate period

        tourates.setflags(write=False)
        return tourates

    def valid(self) -> bool:
        """Check validity of bill details, which can be incorrect due to OCR errors

        Returns
        -------
        bool
            True if bill details valid, else False

        """
        ok = True

        if self.period.fr != self.rate_periods[0].period.fr:
            error_msg(
                logger,
                f'Start of {self.provider} billing period {self.period} '
                f'not equal to start of first rate period {self.rate_periods[0].period}.',
            )
            ok = False

        if self.period.to != self.rate_periods[-1].period.to:
            error_msg(
                logger,
                f'End of {self.provider} billing period {self.period} '
                f'not equal to end of last rate period {self.rate_periods[-1].period}.',
            )
            ok = False

        for i in range(0, len(self.rate_periods) - 1):
            if self.rate_periods[i].period.to + ONE_DAY != self.rate_periods[i + 1].period.fr:
                error_msg(
                    logger,
                    f'{self.provider} {self.rate_periods[i].period} '
                    f'and {self.rate_periods[i+1].period} rate periods are not consecutive.',
                )
                ok = False

        for rate_period in self.rate_periods:
            if not rate_period.valid():
                ok = False

        if self.total_charges != self.total_charges_ocr:
            error_msg(
                logger,
                f'Calculated {self.provider} total charges ${self.total_charges} '
                f'not equal to OCR total charges ${self.total_charges_ocr}.',
            )
            ok = False

        return ok


class PGEBillDetails(BillDetails):
    """PG&E main or submeter bill delivery details."""

    def __str__(self):
        """Return PG&E main or submeter bill delivery details as a formatted string."""
        s = 'Details of PG&E Electric Delivery Charges\n'
        s += super().__str__()
        s += f'\n{"Total PG&E Electric Delivery Charges":<60}  ${self.total_charges:8,.02f}'
        return s

    @property
    def provider(self) -> str:
        """Return provider name."""
        return 'PG&E'

    @property
    def re_total_charges(self) -> str:
        """Return RE to parse total charges."""
        return rf'Total PG&E Electric Delivery Charges \${RE_DOLLARS}'

    @property
    def rate_schedule(self) -> str:
        """Return rate schedule."""
        return 'BEV1 Bus Low Use EV'

    def create_rate_period(self, bill: Bill, period: BillPeriod, text: str) -> RatePeriod:
        """Create rate period."""
        return PGERatePeriod(bill, period, text)

    def subscription_total_cost(self) -> Dollars:
        """Calculate total subscription cost including overage fees, taxes, and
        surcharges.

        Returns
        -------
        Dollars
            Total subscription cost including overage fees, taxes, and surcharges.
        """
        total_subscription: Dollars = Dollars('0.00')
        """Subscription charges + overage fees for all rate periods."""
        total_tax_fees: Dollars = Dollars('0.00')
        """Taxes and surcharges for all rate periods."""

        for rate_period in self.rate_periods:
            assert isinstance(
                rate_period, PGERatePeriod
            ), f'Expected type(rate_period) PGERatePeriod; got {type(rate_period).__name__}'

            subscription = rate_period.subscription.charge + rate_period.overage_fee.charge
            total_subscription += subscription
            total_tax_fees += subscription * rate_period.other_pct_net_rates()

        return total_subscription + total_tax_fees


class CPSFBillDetails(BillDetails):
    """CleanPowerSF main or submeter bill generation details."""

    def __init__(self, bill: Bill, text: str) -> None:
        """Initialize CleanPowerSF Electric Generation bill details from OCRtext.

        Parameters
        ----------
        bill : Bill
            Bill instance
        text : str
            OCR text of CleanPowerSF Electric Generation bill details page.

        Raises
        ------
        LookupError
            Missing CleanPowerSF energy charges

        Notes
        -----
        CleanPowerSF changes rates on July 1, but uses a single rate period with
        pairs of TOU rates.  The rate period is split into two, assuming that
        the first of each TOU rate pair is the old rate and the second is the
        new rate.

        """
        super().__init__(bill, text)

        # Check for rate change on July 1 and split rate period into two if so.

        change_date = date(
            self.period.fr.year, *map(int, Config.rate_info.cpsf_rate_change.split('/'))
        )
        if not self.period.fr < change_date <= self.period.to:
            return

        if len(self.rate_periods) > 1:
            warning_msg(
                logger,
                f'Multiple CleanPowerSF rate periods found during billing period '
                f'that includes rate change date ({change_date}) -- check bill.',
            )
            for rate_period in self.rate_periods:
                if rate_period.period.fr == change_date:
                    warning_msg(
                        logger,
                        f'CleanPowerSF rate period begins on {change_date}; '
                        f'assuming split not needed.',
                    )
                    return

        logger.info(f'Splitting CleanPowerSF rate period {self.period} ...')

        old_rates: RatePeriod = copy.deepcopy(self.rate_periods[0])
        new_rates: RatePeriod = copy.deepcopy(self.rate_periods[0])
        change_dt: datetime = datetime.combine(change_date, time.min, tzinfo=TZ_LOCAL)
        old_rates.period = BillPeriod(
            old_rates.period.str_fr(), (change_dt - ONE_DAY).strftime('%m/%d/%Y')
        )
        new_rates.period = BillPeriod(change_dt.strftime('%m/%d/%Y'), new_rates.period.str_to())

        energy_charges: list[list[EnergyCharge]] = [
            list(it)
            for tou, it in groupby(
                sorted(
                    self.rate_periods[0].energy_charges, key=lambda chrg: TOU_STR.index(chrg.tou)
                ),
                key=lambda chrg: TOU_STR.index(chrg.tou),
            )
        ]
        missing_tou: set[Tou] = set()
        for tou_energy_charges in energy_charges:
            if len(tou_energy_charges) != 2:
                missing_tou.add(tou_energy_charges[0].tou)
                error_msg(
                    logger, f'Missing CleanPowerSF {tou_energy_charges[0].tou} energy charge.'
                )
        if missing_tou:
            raise LookupError(
                f'Missing CleanPowerSF energy charges: '
                f'{", ".join(tou for tou in Tou if tou in missing_tou)}.'
            )

        old, new = list(zip(*energy_charges))
        old_rates.energy_charges, new_rates.energy_charges = (old, new)  # type: ignore

        for rates in (old_rates, new_rates):
            other_charges = rates.other_charges

            name = 'Local Utility Users Tax'
            other_charges[name].charge = Dollars(other_charges[name].rate * rates.net_charges)

            name = 'Energy Commission Surcharge'
            other_charges[name].charge = Dollars(other_charges[name].rate * rates.total_kWh)

        self.rate_periods = [old_rates, new_rates]

    def __str__(self) -> str:
        """Return CleanPowerSF main or submeter bill delivery details as string."""
        s = 'Details of CleanPowerSF Electric Generation Charges\n'
        s += super().__str__()
        s += f'\n{"Total CleanPowerSF Electric Delivery Charges":<60}  ${self.total_charges:8,.02f}'
        return s

    @property
    def provider(self) -> str:
        """Return provider name."""
        return 'CleanPowerSF'

    @property
    def re_total_charges(self) -> str:
        """Return RE to parse total charges."""
        return rf'Generation Charges \${RE_DOLLARS}'

    @property
    def rate_schedule(self) -> str:
        """Return rate schedule."""
        return 'BEV-1 Business Electric Vehicles'

    def create_rate_period(self, bill: Bill, period: BillPeriod, text: str) -> RatePeriod:
        """Create rate period."""
        return CPSFRatePeriod(bill, period, text)


class SubscriptionCharge:
    """PG&E subscription (demand) charge, 10 kW blocks.

    Note
    ----
    The PG&E subscription (demand) charge is a measurement of the maximum kW
    power usage in any single 15 minute period during a monthly billing cycle.

    """

    def __init__(self, quantity: str, months: str, rate: str, charge: str) -> None:
        """Initialize a SubscriptionCharge instance from PG&E bill OCR text.

        Parameters
        ----------
        quantity : str
            Number of 10 kW blocks.
        months : str
            Fraction of billing period, len(Rate Period)/len(Billing Period).
        rate : str
            $ per 10 kW block per billing period.
        charge : str
            months*quantity*rate.

        Note
        ----
        The prorated "months" amount shown on the PG&E bill is slightly
        inaccurate and may fail validation, so it is calculated from the charge
        and rate. Validation compares the calculated amount to the OCR amount to
        three decimal places.

        """
        self.quantity = Kilowatts(quantity)
        """Number of 10 kW blocks."""
        self.months_ocr = SubscriptionMonths(months)
        """Fraction of billing period from PG&E pdf OCR."""
        self.rate = DollarsPerKilowatt(rate)
        """$ per 10 kW block per billing period."""
        self.charge = Dollars(charge)
        """months*quantity*rate"""
        self.months = SubscriptionMonths(self.charge / (self.quantity * self.rate))
        """Calculated fraction of billing period."""

    def __str__(self) -> str:
        """Return Subscription Charge as formatted string."""
        return (
            f'Subscription Level {self.quantity:^5.3g} 10kW blocks '
            f'@ {self.months:.4f} month @ ${self.rate:.2f}  ${self.charge:8,.02f}'
        )

    def valid(self) -> bool:
        """Return True if subscription charge is valid.

        Returns
        -------
        bool
            True if subscription charge is valid, else False.

        """
        return (
            self.months.quantize() == SubscriptionMonths(self.months_ocr).quantize()
            and Dollars(self.months * self.quantity * self.rate) == self.charge
        )

    def submeter_subscription_charge(
        self, evse_kW_rating: Kilowatts, total_evse_kW: Kilowatts
    ) -> None:
        """Set submeter subscription (demand) charge based on EV charger peak kW demand.

        Parameters
        ----------
        evse_kW_rating : Kilowatts
            EV charger power rating in kW.
        total_evse_kW : Kilowatts
            Total connected EV charger power ratings in kW.

        Notes
        -----
        The subscription charge for 10 kW blocks is apportioned by EVSE kW
        rating.
        """
        self.quantity *= float(evse_kW_rating / total_evse_kW)
        """Prorated number of 10 kW blocks."""

        self.charge = Dollars(self.months * self.quantity * self.rate)


class OverageFee:
    """Subscription Level Overage Fee, $/kW."""

    def __init__(self, kW: str, rate: str, charge: str) -> None:
        """Initialize an OverageFee instance from PG&E bill OCR text.

        Parameters
        ----------
        kW : str
            15-minute peak demand kW subscription level overage: 'd,ddd.dddddd'.
        rate : str
            Subscription Overage Fee Rate, $/kWh: 'd.ddddd'
        charge : str
            Overage Fee, kWh*rate: 'd,ddd.dd'.

        """
        self.kW = Kilowatts(kW)
        """15-minute peak demand kW subscription level overage."""
        self.rate = DollarsPerKilowatt(rate)
        """Subscription Overage Fee Rate, $/kWh."""
        self.charge = Dollars(charge)
        """Overage Fee, kWh*rate"""

    def __str__(self) -> str:
        """Return overage fee as formatted string."""
        return (
            f' {'Overage Fees':<32}{self.kW:12,.6f} kW @ ${self.rate:.5f}   ${self.charge:8,.02f}'
        )

    def submeter_overage_fee(self, evse_kW_rating: Kilowatts, total_evse_kW: Kilowatts) -> None:
        """Set submeter subscription overage fees based on EV charger peak kW demand.

        Parameters
        ----------
        evse_kW_rating : Kilowatts
            EV charger power rating in kW.
        total_evse_kW : Kilowatts
            Total connected EV charger power ratings in kW.

        Notes
        -----
        The subscription overage fee is apportioned by EVSE kW rating.
        """
        # Calculate submeter portion of overage kW
        self.kW *= evse_kW_rating / total_evse_kW
        self.charge = self.kW * self.rate

    def valid(self) -> bool:
        """Return True if overage fee is valid.

        Returns
        -------
        bool
            True if overage fee is valid, else False.

        """
        return Dollars(self.kW * self.rate) == self.charge


class EnergyCharge:
    """Time Of Use Energy (kWh) Usage Charges."""

    def __init__(
        self, tou: Tou, kWh: str = '0.000000', rate: str = '0.00000', charge: str = '0.00'
    ) -> None:
        """Initialize an EnergyCharge instance from PG&E bill OCR text.

        Parameters
        ----------
        tou : Tou
            Time Of Use.
        kWh : str
            Energy (kWh) used: 'd,ddd.dddddd'.
        rate : str
            Energy usage rate, $ per kWh: 'd.ddddd'
        charge : str
            kWh*rate: 'd,ddd.dd'.

        """
        self.tou = Tou(initial_caps(tou))
        """Time Of Use."""
        self.kWh = KilowattHours(kWh)
        """Energy (kWh) used."""
        self.rate = DollarsPerKilowattHour(rate)
        """Energy usage rate, $ per kWh."""
        self.charge = Dollars(charge)
        """Energy charge $, should equal kWh*rate."""

    def __str__(self) -> str:
        """Return Energy Charge as formatted string."""
        return f' {self.tou:<32}{self.kWh:12,.6f} kWh @ ${self.rate:.5f}  ${self.charge:8,.02f}'

    def valid(self) -> bool:
        """Return True if energy charge is valid.

        Returns
        -------
        bool
            True if energy charge is valid, else False.

        """
        return self.kWh * self.rate == self.charge


class OtherCharge(ABC):
    """Generation credit, PCIA charge, taxes, and surcharges.

    Notes
    -----
    Other PG&E credits, surcharges, and taxes:
        Power Charge Indifference Adjustment ($/Total kWh)
        Franchise Fee Surcharge (% Total Energy Charges)
        San Francisco Utility Users' Tax (% Net Charges)
        SF Prop C Tax Surcharge (% Net Charges)

    Other CleanPowerSF surcharges and taxes:
        Local Utility Users Tax (% Net Charges)
        Energy Commission Surcharge ($/Total kWh)

    """

    def __init__(self, name: str, charge='0.00') -> None:
        """Initialize an OtherCharge instance from PG&E bill OCR text.

        Parameters
        ----------
        name : str
            Charge name.
        charge : str
            Charge in dollars: 'd,ddd.dd'.

        """
        self.name: str = initial_caps(name)
        """Charge name."""
        self.charge = Dollars(charge)
        """Charge in dollars."""
        self.rate: DollarsPerKilowattHour | Percent
        """Calculated $/kWh rate or % of net charges or % total kWh."""

    @abstractmethod
    def __str__(self) -> str:
        """Return charge as formatted string."""

    @abstractmethod
    def set_rate(self, rate_period: RatePeriod) -> None:
        """Set the rate for a charge."""

    @abstractmethod
    def set_charge(self, rate_period: RatePeriod) -> None:
        """Set the charge."""


class OtherEnergyCharge(OtherCharge):
    """Other charge based on energy (kWh) usage:

    PG&E Power Charge Indifference Adjustment ($/Total kWh)
    CPSF Energy Commission Surcharge ($/Total kWh)

    """

    def __str__(self) -> str:
        """Return OtherEnergyCharge charge as formatted string."""
        rate_fmt = f' (${self.rate:.05f}/kWh)'
        return f'{self.name + rate_fmt:<60}  ${self.charge:8,.02f}'

    def set_rate(self, rate_period: RatePeriod) -> None:
        """Set the rate for an energy usage-based charge.

        Parameters
        ----------
        rate_period : RatePeriod
            Containing RatePeriod instance.

        """
        self.rate = DollarsPerKilowattHour(
            self.charge / rate_period.total_kWh
            if rate_period.total_kWh > 0
            else DollarsPerKilowattHour('NaN')
        )

    def set_charge(self, rate_period: RatePeriod) -> None:
        """Set the charge for an energy usage-based charge.

        Parameters
        ----------
        rate_period : RatePeriod
            Containing RatePeriod instance.

        """
        self.charge = Dollars(rate_period.total_kWh * self.rate)


class OtherPctNetCharge(OtherCharge):
    """Other charge based on percentage of net charges:

    PG&E San Francisco Utility Users' Tax (%)
    PG&E SF Prop C Tax Surcharge (%)
    CPSF Local Utility Users Tax (%)

    """

    def __str__(self) -> str:
        """Return OtherNetCharge charge as formatted string."""
        rate_fmt = f' ({self.rate:.03f}%)'
        return f'{self.name + rate_fmt:<60}  ${self.charge:8,.02f}'

    def set_rate(self, rate_period: RatePeriod) -> None:
        """Set the percentage for a charge based on net charges.

        Parameters
        ----------
        rate_period : RatePeriod
            Containing RatePeriod instance.

        """
        self.rate = Percent(
            self.charge * 100 / rate_period.net_charges
            if rate_period.net_charges > 0
            else Dollars(0)
        ).quantize()

    def set_charge(self, rate_period: RatePeriod) -> None:
        """Set the charge for a percentage of net charge.

        Parameters
        ----------
        rate_period : RatePeriod
            Containing RatePeriod instance.

        """
        self.charge = Dollars(rate_period.net_charges * self.rate)


class OtherPctEnergyCharge(OtherCharge):
    """Other charge based on percentage of total energy charges:

    PG&E Franchise Fee Surcharge (% Total Energy Charges)

    """

    def __str__(self) -> str:
        """Return OtherPctEnergyCharge charge as formatted string."""
        rate_fmt = f' ({self.rate:.03f}%)'
        return f'{self.name + rate_fmt:<60}  ${self.charge:8,.02f}'

    def set_rate(self, rate_period: RatePeriod) -> None:
        """Set the percentage for a charge based on a percentage of total energy charges.

        Parameters
        ----------
        rate_period : RatePeriod
            Containing RatePeriod instance.

        """
        self.rate = Percent(
            self.charge * 100 / rate_period.total_energy_charges
            if rate_period.total_kWh > 0
            else Percent('NaN')
        )

    def set_charge(self, rate_period: RatePeriod) -> None:
        """Set the charge as a percentage of total energy charges.

        Parameters
        ----------
        rate_period : RatePeriod
            Containing RatePeriod instance.

        """
        self.charge = rate_period.total_energy_charges * self.rate


class EnergyCredit(ABC):
    """Energy (kWh) Credit."""

    @abstractmethod
    def __init__(self, name: str, kWh: KilowattHours, rate: DollarsPerKilowattHour) -> None:
        """Initialize an EnergyCredit instance for a RatePeriod.

        Parameters
        ----------
        name : str
            Energy credit name.
        kWh : KilowattHours
            Energy (kWh) used.
        rate : DollarsPerKilowattHour
            Energy credit rate, $/kWh from PG&E BEV-1 tariff.
        """
        self.name: str = name
        """Energy credit name."""
        self.kWh: KilowattHours = kWh
        """Energy (kWh) used."""
        self.rate: DollarsPerKilowattHour = rate
        """Energy credit rate, $/kWh from PG&E BEV-1 tariff."""
        self.credit: Dollars = self.kWh * self.rate
        """Energy credit $, kWh*rate"""

    def __str__(self) -> str:
        """Return EnergyCredit as formatted string."""
        return f' {self.name:<20}{self.kWh:12,.6f} kWh @ ${self.rate:+.5f}  ${self.credit:+8,.02f}'

    @abstractmethod
    def submeter_energy_credit(self, rate_period: RatePeriod) -> None:
        """Update PG&E credit for a submeter."""


class TOUGenerationCredit(EnergyCredit):
    """Time Of Use Energy (kWh) Generation Credit."""

    def __init__(self, period: BillPeriod, tou: Tou, kWh=KilowattHours(0)) -> None:
        """Initialize a Time Of Use TouGenerationCredit instance for a RatePeriod.

            Parameters
            ----------
            period : BillPeriod
                Period instance.
            tou : Tou
                Time Of Use.
            kWh : KilowattHours
                kWh used.

        Raises
        ------
        LookupError
            PG&E rate period missing energy charge
        """
        super().__init__(tou, kWh, -PGEBEV1Tariff.effective_rates(period)[f'Credit/{tou}'])

    def submeter_energy_credit(self, rate_period: RatePeriod) -> None:
        """Update PG&E Time Of Use rate period energy credit for a submeter.

        Parameters
        ----------
        rate_period : RatePeriod
            Rate period to be updated.
        """
        energy_charge = next(
            (
                energy_charge
                for energy_charge in rate_period.energy_charges
                if energy_charge.tou == self.name
            ),
            None,
        )
        if energy_charge is None:
            raise LookupError(
                f'PG&E rate period {rate_period.period} ' f'missing {self.name} energy charge'
            )

        self.kWh: KilowattHours = energy_charge.kWh
        self.credit: Dollars = self.kWh * self.rate


class PCIACredit(EnergyCredit):
    """Bundled Power Charge Indifference Adjustment Credit.

    Notes
    -----
    Bundled Power Charge Indifference Adjustment (PCIA) may be negative.
    """

    def __init__(self, period: BillPeriod, kWh=KilowattHours(0)) -> None:
        """Initialize a PCIACredit instance for a RatePeriod.

        Parameters
        ----------
        period : BillPeriod
            Period instance.
        kWh : KilowattHours
            kWh used.

        """
        super().__init__(
            'Bundled PCIA', kWh, -PGEBEV1Tariff.effective_rates(period)['Bundled PCIA']
        )

    def submeter_energy_credit(self, rate_period: RatePeriod) -> None:
        """Update PG&E Bundled Power Charge Indifference Adjustment rate period
        credit for a submeter.

        Parameters
        ----------
        rate_period : RatePeriod
            Rate period to be updated.
        """
        self.kWh: KilowattHours = rate_period.total_kWh
        self.credit: Dollars = Dollars(self.kWh * self.rate)


class PDF(FPDF):
    """FPDF subclass to generate submeter bill headers and footers."""

    def __init__(self, submeter, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.submeter = submeter

    def header(self) -> None:
        """Write header to PDF file."""
        # Left edge: thumbnail photo
        self.image(Config.thumbnail, x=0.5, y=0.25, h=0.5)

        # Center: Title
        self.set_font('Helvetica', 'B', 11)
        self.set_xy(1 / 2 + 1 / 2, 3 / 8)
        self.multi_cell(
            3,
            None,
            Config.title,
            border=0,
            align='C',
            new_x=XPos.RIGHT,
        )

        # Right edge
        self.set_font('Courier', 'B', 11)
        self.set_xy(-(1 / 2 + 2.75), 1 / 4)
        account = 'Account:'
        statement_date = 'Statement Date:'
        due_date = 'Due Date:'
        title = f'{account:<15}{self.submeter.evse_id:>11}\n'
        title += f'{statement_date:<15}{self.submeter.submeter_bill.statement_date:>11}\n'
        title += f'{due_date:<15}{self.submeter.submeter_bill.due_date:>11}'
        self.multi_cell(2.75, None, title, border=0, align='R', new_x=XPos.RIGHT)

    def footer(self) -> None:
        """ "Write footer to PDF file."""
        self.set_font('Helvetica', '', 9)

        # Left edge: Help link
        self.set_xy(1 / 2, -1 / 2)  # position help link cell at lower left
        self.cell(
            3,
            1 / 4,
            markdown=True,
            text=(
                f'Questions? Email: [{Config.contact_email}](mailto:{Config.contact_email}'
                f'?subject=EV%20charger%20bill%20{self.submeter.evse_id}%20'
                f'{self.submeter.submeter_bill.statement_date})'
            ),
        )

        # Center: Today's date: mm/dd/yyyy
        self.set_xy(1 / 2 + 3 + 1 / 4, -1 / 2)  # position date cell at center
        today = datetime.today()
        self.cell(1, 1 / 4, f'{today.month}/{today.day}/{today.year}', border=0, align='C')

        # Right edge: Page number
        self.set_xy(-(1 / 2 + 3 / 4), -1 / 2)  # position page number cell at lower right
        self.cell(1, 1 / 4, f'Page {self.page_no()}', border=0, align='R')


class Submeter:
    """Submeter bill."""

    def __init__(self, main_bill: Bill, ev_chargers: EVChargers, evse_id: str) -> None:
        """Download Emporia Vue usage data and initialize submeter bill.

        Parameters
        ----------
        main_bill : Bill
            Full Bill instance for EV power panel.
        ev_chargers : EVChargers
            EVChargers instance.
        evse_id : str
            EVSE (EV charger) id

        Notes
        -----
        Best to use individual channels to monitor EV chargers with 2- or 3-pole
        breakers breakers:

        "If 2- or 3-pole breakers are to be monitored, we recommended that one
        CT be used for on each pole; however, to conserve the number of CTs, a
        single CT can be used. To use a single CT, clasp the clamp around either
        one of the non-neutral leads coming off the breaker (it doesn’t matter
        which). When only one CT is used, input a circuit multiplier in the app
        to double or triple the reading by entering a “2” or “1.7”. Using a
        single CT to monitor a multi-pole breaker does not accurately monitor
        unbalanced loads."

        """
        self.main_bill: Bill = main_bill
        """Full Bill instance for EV power panel."""
        self.evse_id: str = evse_id
        """EVSE (EV charger) id."""
        self.evse_kW_rating: Kilowatts = ev_chargers.chargers[evse_id].kW
        """EV charger power rating in kW."""
        self.total_evse_kW = ev_chargers.total_evse_kW
        self.hourly_kWh = ev_chargers.download_usage_data(self.evse_id, self.main_bill.period).data
        """Hourly energy usage data from Emporia Vue: hourly_kWh[day, hour]."""
        self.daily_kWh: npt.NDArray[np.float32] = self.hourly_kWh.sum(axis=1)
        """Daily energy usage: daily_kWh[day]."""
        self.daily_kWh.setflags(write=False)
        self.total_kWh = KilowattHours(str(self.hourly_kWh.sum()))
        """Total energy usage."""
        self.daily_tou_kWh: dict[Tou, npt.NDArray[np.float32]] = {
            tou: self.hourly_kWh[:, Config.tou_hours_mask[tou]].sum(axis=1) for tou in Tou
        }
        """Daily TOU energy usage: daily_tou_kWh[Tou] = daily_kWh[day]."""
        for tou in Tou:
            self.daily_tou_kWh[tou].setflags(write=False)
        self.total_tou_kWh: dict[Tou, KilowattHours] = {
            tou: KilowattHours(float(self.daily_tou_kWh[tou].sum())) for tou in Tou
        }
        """Total TOU energy usage: total_tou_kWh[Tou] = kWh."""
        self.tou_rates = main_bill.tou_rates()
        """tou_rates[Provider, day, hour] = rate ($/hourly_kWh)."""
        self.hourly_kWh_cost = self.hourly_kWh * self.tou_rates
        """hourly_kWh_cost[Provider, day, hour] = cost."""
        self.hourly_kWh_cost.setflags(write=False)
        self.daily_kWh_cost: npt.NDArray[np.float32] = self.hourly_kWh_cost.sum(axis=2)
        """daily_kWh_cost[Provider, day] = cost."""
        self.daily_kWh_cost.setflags(write=False)
        self.total_kWh_cost: npt.NDArray[np.float32] = self.daily_kWh_cost.sum(axis=1)
        """total_kWh_cost[Provider] = cost."""
        self.total_kWh_cost.setflags(write=False)
        self.daily_tou_kWh_cost: dict[Tou, npt.NDArray[np.float32]] = {
            tou: self.hourly_kWh_cost[:, :, Config.tou_hours_mask[tou]].sum(axis=2) for tou in Tou
        }
        """daily_tou_kWh_cost[Tou] = daily_kWh_cost[Provider, day]."""
        for tou in Tou:
            self.daily_tou_kWh_cost[tou].setflags(write=False)
        self.monthly_history_start_date: date
        """Monthly history start date."""
        self.monthly_tou_kWh_history = {
            tou: np.zeros((13), dtype=np.float32) for tou in Tou
        }  # monthly_tou_kWh_history[Tou][month] = kWh
        """Monthly TOU energy usage: monthly_tou_kWh_history[Tou][month] = kWh."""
        self.submeter_bill: Bill
        """Submeter bill initialized from main bill."""

        logger.info(f'Downloading historical usage data for EV charger {self.evse_id} ...')

        end_date: date = (
            self.period.to
            if (self.period.to + ONE_DAY).day == 1  # last day of month
            else self.period.to.replace(day=1) - ONE_DAY
        )  # last day of previous month
        self.monthly_history_start_date = (end_date - 12 * 31 * ONE_DAY).replace(day=1)
        for month in range(13):
            start_date = date(end_date.year, end_date.month, 1)
            period = BillPeriod(start_date.strftime('%m/%d/%Y'), end_date.strftime('%m/%d/%Y'))
            usage: UsageData = ev_chargers.download_usage_data(self.evse_id, period)
            if len(usage.empty_channels) > 0:  # Channel contained no data
                break  # No more usage data for this charger

            for tou in Tou:
                self.monthly_tou_kWh_history[tou][-1 - month] = usage.data[
                    :, Config.tou_hours_mask[tou]
                ].sum()

            end_date = start_date - ONE_DAY

        for tou in Tou:
            self.monthly_tou_kWh_history[tou].setflags(write=False)

        with np.printoptions(precision=2, floatmode='fixed'):
            logger.info(
                f'{month} month(s) usage data downloaded '
                f'for EV charger {self.evse_id} '
                f'starting from {self.monthly_history_start_date}:\n'
                f'{self.monthly_tou_kWh_history}'
            )

        self.submeter_bill = main_bill.submeter_bill(
            self
        )  # Initialize submeter bill from main bill

    def __str__(self) -> str:
        """Return a submeter bill as a formatted string."""
        return str(self.submeter_bill)

    @property
    def period(self) -> BillPeriod:
        """Return full bill period."""
        return self.main_bill.pge_bill_details.period

    def dump_usage_data(self, csvfile) -> None:
        """Dump submeter raw usage data to .CSV file.

        Parameters
        ----------
        csvfile : str
            CSV output file name.
        """
        date_strings = np.array(
            [date.strftime('%Y-%m-%d') for date in self.period.date_range()]
        ).reshape(-1, 1)
        combined_matrix = np.hstack((date_strings, self.hourly_kWh.astype(str)))
        np.savetxt(
            csvfile,
            combined_matrix,
            delimiter=',',
            fmt='%s',
            header=','.join(['Hour:'] + list(map(str, range(24)))),
        )

    def summary(self) -> str:
        """Return a submeter bill summary as a string."""
        s = '\n'.join(
            [
                f'Summary for Meter # {self.evse_id}',
                f'{"Charger Power Rating":<40} {self.evse_kW_rating:>12.2f} kW',
                self.submeter_bill.summary(),
            ]
        )
        return s

    def effective_rate(self) -> str:
        """Return effective $/kWh rate as a formatted string."""
        return self.submeter_bill.effective_rate()

    def as_text(self) -> str:
        """Return submeter bill as formatted string for print()."""
        return f'{str(self)}\n{self.summary()}\n\n{self.effective_rate()}'

    @functools.lru_cache
    def daily_tou_usage_cost_breakdown(self, tou: Tou) -> DailyUsageCostBreakdown:
        """Return submeter daily usage cost for specified TOU,
           generation credit + PCIA, and taxes + fees + surcharges.

        Parameters
        ----------
        Tou
            Time of Use.

        Returns
        -------
        DailyUsageCostBreakdown

        """
        pge_bill_details: PGEBillDetails = self.submeter_bill.pge_bill_details
        daily_kWh_cost = self.daily_tou_kWh_cost[tou].sum(axis=0)
        daily_kWh_cost.setflags(write=False)
        daily_gen_pcia = np.zeros((len(self.period)), dtype=np.float32)
        daily_tax_fees = np.zeros((len(self.period)), dtype=np.float32)
        daily_adjustment = np.zeros((len(self.period)), dtype=np.float32)

        for rate_period in pge_bill_details.rate_periods:
            assert isinstance(
                rate_period, PGERatePeriod
            ), f'Expected type(rate_period) PGERatePeriod; got {type(rate_period).__name__}'

            if rate_period.total_energy_charges == 0:
                continue

            start_index = (rate_period.period.fr - pge_bill_details.period.fr) // ONE_DAY
            stop_index = (rate_period.period.to - pge_bill_details.period.fr) // ONE_DAY + 1
            kWh_view = self.daily_tou_kWh[tou][start_index:stop_index]
            cost_view = self.daily_tou_kWh_cost[tou][Provider.PGE, :][start_index:stop_index]

            # PG&E TOU share of generation credit and pcia:

            daily_gen_pcia[start_index:stop_index] = (
                float(rate_period.tou_gen_credit_pcia_rates(tou)) * kWh_view
            )

            # PG&E TOU share of taxes and surcharges:

            daily_tax_fees[start_index:stop_index] = float(rate_period.other_pct_net_rates()) * (
                cost_view + daily_gen_pcia[start_index:stop_index]
            )

            # PG&E share of other energy fees, e.g. Franchise Fee Surcharge:

            daily_tax_fees[start_index:stop_index] += (
                float(rate_period.other_pct_energy_rates()) * cost_view
            )

        cpsf_bill_details: CPSFBillDetails = self.submeter_bill.cpsf_bill_details

        for rate_period in cpsf_bill_details.rate_periods:
            if rate_period.total_energy_charges == 0:
                continue

            start_index = (rate_period.period.fr - cpsf_bill_details.period.fr) // ONE_DAY
            stop_index = (rate_period.period.to - cpsf_bill_details.period.fr) // ONE_DAY + 1
            kWh_view = self.daily_tou_kWh[tou][start_index:stop_index]
            cost_view = self.daily_tou_kWh_cost[tou][Provider.CPSF, :][start_index:stop_index]

            # CPSF TOU share of taxes and surcharges, i.e. Local Utility Users Tax:

            daily_tax_fees[start_index:stop_index] += (
                float(rate_period.other_pct_net_rates()) * cost_view
            )

            # CPSF TOU share of other energy fees, i.e. Energy Commission Surcharge:

            daily_tax_fees[start_index:stop_index] += (
                float(rate_period.other_energy_rates()) * kWh_view
            )

        if (total_kWh_cost := self.total_kWh_cost.sum()) > 0:
            daily_adjustment = (
                float(self.submeter_bill.adjustment) * daily_kWh_cost / total_kWh_cost
            )

        daily_gen_pcia.setflags(write=False)
        daily_tax_fees.setflags(write=False)
        daily_adjustment.setflags(write=False)
        return DailyUsageCostBreakdown(
            tou, daily_kWh_cost, daily_gen_pcia, daily_tax_fees, daily_adjustment
        )

    def daily_tou_usage_cost(self, tou) -> npt.NDArray[np.float32]:
        """Return submeter daily total usage cost for specified TOU
           including PCIA, credits, taxes, surcharges, and metering
           difference adjustment.

        Parameters
        ----------
        tou: Tou
            Time of Use.

        Returns
        -------
        ndarray((len(bill period), dtype=np.float32)

        """
        usage = self.daily_tou_usage_cost_breakdown(tou)
        return usage.kWh_cost + usage.gen_pcia + usage.tax_fees + usage.adjustment

    @functools.lru_cache
    def daily_subscription_cost_breakdown(self) -> DailySubscriptionCostBreakdown:
        """Return daily subscription cost and taxes and surcharges.

        Returns
        -------
        DailySubscriptionCostBreakdown

        """
        pge_bill_details: PGEBillDetails = self.submeter_bill.pge_bill_details
        daily_subscription = np.full(len(pge_bill_details.period), np.nan, np.float32)
        daily_tax_fees = np.full(len(pge_bill_details.period), np.nan, np.float32)

        for rate_period in pge_bill_details.rate_periods:
            assert isinstance(
                rate_period, PGERatePeriod
            ), f'Expected type(rate_period) PGERatePeriod; got {type(rate_period).__name__}'

            start_index = (rate_period.period.fr - pge_bill_details.period.fr) // ONE_DAY
            stop_index = (rate_period.period.to - pge_bill_details.period.fr) // ONE_DAY + 1
            daily_subscription[start_index:stop_index] = float(
                rate_period.subscription.charge + rate_period.overage_fee.charge
            ) / len(rate_period)
            daily_tax_fees[start_index:stop_index] = (
                float(rate_period.other_pct_net_rates())
                * daily_subscription[start_index:stop_index]
            )

        daily_subscription.setflags(write=False)
        daily_tax_fees.setflags(write=False)
        return DailySubscriptionCostBreakdown(daily_subscription, daily_tax_fees)

    def daily_subscription_cost(self) -> npt.NDArray[np.float32]:
        """Return daily subscription cost including taxes and surcharges.

        Returns
        -------
        ndarray((len(bill period)), dtype=np.float32)

        """
        kW_costs = self.daily_subscription_cost_breakdown()
        return kW_costs.subscription + kW_costs.tax_fees

    def tou_usage_cost(self, tou) -> float:
        """Return energy usage cost including generation credit, PCIA, and
        metering adjustment for specified tou.

        Parameters
        ----------
        tou : Tou
            Time of Use.

        Returns
        -------
        cost: float

        """
        usage = self.daily_tou_usage_cost_breakdown(tou)
        tou_kWh_cost = usage.kWh_cost.sum()
        if tou_kWh_cost == 0:
            return 0

        tou_gen_pcia = usage.gen_pcia.sum()
        tou_adjustment = usage.adjustment.sum()
        return tou_kWh_cost + tou_gen_pcia + tou_adjustment

    def total_taxes_fees(self) -> float:
        """Return total taxes, fees, and surcharges."""
        tax_fees = self.daily_subscription_cost_breakdown().tax_fees.sum()
        for tou in Tou:
            usage = self.daily_tou_usage_cost_breakdown(tou)
            tax_fees += usage.tax_fees.sum()
        return tax_fees

    def plot_cost_pie(self, plotfile) -> None:
        """Write a pie chart of submeter costs to the specified PDF plotfile.

        Parameters
        ----------
        plotfile : file instance
            File to which the plot is written.

        """
        logger.info(f'Generating {self.evse_id} cost pie chart ...')

        PieSlice = namedtuple('PieSlice', 'size label color')
        pieslices = [
            PieSlice(
                (taxes_fees := self.total_taxes_fees()),
                f'Taxes & Fees\n${taxes_fees:.2f}    ',
                'darkgrey',
            ),
            PieSlice(
                (subscription := self.daily_subscription_cost_breakdown().subscription.sum()),
                f'Subscription\n${subscription:.2f}',
                'lightgrey',
            ),
            PieSlice(
                (super_off_peak := self.tou_usage_cost(Tou.SUPER_OFF_PEAK)),
                f' Super Off\nPeak ${super_off_peak:.2f}',
                'green',
            ),
            PieSlice(
                (off_peak := self.tou_usage_cost(Tou.OFF_PEAK)), f'Off Peak ${off_peak:.2f}', 'blue'
            ),
            PieSlice((peak := self.tou_usage_cost(Tou.PEAK)), f'Peak ${peak:.2f}', 'orange'),
        ]

        sizes, labels, colors = zip(*[pieslice for pieslice in pieslices if pieslice.size >= 0.01])

        plt.rcParams['font.size'] = 6
        fig, ax = plt.subplots(figsize=(4, 3.5))
        ax.pie(
            list(sizes),
            labels=list(labels),
            colors=list(colors),
            autopct='%1.1f%%',
            shadow=True,
            startangle=180,
            labeldistance=1.15,
        )

        # Draw border around chart
        # See: https://stackoverflow.com/questions/71817949/framing-a-pie-chart-in-matplotlib

        rect = plt.Rectangle(
            (-0.15, -0.1),
            1.275,
            1.15,
            fill=False,
            color='black',
            linewidth=1,
            zorder=-1,
            transform=ax.transAxes,
        )
        # rect = plt.Rectangle((0.01, 0.01), .98, .99,
        #                      fill=False, color='black', linewidth=1, zorder=-1,
        #                      transform=fig.transFigure)
        fig.add_artist(rect)

        plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        plt.title(f'{self.evse_id} Cost Breakdown {self.main_bill.period}', fontsize=9, pad=15)
        plt.savefig(plotfile, format='png')
        plt.close(fig)

    def plot_cost_vs_day(self, plotfile) -> None:
        """Write a stacked bar chart of submeter costs to the specified PDF plotfile.

        Parameters
        ----------
        plotfile : file instance
            File to which the plot is written.

        """
        logger.info(f'Generating {self.evse_id} cost stacked bar chart ...')
        categories = [str(d.day) for d in self.main_bill.period.date_range()]
        x = np.arange(len(self.main_bill.period))
        fig, ax = plt.subplots(figsize=(7.5, 2.0))
        subscription = self.daily_subscription_cost()
        super_off_peak = self.daily_tou_usage_cost(Tou.SUPER_OFF_PEAK)
        off_peak = self.daily_tou_usage_cost(Tou.OFF_PEAK)
        peak = self.daily_tou_usage_cost(Tou.PEAK)
        plt.bar(x, subscription, label='Subscription', color='gray')
        plt.bar(
            x,
            super_off_peak,
            bottom=subscription,
            label=f'{Tou.SUPER_OFF_PEAK}: 9am-2pm',
            color='green',
        )
        plt.bar(
            x,
            off_peak,
            bottom=subscription + super_off_peak,
            label=f'{Tou.OFF_PEAK}: All other hours',
            color='blue',
        )
        plt.bar(
            x,
            peak,
            bottom=subscription + super_off_peak + off_peak,
            label=f'{Tou.PEAK}: 4pm-9pm',
            color='orange',
        )
        ax.set_title(f'{self.evse_id} Energy Usage Cost {self.main_bill.period}', fontsize=9)
        ax.set_xlabel('Day of Month', fontsize=7)
        ax.yaxis.set_major_formatter('${:.2f}'.format)  # pylint: disable=consider-using-f-string
        ax.tick_params(axis='both', which='major', labelsize=6)
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.legend(
            loc='center left',
            bbox_to_anchor=(1, 0.5),
            fontsize=6,
            markerscale=0.4,
            labelspacing=0.4,
            borderpad=0.4,
        )
        plt.tight_layout()
        plt.plot()
        plt.savefig(plotfile, format='png')
        plt.close(fig)

    def plot_tou_kWh_history(self, plotfile) -> None:
        """Write a stacked bar chart of submeter TOU kWh usage to the specified PDF plotfile.

        Parameters
        ----------
        plotfile : file instance
            File to which the plot is written.

        """
        logger.info(f'Generating {self.evse_id} usage history stacked bar chart ...')
        months: list[str] = [
            (self.monthly_history_start_date + i * timedelta(days=31)).strftime('%b')
            for i in range(13)
        ]
        months[0] += f' {self.monthly_history_start_date.year}'
        months[-1] += f' {self.monthly_history_start_date.year + 1}'
        x = np.arange(13)
        fig, ax = plt.subplots(figsize=(7.5, 2.0))
        super_off_peak = self.monthly_tou_kWh_history[Tou.SUPER_OFF_PEAK]
        off_peak = self.monthly_tou_kWh_history[Tou.OFF_PEAK]
        peak = self.monthly_tou_kWh_history[Tou.PEAK]
        plt.bar(x, super_off_peak, label=f'{Tou.SUPER_OFF_PEAK}: 9am-2pm', color='green')
        plt.bar(
            x,
            off_peak,
            bottom=super_off_peak,
            label=f'{Tou.OFF_PEAK}: All other hours',
            color='blue',
        )
        plt.bar(
            x, peak, bottom=super_off_peak + off_peak, label=f'{Tou.PEAK}: 4pm-9pm', color='orange'
        )
        ax.set_title(f'{self.evse_id} Monthly kWh Usage {months[0]} - {months[-1]}', fontsize=9)
        ax.set_xlabel('Month', fontsize=8)
        ax.set_ylabel('kWh', fontsize=8)
        ax.tick_params(axis='both', which='major', labelsize=6)
        ax.set_xticks(x)
        ax.set_xticklabels(months)
        ax.legend(
            loc='center left',
            bbox_to_anchor=(1, 0.5),
            fontsize=6,
            markerscale=0.4,
            labelspacing=0.4,
            borderpad=0.4,
        )
        plt.tight_layout()
        plt.plot()
        plt.savefig(plotfile, format='png')
        plt.close(fig)

    def write_pdf(self, subbillfile) -> None:
        """Write a PDF submeter bill to the specified submeter billfile.

        Parameters
        ----------
        subbillfile : str
            Name of file to which PDF submeter bill is written.

        """
        logger.info(f'Writing {subbillfile} submeter bill ...')

        pdf = PDF(self, orientation='P', unit='in', format='letter')
        pdf.set_margins(top=1 / 4, left=1 / 2, right=1 / 2)
        pdf.set_author('Keith Gorlen gorlen@comcast.net')
        pdf.set_creator('evbilling.py')
        pdf.set_subject('EV Charging Bill')
        pdf.set_title('The Palace at Washington Square EV Charging Bill')
        pdf.set_keywords('EV EVSE PG&E BEV-1 CleanPowerSF BEV-1')

        # Write summary page

        pdf.add_page()
        pdf.set_font('Courier', 'B', 14)
        pdf.set_xy(1 / 2, 1)
        pdf.multi_cell(0, None, f'{self.summary()}\n\n', border=0, align='L')
        pdf.set_font('Helvetica', '', 12)
        pdf.multi_cell(0, None, self.effective_rate(), border=0, align='L')

        with tempfile.TemporaryFile() as plotfile:
            self.plot_cost_pie(plotfile)
            pdf.image(plotfile, x=2 + 3 / 16, y=7 - 0.5 - 3.5, w=4)

        with tempfile.TemporaryFile() as plotfile:
            self.plot_cost_vs_day(plotfile)
            pdf.image(plotfile, x=0.5, y=9 - 0.5 - 2, w=7.5)

        with tempfile.TemporaryFile() as plotfile:
            self.plot_tou_kWh_history(plotfile)
            pdf.image(plotfile, x=0.5, y=11 - 0.5 - 2, w=7.5)

        # Write PG&E Electric Delivery Charges details page

        pdf.add_page()
        pdf.set_font('Courier', '', 9)
        pdf.set_xy(1 / 2, 1)
        pdf.multi_cell(pdf.epw, None, str(self.submeter_bill.pge_bill_details), border=0, align='L')

        pdf.set_x(1 / 2)
        info = '\n'.join(['\n\nFurther information:\n', *Config.pge_reference_urls])
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(pdf.epw, markdown=True, text=info)

        # Write CleanPowerSF Electric Generation Charges details page

        pdf.add_page()
        pdf.set_font('Courier', '', 9)
        pdf.set_xy(1 / 2, 1)
        pdf.multi_cell(
            pdf.epw, None, str(self.submeter_bill.cpsf_bill_details), border=0, align='L'
        )

        pdf.set_x(1 / 2)
        info = '\n'.join(['\n\nFurther information:\n', *Config.cpsf_reference_urls])
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(pdf.epw, markdown=True, text=info)

        # Output the PDF file

        pdf.output(subbillfile)
        logger.info(f'Submeter bill written to {subbillfile}.')

    def valid(self) -> bool:
        """Validate a submeter bill.

        Returns
        -------
        bool
            True if Submeter is valid, else False.

        """
        logger.info(f'Validating {self.evse_id} submeter bill ...')
        ok = self.submeter_bill.valid()

        total_chart_cost = Dollars(
            sum(self.daily_tou_usage_cost(tou).sum() for tou in Tou)
            + self.daily_subscription_cost().sum()
        )

        tolerance = 0.005
        diff = round(
            float(
                abs(total_chart_cost - self.submeter_bill.total_amount_due)
                / self.submeter_bill.total_amount_due
            ),
            2,
        )
        if diff > tolerance and diff > 0.01:
            warning_msg(
                logger,
                f'Difference between total chart cost {total_chart_cost} and '
                f'total amount due {self.submeter_bill.total_amount_due} > '
                f'{tolerance:.1%}.',
            )
            ok = False

            # Log chart diagnostic info
            total_kWh_cost = 0
            total_gen_pcia = 0
            total_tax_fees = 0
            total_adjustment = 0
            for tou in Tou:
                usage = self.daily_tou_usage_cost_breakdown(tou)
                logger.info(f'  {tou} usage cost: ${usage.kWh_cost.sum():.2f}')
                logger.info(f'  {tou} gen + pcia: ${usage.gen_pcia.sum():.2f}')
                logger.info(f'  {tou} tax + fees: ${usage.tax_fees.sum():.2f}')
                logger.info(f'  {tou} adjustment: ${usage.adjustment.sum():.2f}')
                total_kWh_cost += usage.kWh_cost.sum()
                total_gen_pcia += usage.gen_pcia.sum()
                total_tax_fees += usage.tax_fees.sum()
                total_adjustment += usage.adjustment.sum()

            logger.info(f'  Total usage cost: ${total_kWh_cost:.2f}')
            logger.info(f'  Total gen + pcia: ${total_gen_pcia:.2f}')
            logger.info(f'  Total tax + fees: ${total_tax_fees:.2f}')
            logger.info(f'  Total adjustment: ${total_adjustment:.2f}')

            kW_costs = self.daily_subscription_cost_breakdown()
            logger.info(f'  Total subscription cost: ${kW_costs.subscription.sum():.2f}')
            logger.info(f'  Total subscr tax + fees: ${kW_costs.tax_fees.sum():.2f}')

        return ok


def log_environment() -> None:
    """Log the current environment variables and pipx or venv environment
    packages."""

    logger.debug('Current environment variables:')
    for key, value in os.environ.items():
        if key in ('PATH', 'PSMODULEPATH', 'VSCODE_ENV_PREPEND', 'VSCODE_ENV_REPLACE'):
            logger.debug(f'  {key}:')
            for path in value.split(':' if key == 'VSCODE_ENV_REPLACE' else ';'):
                logger.debug(f'    {path}')
        else:
            logger.debug(f'  {key}: {value}')

    def log_cmd_output(list_cmd: str) -> None:
        """Run command and log output.

        Parameters
        ----------
        list_cmd : str
            Command to run.
        """
        try:
            logger.debug(f'Running "{list_cmd}" ...')
            result = subprocess.run(list_cmd.split(), capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                logger.debug(line)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f'subprocess.run("{list_cmd}") failed: {e}.)')

    virtual_env = os.getenv('VIRTUAL_ENV')
    if virtual_env:
        logger.debug(f'Packages in {virtual_env} environment:')
        log_cmd_output('pip list')
        return

    log_cmd_output(f'pipx runpip {SCRIPT_NAME} list')


def file_path_generator(
    globs: list[str], pattern: Optional[str] = "*", recursive: bool = True
) -> Generator[Path, None, None]:
    """Generate matched files from a list of files and/or directories with
    globbing, environment variable substitution, '~' expansion, '-' input
    from stdin, and optional '**' recursion.

    Parameters
    ----------
    globs : list[str]
        List of file and directory paths to process.
    pattern : Optional[str], optional
        Glob pattern to match files, by default "*"
    recursive : bool, optional
        Process "**" directories recursively, by default True

    Yields
    ------
    Generator[Path, None, None]
        List of Path objects for matched files.
    """
    assert pattern is not None

    def expand_glob(glob_pattern: str) -> Generator[Path, None, None]:
        """Expand a glob

        Parameters
        ----------
        glob_pattern : str
            A glob.

        Yields
        ------
        Generator[Path, None, None]
            Paths from expanded glob.
        """
        for filename in glob.iglob(glob_pattern, recursive=recursive):
            path = Path(os.path.expanduser(os.path.expandvars(filename)))
            if path.is_file() and path.match(pattern):
                yield path

    for glob_pattern in globs:
        if glob_pattern == '-':
            logger.debug('Reading FILES from stdin ...')
            for stdin_glob in sys.stdin.read().splitlines():
                yield from expand_glob(stdin_glob.strip())
            continue

        path = Path(os.path.expanduser(os.path.expandvars(glob_pattern)))
        if path.is_dir():
            yield from expand_glob(str(path.joinpath(pattern)))
        else:
            yield from expand_glob(glob_pattern)


def pge_pdf_bill_paths(globs: list[str]) -> Generator[Path, None, None]:
    """Generate NNNNcustMMDDYYYY.pdf files from a list of files and/or
    directories with globbing.

    Parameters
    ----------
    globs : list[str]
        List of file and directory paths to process.

    Yields
    ------
        Path
            Absolute Path object for each matched file.
    Raises
    ------
    ValueError
        No PG&E PDF bill files specified
    """
    if not globs:
        raise ValueError('No PG&E PDF bill files specified')

    yield from [
        bill_path.absolute() for bill_path in file_path_generator(globs, '????custbill????????.pdf')
    ]


def process_main_bill(bill_path: Path) -> Bill:
    """Process the main PG&E bill for the EV power panel.

    Parameters
    ----------
    bill_path : Path
        Path to PG&E PDF bill.

    Returns
    -------
    Bill
        Bill instance.

    Raises
    ------
    ValueError
        Invalid bill file evse_id
    PermissionError
        Failed to copy PDF bill file to output directory
    """
    bill_file: Path = Args.bill_path.absolute()
    bill_filename: str = Args.bill_path.name

    # Parse statement date from PDF filename and create output subdirectory for
    # statement date.

    info_msg(logger, f'Processing {bill_file} ...')

    if (m := re.fullmatch(r'(\d{4})custbill(\d\d)(\d\d)(\d{4})\.pdf', bill_filename)) is None:
        raise ValueError(
            f'Invalid bill file evse_id {bill_filename}, must be NNNNcustbillMMDDYY.pdf'
        )

    account_last4 = m.group(1)  # pylint: disable=unused-variable
    statement_date_ymd = f'{m.group(4)}-{m.group(2)}-{m.group(3)}'

    out_subdir: Path = Args.outdir.joinpath(statement_date_ymd)
    os.makedirs(out_subdir, exist_ok=True)

    # Copy PDF bill file to output directory

    dest_file: Path = out_subdir.joinpath(bill_filename)
    logger.info(f'Copying "{bill_file}" to "{dest_file}" ...')

    try:
        if not dest_file.exists():  # Copy if file doesn't already exist
            shutil.copy2(bill_file, out_subdir)
            logger.info(f'File "{bill_file}" copied to "{dest_file}".')
        else:
            info_msg(logger, f'File "{bill_filename}" already exists in "{out_subdir}"')
    except PermissionError as e:
        raise PermissionError(f'Failed to copy "{Args.bill_path}" to "{dest_file}": {e}') from e

    # Extract text from PDF bill and create Bill instance.

    ocrpages: tuple[str, str] = extract_text(
        bill_file, out_subdir
    )  # Extract text pages from bill PDF

    logger.debug(f'Extracted text:\n{"".join(ocrpages)}')

    bill = Bill(ocrpages)  # Parse OCR text

    bill_ocrtxt: Path = out_subdir.joinpath(bill_path.stem + '.txt')
    logger.info(f'Writing {bill_ocrtxt} ...')
    with open(bill_ocrtxt, 'w', encoding='utf-8') as ocrtxt:
        print(bill.as_text(), file=ocrtxt)

    if Args.print:
        print(bill.as_text())

    bill.valid()

    return bill


def produce_submeter_bills(bill: Bill, ev_chargers: EVChargers) -> list[Submeter]:
    """Produce submeter bills from main PG&E bill and Emporia Vue usage data.

    Parameters
    ----------
    bill : Bill
        Main PG&E Bill instance.
    ev_chargers : EVChargers
        EVChargers instance.

    Returns
    -------
    List[Submeter]
        List of Submeter instances.
    """
    bill_path: Path = Path(Args.bill_path)
    out_subdir: Path = bill.out_subdir
    submeter_bills: list[Submeter] = [
        Submeter(bill, ev_chargers, evse_id) for evse_id in ev_chargers.chargers.keys()
    ]

    if not submeter_bills:
        raise ValueError('No active EV chargers found')

    # Calculate adjustment needed to make the sum of all submeter bills
    # equal to the PG&E bill. Submeter bill adjustments are proportional to
    # kWh usage.

    total_submeter_charges: Dollars = sum(
        subbill.submeter_bill.amount_due for subbill in submeter_bills
    )
    total_adjustment: Dollars = bill.amount_due - total_submeter_charges

    info_msg(
        logger,
        f'Adjustment for {bill.statement_date} bill: ${bill.amount_due} '
        f'- ${total_submeter_charges} = ${total_adjustment} '
        f'({total_adjustment/total_submeter_charges:.1%}).',
    )

    nbills = 0
    for nbills, subbill in enumerate(submeter_bills, 1):
        subbill_txt = out_subdir.joinpath(f'{bill_path.stem}-{subbill.evse_id}.txt')
        logger.info(f'Writing {subbill_txt} ...')
        with open(subbill_txt, 'w', encoding='utf-8') as subtxt:

            if bill.total_usage > 0:
                adjustment_share = subbill.total_kWh / bill.total_usage
                logger.info(
                    f'Adjustment share = '
                    f'{(adjustment_share):.1%}.'
                )
                subbill.submeter_bill.adjustment = Dollars(
                    total_adjustment * adjustment_share
                )
            else:
                subbill.submeter_bill.adjustment = Dollars('0.00')

            logger.info(
                f'Adjustment for {subbill.evse_id}: ' f'${subbill.submeter_bill.adjustment}.'
            )

            print(subbill.as_text(), file=subtxt)
            reset_errors()
            subbill.valid()

        # Write usage data to .csv file

        subbill_csv: Path = out_subdir.joinpath(f'{bill_path.stem}-{subbill.evse_id}.csv')
        logger.info(f'Writing {subbill_csv} ...')
        subbill.dump_usage_data(subbill_csv)

        # Write submeter bill PDF file

        subbill_pdf: Path = out_subdir.joinpath(f'{bill_path.stem}-{subbill.evse_id}.pdf')
        subbill.write_pdf(subbill_pdf)

        if warning_count() > 0:
            info_msg(logger, f'{warning_count()} warning(s) while processing {subbill_pdf}.')

        if error_count() > 0:
            info_msg(
                logger, f'{error_count()} error(s) found while processing {subbill_pdf}.'
            )

    info_msg(logger, f'{nbills} submeter bills written to "{out_subdir}".')

    return submeter_bills


def main() -> None:
    """evbilling.py main()

    Raises
    ------
    RuntimeError
        Error(s) found while processing PG&E PDF bill file
    RuntimeError
        Error(s) found while processing submeter_bills

    Notes
    -----
    - Perform Optical Character Recognition (OCR) on PG&E/CleanPowerSF PDF bills
      to obtain billing periods, rates, and charges.

    - Write an OCR sidecar text file, which can be edited if necessary to
      correct OCR errors.

    - Download hourly energy EV charger usage data for the billing period from
      the Emporia Vue server.

    - Write EV charger PDF and text submeter bills.

    """

    # Parse command line arguments

    Args.init()

    logger.info(f'{"=" * 60}')
    logger.info(f'{SCRIPT_NAME} version {__version__} starting in {os.getcwd()} ...')
    logger.info(f'Configuration loaded from "{Config.config_file}".')
    logger.info(f'{SCRIPT_NAME} arguments: {Args.as_string()}.')

    if Args.debug:
        logger.setLevel(logging.DEBUG)
        rotating_handler.setLevel(logging.DEBUG)

    log_environment()

    # Other Initialization

    getcontext().rounding = ROUND_HALF_UP
    """Class Decimal round $0.005 up to $0.01."""

    np.set_printoptions(linewidth=250, threshold=2 * 40 * 24)
    """Increase numpy linewidth and threshold for truncated print()."""

    PGEBEV1Tariff.init()

    if Args.version:
        info_msg(logger, f'{SCRIPT_NAME} version {__version__}')
        sys.exit(0)

    if Args.submeter:
        ev_em = EnergyMonitor()

    # Process PG&E PDF bills

    assert isinstance(Args.billfiles, list)
    for bill_path in pge_pdf_bill_paths(Args.billfiles):

        Args.bill_path = bill_path
        bill: Bill = process_main_bill(bill_path)
        out_subdir: Path = bill.out_subdir

        if warning_count() > 0:
            info_msg(
                logger, f'{warning_count()} warning(s) while processing {Args.bill_path}.'
            )

        if error_count() > 0:
            raise RuntimeError(
                f'{error_count()} error(s) found while processing {Args.bill_path}, '
                f'for details see log file: {Config.evbilling_log}'
            )

        # Produce submeter bills

        if Args.submeter:

            evse_file = out_subdir.joinpath(f'{bill_path.stem}-EVE.json')
            ev_chargers = EVChargers(ev_em, bill.period.to, evse_file)
            produce_submeter_bills(bill, ev_chargers)

            # Write all PDF bill files to NNNNcustbillMMDDYY.zip file

            zip_file: Path = out_subdir.joinpath(f'{bill_path.stem}.zip')
            logger.info(f'Writing {zip_file} ...')
            with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for pdf_file in out_subdir.glob('*.pdf'):
                    logger.info(f'Adding {pdf_file.name} to {zip_file} ...')
                    zipf.write(pdf_file, pdf_file.name)
            info_msg(logger, f'{zip_file} written to "{out_subdir}".')

    info_msg(logger, f'{SCRIPT_NAME} finished.')

    if total_error_count():
        raise RuntimeError(
            f'{total_error_count()} error(s) found while processing submeter_bills, '
            f'for details see log file: {evlogger.logfile}'
        )

    logger.info(f'{"=" * 60}')
    logging.shutdown()
    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except Exception as msg:  # pylint: disable=broad-exception-caught
        """Log a CRITICAL message and sys.exit(1)."""
        print(f'{datetime.now().strftime(DATE_FMT)} - CRITICAL - {msg}; exiting.', file=sys.stderr)
        logger.critical(f'{msg}; exiting.')
        logger.info(f'{"=" * 60}')
        logging.shutdown()
        sys.exit(1)
