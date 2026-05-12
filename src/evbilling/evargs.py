'''

@author: Keith Gorlen kgorlen@gmail.com

Parse evbilling command line arguments.
'''

__author__ = 'Keith Gorlen'

import os
import sys
import logging
import argparse
from pathlib import Path
import glob
import tempfile
import shlex
from typing import Any, Optional, Generator

logger = logging.getLogger(f'evbilling.{__name__}')


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

    debug: bool
    """Log debugging information; default --no-debug."""
    link: bool
    """Link PDF bill input file to standard name file instead of renaming it; default: --no-link."""
    maxscore: float
    """Maximum normalized Levenshtein distance of recognizable extracted text lines."""
    outdir: Path | None
    """Output directory, default: directory of PG&E .pdf bill."""
    pages: int
    """Two single-digit page numbers, *i* is the *Details of PG&E
    Electric Delivery Charges* page number and *j* is the *Details of CleanPowerSF
    Electric Generation Charges* page number; default: 34."""
    print: bool
    """Print PG&E bill extracted text to `stdout`; default: --no-print."""
    quiet: bool
    """Do not print INFO, WARNING, ERROR, or CRITICAL messages to `stderr`;
    default --no-quiet."""
    version: bool
    """Display the version number and exit."""
    billfiles: list[str]
    """List of PG&E PDF bill files to be processed.  *FILES* must have the format
    *nnnn*custbill*mmddyyyy*.pdf, where *nnnn* is the last four digits of the
    PG&E account number and *mmddyyyy* is the PG&E bill statement date."""

    args_dict: dict[str, Any]
    """Dictionary of command line options and arguments."""

    @classmethod
    def init(cls, script_name: str, version: str) -> None:
        """Parse command line options and arguments.

        Args:
            script_name (str): Name of the script being executed.
            version (str): Version of the script.

        Raises:
            ValueError: If no PG&E PDF bill files are specified.
            ValueError: Invalid --pages option.
        """
        parser = argparse.ArgumentParser(description='Generate EV charger bills')
        parser.add_argument(
            '-d',
            '--debug',
            action=argparse.BooleanOptionalAction,
            default=False,
            help='Log debug info',
        )
        parser.add_argument(
            '--link',
            action=argparse.BooleanOptionalAction,
            default=False,
            help=(
                'Link PDF bill input file to standard name file '
                'instead of renaming it; default: --no-link.'
            ),
        )
        parser.add_argument(
            '--maxscore',
            type=float,
            default=0.2,
            help='Maximum normalized Levenshtein distance of recognizable extracted text lines; '
            'default: 0.2',
        )
        parser.add_argument(
            '--outdir',
            metavar='DIRECTORY',
            type=Path,
            default=None,
            help='Output directory; default: directory of PG&E .pdf bill',
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
            help='Print PG&E bill extracted text to stdout',
        )
        parser.add_argument(
            '-q',
            '--quiet',
            action=argparse.BooleanOptionalAction,
            default=False,
            help='Do not print verbose output',
        )
        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'{script_name} {version}',
            default=False,
            help='Display the version number and exit',
        )
        parser.add_argument(
            'billfiles',
            metavar='FILES',
            type=str,
            nargs='*',
            help='PG&E .pdf bills to process',
        )

        if len(sys.argv) < 2:
            raise ValueError('No PG&E PDF bill files specified')

        # If args passed as list, e.g. ['-d', 'bill.pdf'], then parse_args(None)
        # to parse sys.argv[1:], else shlex.split(sys.argv[1]) and pass to
        # parse_args().
        arg_list = (
            None
            if len(sys.argv) > 2
            else shlex.split(sys.argv[1], posix=os.name != 'nt')  # Pass '\' if Windows
        )
        cls.args_dict = vars(parser.parse_args(arg_list))

        if cls.args_dict['outdir'] is not None:
            # ARGS.outdir is writeable absolute Path
            assert isinstance(cls.args_dict['outdir'], Path)
            cls.args_dict['outdir'] = writable_dir(cls.args_dict['outdir'])

        for var, value in cls.args_dict.items():
            setattr(cls, var, value)

        pge_page, cpsf_page = divmod(Args.pages, 10)
        """pge_page = page number of PG&E page, cpsf_page = page number of CPSF page."""
        if Args.pages > 99 or pge_page == 0 or cpsf_page == 0 or pge_page >= cpsf_page:
            raise ValueError(f'Invalid --pages option {Args.pages}')

    @classmethod
    def as_string(cls) -> str:
        """Return arguments as string."""
        return ', '.join([f'{var}={value}' for var, value in cls.args_dict.items()])


def file_path_generator(
    globs: list[str], pattern: Optional[str | list[str]] = "*", recursive: bool = True
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

    Raises
    ------
    ValueError           If file name does not match allowed patterns.
    FileNotFoundError    File not found or not accessible.
    """
    assert pattern is not None

    # Convert pattern to list[str]
    patterns = [pattern] if isinstance(pattern, str) else pattern

    def expand_glob(glob_pattern: str) -> Generator[Path, None, None]:
        """Expand a glob

        Parameters
        ----------
        glob_pattern : str
            A glob.

        Yields
        ------
        Generator[Path, None, None]
            File paths from expanded glob.

        Raises
        ------
        ValueError           If file name does not match allowed patterns.
        FileNotFoundError    File not found or not accessible.
        """

        for filename in (
            glob.iglob(glob_pattern, recursive=recursive)
            if glob.has_magic(glob_pattern)
            else [glob_pattern]
        ):
            path = Path(os.path.expanduser(os.path.expandvars(filename)))
            if not any(path.match(p) for p in patterns):
                raise ValueError(f'Invalid file name "{filename}"')
            if not path.is_file():
                raise FileNotFoundError(f'File not found or not accessible: "{filename}"')
            print(f'expand_glob({glob_pattern}) yielding "{path}"', file=sys.stderr)
            yield path

    for glob_pattern in globs:
        if glob_pattern == '-':
            logger.info('Reading FILES from stdin ...')
            print('Reading FILES from stdin ...', file=sys.stderr)
            for stdin_glob in sys.stdin.read().splitlines():
                yield from expand_glob(stdin_glob.strip())
            continue

        path = Path(os.path.expanduser(os.path.expandvars(glob_pattern)))
        if path.is_dir():
            for p in patterns:
                yield from expand_glob(str(path / p))
        else:
            yield from expand_glob(glob_pattern)


def pge_pdf_bill_paths(globs: list[str]) -> Generator[Path, None, None]:
    """Generate NNNNcustMMDDYYYY.pdf or
    xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.pdffiles from a list of files and/or
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

    bill_id_pat = '[0-9a-f]' * 8 + ('-' + '[0-9a-f]' * 4) * 3 + '-' + '[0-9a-f]' * 12 + '.pdf'

    for bill_path in file_path_generator(globs, ['????custbill????????.pdf', bill_id_pat]):
        yield bill_path.resolve()
