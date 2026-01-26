'''
evfiles.py -- Manage file naming for EV billing.

'''

__author__ = 'Keith Gorlen'

import os
import sys
import logging
from pathlib import Path
import re

SCRIPT_DIR: Path = Path(__file__).absolute().parent
"""Path to directory containing this Python script."""
sys.path.append(str(SCRIPT_DIR))
"""Allow evbilling CLI to import modules from script directory."""

# pylint: disable=wrong-import-position

from __init__ import __version__
from evargs import Args
from evlogger import (
    info_msg,
)

# pylint: enable=wrong-import-position

logger = logging.getLogger(f'evbilling.{__name__}')


class EVFiles:
    """Handles file naming for EV billing."""

    def __init__(self, bill_path: Path):
        """Initialize EVFiles with a bill path."""
        self.bill_path: Path = bill_path.absolute()
        """Current path to bill file."""
        self.bill_filename: str = bill_path.name
        """Current bill file name."""
        self.outdir: Path
        """Current output directory."""
        self.account_last4: str = ''
        """Last 4 digits of account number before '-' from bill file name."""
        self.statement_date_ymd: str = ''
        """Statement date MMDDYYYY from bill file name."""
        self.bill_id: str = ''
        """Bill file identifier from bill file name."""

        info_msg(logger, f'Processing {self.bill_path} ...')

        if m := re.fullmatch(r'(\d{4})custbill(\d\d)(\d\d)(\d{4})\.pdf', self.bill_filename):
            # Parse statement date from PDF filename.
            self.account_last4 = m.group(1)
            self.statement_date_ymd: str = f'{m.group(4)}-{m.group(2)}-{m.group(3)}'
            self.outdir = (
                Args.outdir if Args.outdir else (self.bill_path.parent / self.statement_date_ymd)
            )

        elif m := re.fullmatch(
            r'([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\.pdf', self.bill_filename
        ):
            # Parse bill ID from UUID-based bill filename and create output subdirectory.
            self.bill_id = m.group(1)
            self.outdir = Args.outdir if Args.outdir else (self.bill_path.parent / self.bill_id)
        else:
            raise ValueError(
                f'Invalid bill file evse_id {self.bill_filename}, must be NNNNcustbillMMDDYYYY.pdf '
                f'or xxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.pdf'
            )

        logger.info(f'Creating output directory {self.outdir} ...')
        os.makedirs(self.outdir, exist_ok=True)

    def outdir_path(self, suffix: str) -> Path:
        """Return the output directory path with a suffix.
        Args:
            suffix: Suffix to append to the bill file stem, e.g. '-DUE.txt'.

        Returns:
            Path for file with the specified suffix in the output directory.
        """
        return self.outdir.joinpath(self.bill_path.stem + suffix)

    def rename(self, statement_date: str, account_no: str) -> None:
        """Rename files to standardized names.

        Args:
            statement_date: PG&E statement date mm/dd/yyyy.
            account_no: PG&E account number nnnnnnnnnn-n.

        """
        self.account_last4 = account_no[-6:-2]
        self.statement_date_ymd = (f'{statement_date[6:10]}-'
                                   f'{statement_date[0:2]}-'
                                   f'{statement_date[3:5]}')
        new_bill_stem: str = f'{self.account_last4}custbill{statement_date.replace("/", "")}'

        if not Args.outdir:
            info_msg(
                logger,
                f'Renaming output directory {self.bill_id} to 'f'{self.statement_date_ymd} ...',
            )
            new_out_subdir: Path = self.bill_path.parent / (
                statement_date[6:10] + '-' + statement_date[0:2] + '-' + statement_date[3:5]
            )
            if new_out_subdir.exists():
                info_msg(logger, f'Removing existing directory {new_out_subdir} ...' )
                for file in new_out_subdir.iterdir():
                    if file.is_file():
                        file.unlink()
                new_out_subdir.rmdir()
            self.outdir = self.outdir.rename(new_out_subdir)

        info_msg(logger, f'{"Linking" if Args.link else "Renaming"} PG&E bill file '
                 f'from {self.bill_id}.pdf to {new_bill_stem}.pdf ...')
        new_bill_path: Path = self.bill_path.parent / f'{new_bill_stem}.pdf'
        if new_bill_path.exists():
            info_msg(logger, f'Removing existing PG&E bill file {new_bill_path} ...' )
            new_bill_path.unlink()
        if Args.link:
            info_msg(logger, f'Linking {self.bill_path} to {new_bill_path} ...')
            os.link(self.bill_path, new_bill_path)
        else:
            self.bill_path.rename(new_bill_path)
        self.bill_path = new_bill_path
        self.bill_filename = new_bill_path.name

        # Rename files in output subdirectory to match new bill file stem.
        for file in self.outdir.iterdir():
            if file.is_file() and (
                m := re.fullmatch(rf'{self.bill_id}(-.+)?', file.stem)
            ):
                new_file_path: Path = (
                    self.outdir
                    / f'{new_bill_stem}{m.group(1) if m.group(1) else ""}{file.suffix}'
                )
                info_msg(
                    logger,
                    f'Renaming {file.name} to {new_file_path.name}',
                )
                file.rename(new_file_path)
