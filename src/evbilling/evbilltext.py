'''
evbilltext -- Extract text from selected pages of the PG&E searchable PDF bill file.

References:
    https://pypi.org/project/pdfplumber/ -- Plumb a PDF for detailed information
    about each char, rectangle, and line.

'''

__author__ = 'Keith Gorlen'

import os
import sys
import logging
from pathlib import Path

SCRIPT_DIR: Path = Path(__file__).absolute().parent
"""Path to directory containing this Python script."""
sys.path.append(str(SCRIPT_DIR))
"""Allow evbilling CLI to import modules from script directory."""

# pylint: disable=wrong-import-position

from __init__ import __version__
from evargs import Args, pge_pdf_bill_paths
from evlogger import DATE_FMT, info_msg
from evfiles import EVFiles
from pdfxtractr import PDFXtractr, BBox
from pdfbev1 import PDFBEV1
import pdfplumber
from pdfplumber.pdf import PDF
from pdfplumber.page import Page

# pylint: enable=wrong-import-position

#
# Global constants
#

logger = logging.getLogger(f'evbilling.{__name__}')


def extract_text(
    xtr: PDFXtractr,
    page_nums: list[int],
    ev_files: EVFiles,
) -> list[str]:
    """Extract text from selected pages of the PDF bill file.

    Parameters
    ----------
    xtr: PDFXtractr
        The PDFXtractr instance for the PDF file.
    page_nums: list[int]
        List of page numbers from which to extract text.
    ev_files: EVFiles
        EVFiles instance

    Returns
    -------
    list[str].
        Extracted text from selected pages, one string per page.
    Raises
    ------
    ValueError
        Page number out of range 1 to number of pages in document.
    FileNotFoundError
        PDF is not searchable and OCR sidecar file not found.

    Notes
    -----
    PG&E bills prior to November 2025 were not searchable, and python-docTR was used to
    perform OCR on the bill pages.  OCR is unreliable, requiring auto-correction.

    See python-docTR OCR:
        https://mindee.github.io/doctr/latest/index.html
        https://mindee.github.io/doctr/latest/modules/io.html
        https://source.opennews.org/articles/our-search-best-ocr-tool-2023

    Later PG&E bills are searchable PDFs.  This function first checks for
    keywords on the first page to determine if the PDF is searchable. If not
    searchable, attempts to use OCR text from a -OCR.txt sidecar file.  If
    the sidecar file also doesn't exist, raises FileNotFoundError.

    Saves extracted text to -EXT.txt file for debugging.
    """

    bill_path: Path = ev_files.bill_path
    """Output subdirectory."""
    extracted_pages: list[str] = []
    """Text extracted from each page."""

    if 0 in page_nums:
        raise ValueError('Page number 0 out of range')

    logger.info(f'Extracting text from {bill_path} ...')
    pdf: PDF = pdfplumber.open(bill_path)

    if max(page_nums) > len(pdf.pages):
        raise ValueError(
            f'Page number(s) {", ".join(str(p) for p in page_nums if p > len(pdf.pages))} '
            f'out of range'
        )

    logger.info('Checking for searchable PDF ...')
    first_page_text: str = pdf.pages[page_nums[0] - 1].extract_text() or ''
    if any(keyword not in first_page_text for keyword in xtr.keywords):
        pdf.close()

        sidecar_path: Path = ev_files.outdir_path('-OCR.txt')
        logger.info(f'PDF is not searchable, checking for OCR sidecar file {sidecar_path} ...')
        try:
            with open(sidecar_path, encoding='utf-8') as ocrtextfile:
                logger.info(f'Reading OCR text from sidecar file {sidecar_path} ...')
                sidecar_text: str = ocrtextfile.read()
                info_msg(logger, f'Using OCR text from sidecar file {sidecar_path}.')
                return sidecar_text.split('\f')

        except IOError as err:
            raise FileNotFoundError(
                f'PDF is not searchable and sidecar file not found: {sidecar_path}'
            ) from err

    # Extract pages using pdfplumber

    pdf_pages: list[Page] = []
    for page_num in page_nums:
        logger.info(f'Extracting text from page {page_num} ...')
        pdf_pages.append(pdf.pages[page_num - 1])

    logger.info('Setting bbox coordinates from locations of key phrases ...')
    xtr.auto_bboxes(pdf_pages)

    logger.info('Assembling pages of text from bboxes ...')

    for page_num, page, bbox_names in zip(page_nums, pdf_pages, xtr.page_bbox_names):
        page_text: str = ''
        for bbox_name in bbox_names:
            page_text += f'=== Page {page_num} {bbox_name} ===\n'
            logger.info(f'Correcting extracted text from {bbox_name} on page {page_num} ...')
            try:
                bbox: BBox = xtr.bboxes[bbox_name]
                page_bbox: Page = page.within_bbox(bbox)
                bbox_text = page_bbox.extract_text()
                page_text += xtr.correct_text(bbox_text)
            except Exception as err:
                raise type(err)(
                    f"Error processing {bbox_name} on page {page_num} of file {bill_path}: {err}"
                ) from err
        extracted_pages.append(page_text)

    pdf.close()
    logger.info('Searchable PDF text extraction completed.')

    logger.info(
        f'Corrected lines max score: {xtr.max_score:.3f}, '
        f'skipped line min score: {xtr.min_score:.3f} for "{xtr.min_score_line}"'
    )

    ext_file: Path = ev_files.outdir_path('-EXT.txt')
    logger.info(f'Writing extracted text to {ext_file} ...')
    with open(ext_file, 'w', encoding='utf-8') as f:
        f.write('\f'.join(extracted_pages))

    return extracted_pages


def main(script_name: str) -> None:
    """Test text extraction from PG&E bill PDF files.

    Parameters
    ----------
    script_name : str
        Name of this script without .py extension.
    """
    Args.init(script_name, __version__)

    logger.info(f'{"=" * 60}')
    logger.info(f'{script_name} version {__version__} starting in {os.getcwd()} ...')
    logger.info(f'{script_name} arguments: {Args.as_string()}.')

    if Args.debug:
        logger.setLevel(logging.DEBUG)

    if Args.outdir is None:
        raise ValueError(
            'Output directory not specified; use --outdir <directory> to specify output directory.'
        )

    assert isinstance(Args.billfiles, list)
    for bill_path in pge_pdf_bill_paths(Args.billfiles):
        ev_files = EVFiles(bill_path)
        extract_text(PDFBEV1(), list(divmod(Args.pages, 10)), ev_files)

    # Log statistics

    info_msg(logger, 'Text extraction using pdfplumber completed:')

    for key, count in PDFXtractr.counters.items():
        info_msg(logger, f'{count:4d} {key}')
    info_msg(
        logger,
        f'{PDFXtractr.counters['lines corrected'] / PDFXtractr.counters['lines total']:.0%} '
        f'lines corrected',
    )
    info_msg(
        logger,
        f'Maximum normalized Levenshtein distance of lines corrected by fuzzy matching: '
        f'{PDFXtractr.max_score:.3f}',
    )
    info_msg(
        logger,
        f'Skipped line with minimum normalized Levenshtein distance ({PDFXtractr.min_score:.3f}): '
        f'"{PDFXtractr.min_score_line}"',
    )

    info_msg(logger, f'{script_name} finished.')
    logger.info(f'{"=" * 60}')
    logging.shutdown()
    sys.exit(0)


if __name__ == '__main__':
    from logging.handlers import RotatingFileHandler
    from evsettings import Config

    SCRIPT_NAME: str = Path(__file__).stem
    """Name of this script without .py extension."""
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

    try:
        main(SCRIPT_NAME)
    except Exception as msg:  # pylint: disable=broad-exception-caught
        """Log a CRITICAL message and sys.exit(1)."""
        logger.critical(f'{msg}; exiting.')
        logger.info(f'{"=" * 60}')
        logging.shutdown()
        sys.exit(1)
