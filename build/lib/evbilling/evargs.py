'''

@author: Keith Gorlen kgorlen@gmail.com

Parse evbilling command line arguments.
'''

__author__ = 'Keith Gorlen'

import sys
import argparse
from pathlib import Path
import tempfile
import shlex
from typing import Any, Optional


def writable_dir(directory_path: Path) -> Path:
    """Return absolute path of directory if writable, else raise error.

    Parameters
    ----------
    directory_path : Path
        Path to output directory.

    Returns
    -------
    Path
        Absolute path of 'directory_path' if it is writable.

    Raises
    ------
    argparse.ArgumentTypeError
        If 'directory_path' not writable or does not exist.

    """
    try:
        # Attempt to write to the temporary file
        with tempfile.NamedTemporaryFile(mode='w', dir=directory_path) as test_file:
            test_file.write("test")
        return Path(directory_path).absolute()

    except PermissionError as e:
        raise PermissionError(f'{e}: "{directory_path}" is not writable.') from e
    except FileNotFoundError as e:
        raise FileNotFoundError(f'{e}: "{directory_path}" does not exist.') from e


class Args:
    """Parsed command line options and arguments."""

    autoblock: Optional[bool]
    """Automatically locate OCR text blocks; default --autoblock."""
    debug: Optional[bool]
    """Log debugging information; default --no-debug."""
    fixocr: Optional[bool]
    """Fix obvious OCR errors; default --fixocr."""
    forceocr: Optional[bool]
    """Force OCR; default --no-forceocr."""
    outdir: Path
    """Output directory, default current working directory."""
    pages: int
    """Two single-digit page numbers, *i* is the *Details of PG&E
    Electric Delivery Charges* page number and *j* is the *Details of CleanPowerSF
    Electric Generation Charges* page number; default: 34."""
    print: Optional[bool]
    """Print PG&E bill OCR text to `stdout`; default: --no-print."""
    quiet: Optional[bool]
    """Do not print INFO, WARNING, ERROR, or CRITICAL messages to `stderr`;
    default --no-quiet."""
    showocr: Optional[bool]
    """Show OCR result; implies **--forceocr**; default --no-showocr."""
    submeter: Optional[bool]
    """Write PDF submeter bills; default --submeter."""
    version: Optional[bool]
    """Display the version number and exit."""
    billfiles: str
    """List of PG&E PDF bill files to be processed.  *FILES* must have the format
    *nnnn*custbill*mmddyyyy*.pdf, where *nnnn* is the last four digits of the
    PG&E account number and *mmddyyyy* is the PG&E bill statement date."""

    bill_path: Path = Path('')
    """Class variable: Current PG&E PDF bill file Path."""

    args_dict: dict[str, Any]
    """Dictionary of command line options and arguments."""

    @classmethod
    def init(cls) -> None:
        """Parse command line options and arguments.

        Raises
        ------
        ValueError
            No PG&E PDF bill files specified.
        """
        parser = argparse.ArgumentParser(description='Generate EV charger bills')
        parser.add_argument(
            '--autoblock',
            action=argparse.BooleanOptionalAction,
            default=True,
            help='Automatically locate text blocks',
        )
        parser.add_argument(
            '-d', '--debug', action=argparse.BooleanOptionalAction, help='Log debug info'
        )
        parser.add_argument(
            '--fixocr',
            action=argparse.BooleanOptionalAction,
            default=True,
            help='Fix obvious OCR errors',
        )
        parser.add_argument(
            '--forceocr',
            action=argparse.BooleanOptionalAction,
            help='Force OCR',
        )
        parser.add_argument(
            '--outdir',
            metavar='DIRECTORY',
            type=Path,
            default=Path('.'),
            help='Output directory; default current working directory',
        )
        parser.add_argument(
            '--pages',
            type=int,
            default=34,
            help='Two single-digit page numbers of PG&E and CPSF charges, respectively; default 34',
        )
        parser.add_argument(
            '--print',
            action=argparse.BooleanOptionalAction,
            default=False,
            help='Print PG&E bill OCR text to stdout',
        )
        parser.add_argument(
            '-q',
            '--quiet',
            action=argparse.BooleanOptionalAction,
            default=False,
            help='Do not print verbose output',
        )
        parser.add_argument(
            '--showocr',
            action=argparse.BooleanOptionalAction,
            default=False,
            help='Show OCR result; implies --forceocr',
        )
        parser.add_argument(
            '--submeter',
            action=argparse.BooleanOptionalAction,
            default=True,
            help='Write PDF submeter bills',
        )
        parser.add_argument(
            '-v',
            '--version',
            action=argparse.BooleanOptionalAction,
            default=False,
            help='Display the version number and exit',
        )
        parser.add_argument(
            'billfiles', metavar='FILES', type=str, nargs='*', help='PG&E .pdf bills to process'
        )

        if len(sys.argv) < 2:
            raise ValueError('No PG&E PDF bill files specified')

        arg_list = None if len(sys.argv) > 2 else shlex.split(sys.argv[1])
        cls.args_dict = vars(parser.parse_args(arg_list))

        # ARGS.outdir is writeable absolute Path
        assert isinstance(cls.args_dict['outdir'], Path)
        cls.args_dict['outdir'] = writable_dir(cls.args_dict['outdir'])

        for var, value in cls.args_dict.items():
            setattr(cls, var, value)

    @classmethod
    def as_string(cls) -> str:
        """Return arguments as string."""
        return ', '.join([f'{var}={value}' for var, value in cls.args_dict.items()])
