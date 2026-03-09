'''
Created on September 16, 2025

@author: Keith Gorlen kgorlen@gmail.com

Email EV charging bills to customers and NNNNcustbillMMDDYYYY.zip file to
contact_email address.

'''

__author__ = 'Keith Gorlen'
__version__ = '1.2.3'

import os
import sys
import argparse
from datetime import datetime, date
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import smtplib
import ssl
from typing import NoReturn, Optional, NamedTuple
import re
import csv
import zipfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from io import TextIOWrapper
from functools import partial


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
"""Path to directory containing this Python script."""
sys.path.append(SCRIPT_DIR)
"""Allow evbilling CLI to import evsettings from script directory."""

# pylint: disable=wrong-import-position

from evsettings import Config
from evlogger import DATE_FMT, error_count, info_msg, warning_msg, error_msg
import evargs
import keyring
import evchargers
from evchargers import EnergyMonitor

# pylint: enable=wrong-import-position

# Global Constants

SCRIPT_NAME: str = Path(__file__).stem
"""Name of this script without .py extension."""

# Global Variables

# Initialize logger

logger = logging.getLogger(SCRIPT_NAME)
"""Logging facility."""
logger.setLevel(logging.INFO)
rotating_handler = RotatingFileHandler(
    Config.evmailbills_log, maxBytes=1 * 1024 * 1024, backupCount=3
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
evchargers.logger = logging.getLogger('mailevbills.evchargers')


class ParsedArgs(NamedTuple):
    """Parsed command line options and arguments."""

    debug: bool
    """Log debugging information; default --no-debug."""
    version: bool
    """Display the version number and exit."""
    dry_run: bool
    """Do not actually send emails; default --no-dry-run."""
    test_run: Optional[str]
    """If given, send all emails to this address."""
    msg: str
    """Message to append to the email body; default: empty."""
    input_file: Path
    """Path to a .zip file containing PDF bills (required)."""


ARGS: ParsedArgs
"""Arguments parsed by argparse() in main()."""


def ask_yes_no(prompt: str = "Continue? (y/n): ") -> bool:
    """Prompt the user with a yes/no question.

    Parameters
    ----------
    prompt : str, optional
        The question to ask the user, by default "Continue? (y/n): "

    Returns
    -------
    bool
        True if the user answered yes, False if no.
    """
    while True:
        answer = input(prompt).strip().lower()
        if answer in ("y", "yes"):
            return True

        if answer in ("n", "no"):
            return False

        print("Please enter 'y' or 'n'.")


def cleanup_and_exit(status: int = 0) -> NoReturn:
    """Clean up and exit with the given status code."""
    info_msg(logger, f'{SCRIPT_NAME} finished.')
    logger.info(f'{"=" * 60}')
    logging.shutdown()
    input('Press Enter to exit ...')
    sys.exit(status)


def fatal_error(msg: str) -> NoReturn:
    """Log a CRITICAL message and sys.exit(1)."""
    print(f'{datetime.now().strftime(DATE_FMT)} - CRITICAL - {msg}; exiting.', file=sys.stderr)
    logger.critical(f'{msg}; exiting.')
    cleanup_and_exit(1)


def parse_args() -> ParsedArgs:
    """Parse command line arguments.

    Returns:
        ParsedArgs: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description='Send EV charging bill PDFs to charger owners via email.'
    )
    parser.add_argument(
        '-d',
        '--debug',
        action=argparse.BooleanOptionalAction,
        default=False,
        help='Log debug info; default --no-debug',
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--dry-run',
        action=argparse.BooleanOptionalAction,
        default=False,
        help='Do not send emails; default --no-dry-run',
    )
    group.add_argument(
        '--test-run',
        metavar="ADDRESS",
        type=str,
        default='',
        help='Send all emails to this address instead of the charger owner(s).',
    )
    parser.add_argument(
        '--msg',
        '--message',
        type=str,
        default='',
        help='Message to append to the email body; default: empty',
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
        'input_file',
        type=Path,
        help='Path to a .zip file containing PDF bills or a single .pdf file',
    )

    args_dict: dict[str, Optional[bool | str | int]] = vars(parser.parse_args())
    return ParsedArgs(**args_dict)  # type: ignore


def smtp_connection() -> smtplib.SMTP:
    """Establish and return an SMTP connection.

    Raises:
        LookupError: If the SMTP server password is not found.

    Returns:
        smtplib.SMTP: The established SMTP connection.
    """
    logger.info(
        f'Getting SMTP server {Config.smtp_server} password for {Config.smtp_user} from keyring...'
    )
    password: str | None = keyring.get_password(Config.smtp_server, Config.smtp_user)
    if not password:
        if password is None:
            error_msg(
                logger,
                f'keyring.get_password("{Config.smtp_server}", "{Config.smtp_user}") Failed.\n',
            )
        else:
            error_msg(
                logger,
                f'keyring.get_password("{Config.smtp_server}", "{Config.smtp_user}") '
                f'Returned empty password.\n',
            )
        info_msg(
            logger,
            f'Set SMTP server password with the command:\n'
            f'\tkeyring set {Config.smtp_server} {Config.smtp_user}',
        )
        raise LookupError(f'{Config.smtp_server} {Config.smtp_user} password not found.')

    # Create SMTP connection using SSL for port 465, STARTTLS for port 587 (or others)
    smtp_port: int = getattr(Config, 'smtp_port', 465)
    if smtp_port == 465:
        logger.info(f'Connecting using SMTP_SSL for port {smtp_port} ...')
        ctx = ssl.create_default_context()
        smtp_conn = smtplib.SMTP_SSL(
            host=Config.smtp_server, port=smtp_port, context=ctx, timeout=60
        )
        smtp_conn.ehlo()
        logger.info(f'Connected to SMTP_SSL {Config.smtp_server}:{smtp_port}')
    else:
        logger.info(f'Connecting using SMTP with STARTTLS for port {smtp_port} ...')
        ctx = ssl.create_default_context()
        smtp_conn = smtplib.SMTP(host=Config.smtp_server, port=smtp_port, timeout=60)
        smtp_conn.ehlo()
        smtp_conn.starttls(context=ctx)
        smtp_conn.ehlo()
        logger.info(f'Connected to SMTP with STARTTLS {Config.smtp_server}:{smtp_port}')

    info_msg(
        logger,
        f'Logging into SMTP server {Config.smtp_server}:{smtp_port} as {Config.smtp_user} ...',
    )
    smtp_conn.login(Config.smtp_user, password)
    info_msg(
        logger,
        f'Log in OK, connected to SMTP server '
        f'{Config.smtp_server}:{smtp_port} as {Config.smtp_user}.',
    )
    return smtp_conn


def get_statement_date(pdf_path: Path) -> str:
    """Extract statement date from filename.

    Args:
        pdf_path (Path): Path to PDF file named NNNNcustbillMMDDYYYY[-EVSE].pdf
        or .zip file named NNNNcustbillMMDDYYYY.zip

    Raises:
        ValueError: If the filename does not match the expected pattern.
        ValueError: If the statement date in the filename is invalid.

    Returns:
        str: The extracted statement date in MM/DD/YYYY format.
    """
    match = re.match(r'^\d{4}custbill(\d{8})', pdf_path.name)
    if not match:
        raise ValueError(
            f'Filename "{pdf_path.name}" does not match expected pattern NNNNcustbillMMDDYYYY.'
        )

    mmddyyyy = match.group(1)
    try:
        stmt_date: date = datetime.strptime(mmddyyyy, '%m%d%Y').date()
    except ValueError as e:
        raise ValueError(f'Invalid date "{mmddyyyy}" in filename "{pdf_path.name}": {e}') from e

    statement_date: str = f'{stmt_date.month}/{stmt_date.day}/{stmt_date.year}'
    return statement_date


def get_evse_id(pdf_path: Path) -> str:
    """Extract EVSE ID from PDF filename.

    Args:
        pdf_path (Path): Path to PDF file named NNNNcustbillMMDDYYYY[-EVSE].pdf

    Raises:
        ValueError: If the filename does not match the expected pattern.

    Returns:
        str: The extracted EVSE ID.
    """
    stem: str = pdf_path.stem
    m = re.match(r'^\d{4}custbill\d{8}-(.+)$', stem, re.IGNORECASE)
    if m:
        evse_id = m.group(1)
        return evse_id

    raise ValueError(
        f'Input PDF "{pdf_path.name}" does not match expected name format; '
        f'expected NNNNcustbillMMDDYYYY-EVSE.pdf'
    )


def send_mail(
    subject: str,
    msg: MIMEMultipart,
    mail_to: list[str],
    mail_from: str,
    smtp: smtplib.SMTP,
    attachments: Optional[list[tuple[str, bytes]]] = None,
) -> None:
    """Send email message with optional attachments.
    Args:
        subject (str): The subject of the email.
        body (MIMEMultipart): The body content of the email.
        mail_to (list[str]): List of recipient email addresses.
        mail_from (str): Sender email address.
        smtp (smtplib.SMTP): Established SMTP connection.
        attachments (Optional[list[tuple[str, bytes]]], optional): List of
            attachments as (filename, bytes). Defaults to None.
    """
    msg["From"] = mail_from
    msg["To"] = ', '.join(mail_to)
    msg["Subject"] = subject

    if attachments:
        for fname, data in attachments:
            part = MIMEApplication(data, Name=fname)
            part['Content-Disposition'] = f'attachment; filename="{fname}"'
            msg.attach(part)

    smtp.send_message(msg)


def email_bill(
    pdf_path: Path,
    pdf_bytes: bytes,
    statement_date: str,
    evse_id: str,
    email_list: list[str],
    email_msg: str,
    smtp_conn: smtplib.SMTP,
) -> None:
    """Send an email with the PDF bill attached.

    Args:
        pdf_path (Path): Path to the PDF file.
        pdf_bytes (bytes): Bytes of the PDF file.
        statement_date (str): Statement date for the bill.
        evse_id (str): EVSE ID for the charger.
        email_list (list[str]): List of email addresses to send the bill to.
        email_msg (str): Optional message to include in the email body.
        smtp_conn (smtplib.SMTP): SMTP connection instance.
    """
    pdf_name: str = pdf_path.name
    if not email_list:
        warning_msg(logger, f'No owner email addresses for {evse_id}; skipping {pdf_name}.')
        return

    subject = f'{re.sub(r'\s+', ' ', Config.title)} for {statement_date}'
    body: MIMEMultipart = MIMEMultipart()
    body.attach(
        MIMEText(
            f'Attached is your EV charging bill with statement date {statement_date} '
            f'for EV charger {evse_id}.  '
            f'The Total Amount Due will be included in your monthly HOA assessment.\n\n'
        )
    )
    if email_msg:
        body.attach(MIMEText(f'{email_msg}\n\n'))
    attachments = [(pdf_name, pdf_bytes)]

    if ARGS.dry_run is True:
        info_msg(logger, f'DRY RUN: would send {pdf_name} to {email_list}')
        return

    mail_to: list[str] = [ARGS.test_run] if ARGS.test_run else email_list

    try:
        logger.info(f'Sending {pdf_name} to {mail_to} ...')
        send_mail(subject, body, mail_to, Config.contact_email, smtp_conn, attachments)
        info_msg(logger, f'Sent {pdf_name} to {mail_to}')
    except smtplib.SMTPException as e:
        error_msg(
            logger, f'Failed to send {pdf_name} to {mail_to} from {Config.contact_email}: {e}'
        )


def email_zip(
    zip_path: Path,
    zip_bytes: bytes,
    statement_date: str,
    smtp_conn: smtplib.SMTP,
) -> None:
    """Send an email with amounts due table and the ZIP file attached.

    Args:
        zip_path (Path): Path to the ZIP file.
        zip_bytes (bytes): Bytes of the ZIP file.
        statement_date (str): Statement date for the bill.
        smtp_conn (smtplib.SMTP): SMTP connection instance.
    """
    zip_name: str = zip_path.name
    csv_filename: str = zip_path.stem + '-DUE.csv'
    body: MIMEMultipart = MIMEMultipart()

    logger.info(f'Extracting {csv_filename} from {zip_name} ...')
    with zipfile.ZipFile(zip_path, "r") as z:
        with z.open(csv_filename) as f:
            wrapper = TextIOWrapper(f, encoding="utf-8")
            reader = csv.reader(wrapper)
            rows = list(reader)

    # --- Convert to HTML table ---
    html: list[str] = [
        "<html><body>",
        "Attached is the ZIP file containing all EV charging submeter bills with statement date "
        f"{statement_date}.  "
        "Please include the Amounts Due below in the monthly HOA assessments.<br><br>",
        "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse:collapse;'>",
        f"<tr>{''.join(f'<th>{col}</th>' for col in rows[0])}</tr>",
    ]

    for row in rows[1:]:
        html.append(f'<tr><td>{row[0]}</td><td style="text-align:right;">${row[1]}</td></tr>')

    html.append("</table></body></html><br>")
    html.append(
        "EV Charger PWS-<i>uuu</i>-P<i>nn</i>:<br>"
        "PWS = The Palace at Washington Square<br>"
        "<i>uuu</i> = Unit #<br>"
        "P<i>nn</i> = Parking space #<br>"
    )
    html_body = "\n".join(html)
    body.attach(MIMEText(html_body, "html"))
    subject = f'{re.sub(r"\s+", " ", Config.title)} for {statement_date}'
    attachments = [(zip_name, zip_bytes)]

    if ARGS.dry_run:
        info_msg(logger, f'DRY RUN: would send {zip_name} to {Config.billing_emails}')
        return

    mail_to: list[str] = [ARGS.test_run] if ARGS.test_run else Config.billing_emails

    try:
        logger.info(f'Sending {zip_name} to {mail_to} ...')
        send_mail(subject, body, mail_to, Config.contact_email, smtp_conn, attachments)
        info_msg(logger, f'Sent {zip_name} to {mail_to}')
    except smtplib.SMTPException as e:
        error_msg(logger, f'Failed to send {zip_name} to {mail_to}: {e}')


def main() -> None:
    """Process PG&E bill, get Emporia Vue data, and write submeter bills.

    Raises:
        RuntimeError: If any errors were encountered during processing.
    """
    global ARGS  # pylint: disable=global-statement
    logger.info(f'{"=" * 60}')
    logger.info(f'{SCRIPT_NAME} version {__version__} starting ...')
    logger.info(f'Configuration loaded from "{Config.config_file}".')

    ARGS = parse_args()
    logger.info(f'{SCRIPT_NAME} arguments: {ARGS}.')

    if ARGS.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        rotating_handler.setLevel(logging.DEBUG)

    # Set arguments also used by imported modules.
    evargs.Args.debug = ARGS.debug
    evargs.Args.quiet = False  # Always print INFO, WARNING, ERROR, CRITICAL to stderr

    # Input file is required; validate the path exists
    if not ARGS.input_file.exists():
        fatal_error(f'Input file "{ARGS.input_file}" not found.')

    email_funcs: list[partial] = []
    """List of partial functions to email bills and zip file."""
    smtp_conn: smtplib.SMTP = smtp_connection()
    """Established SMTP connection."""
    energy_monitor: EnergyMonitor = EnergyMonitor()
    """EnergyMonitor instance."""
    energy_monitor.discover_chargers(date.today())

    info_msg(logger, f'Processing input file "{ARGS.input_file}" ...')

    # Support either a .zip containing many PDFs or a single .pdf file

    input_suffix: str = ARGS.input_file.suffix.lower()
    """Input file suffix, .zip or .pdf."""
    statement_date: str = get_statement_date(ARGS.input_file)
    """MM/DD/YYYY statement date extracted from input filename."""
    stmt_dt: date = datetime.strptime(statement_date, '%m/%d/%Y').date()
    """Statement date as a date object."""

    if (date.today() - stmt_dt).days > 30:
        info_msg(logger, f'Statement date {statement_date} is more than 30 days old.')
        if not ask_yes_no():
            info_msg(logger, 'Operation cancelled; no emails sent.')
            return

    if not ARGS.msg:
        email_msg: str = input(
            'Enter optional message to include with email; press Enter if none: '
        ).strip()
    else:
        email_msg = ARGS.msg

    if input_suffix == '.zip':
        with zipfile.ZipFile(ARGS.input_file, 'r') as z:
            for f in z.namelist():
                if not (m := re.match(r'\d{4}custbill\d{8}(?:-(.+))?\.pdf$', f, re.IGNORECASE)):
                    if f.endswith('-DUE.csv'):
                        continue  # Skip the amounts due CSV file

                    warning_msg(
                        logger, f'Skipping unexpected file "{f}" in zip archive {ARGS.input_file}.'
                    )
                    continue

                if not m.group(1):
                    logger.info(f'Skipping "{f}".')
                    continue

                evse_id = m.group(1)
                email_list: list[str] = energy_monitor.chargers[evse_id].owner_emails

                if not email_list:
                    warning_msg(
                        logger,
                        f'No owner email address for {evse_id}; '
                        f'skipping {f} in {ARGS.input_file}.',
                    )
                    continue

                pdf_path: Path = Path(f)
                pdf_bytes = z.read(f)
                email_funcs.append(
                    partial(
                        email_bill,
                        pdf_path,
                        pdf_bytes,
                        statement_date,
                        evse_id,
                        email_list,
                        email_msg,
                        smtp_conn,
                    )
                )
                info_msg(
                    logger, f'Ready to send bill for charger {evse_id} to {", ".join(email_list)}.'
                )

        zip_path = ARGS.input_file
        zip_bytes = zip_path.read_bytes()
        email_funcs.append(partial(email_zip, zip_path, zip_bytes, statement_date, smtp_conn))
        info_msg(
            logger,
            f'Ready to send amounts due and {zip_path.name} file to '
            f'{", ".join(Config.billing_emails)}.',
        )

    elif input_suffix == '.pdf':
        pdf_path = ARGS.input_file
        pdf_bytes = pdf_path.read_bytes()
        evse_id = get_evse_id(pdf_path)
        email_list = energy_monitor.chargers[evse_id].owner_emails
        if not email_list:
            warning_msg(
                logger,
                f'No owner email address for {evse_id}; '
                f'skipping {pdf_path.name} in {ARGS.input_file}.',
            )

        email_funcs.append(
            partial(
                email_bill,
                pdf_path,
                pdf_bytes,
                statement_date,
                evse_id,
                email_list,
                email_msg,
                smtp_conn,
            )
        )
        info_msg(logger, f'Ready to send bill for charger {evse_id} to {", ".join(email_list)}.')

    else:
        fatal_error(f'Input file "{ARGS.input_file}" must be a .zip or .pdf file')

    if error_count():
        raise RuntimeError(
            f'{error_count()} error(s) found while processing {ARGS.input_file}, '
            f'for details see log file: {Config.evmailbills_log}'
        )

    if not email_funcs:
        info_msg(logger, f'No emails to send for input file "{ARGS.input_file}".')
        return

    if ARGS.test_run:
        info_msg(
            logger,
            f'Test run: all emails will be sent to {ARGS.test_run} instead of charger owners.',
        )

    if ask_yes_no():
        for func in email_funcs:
            func()
    else:
        info_msg(logger, 'Operation cancelled; no emails sent.')


def cli() -> None:
    """Command line interface for mailevbills."""
    try:
        main()
        cleanup_and_exit(0)
    except Exception as e:  # pylint: disable=broad-exception-caught
        fatal_error(str(e))


if __name__ == '__main__':
    cli()
