'''
Abstract base class definitions for extracting text from PG&E/CPSF BEV-1
searchable PDF bill.

'''

__author__ = 'Keith Gorlen'

import sys
import logging
from pathlib import Path
from abc import ABC, abstractmethod
from collections import namedtuple
import re
from itertools import zip_longest


SCRIPT_DIR: Path = Path(__file__).absolute().parent
"""Path to directory containing this Python script."""
sys.path.append(str(SCRIPT_DIR))
"""Allow evbilling CLI to import modules from script directory."""

# pylint: disable=wrong-import-position

from __init__ import __version__
from evargs import Args
from pdfplumber.page import Page
from rapidfuzz.distance.Levenshtein import normalized_distance

# pylint: enable=wrong-import-position

#
# Global constants
#

logger = logging.getLogger(f'evbilling.{__name__}')


BBox = namedtuple('BBox', 'left top right bottom')
"""pdfplumber bounding box."""

def bbox(left: float, top: float, right: float, bottom: float, points: bool = False) -> BBox:
    """Create pdfplumber bounding box.

    Parameters
    ----------
    left : float
        x-coordinate of block left edge
    top : float
        y-coordinate of block top edge
    right : float
        x-coordinate of block right edge
    bottom : float
        y-coordinate of block bottom edge
    points : bool, optional
        If True, coordinates are in points (1/72 inch), else inches; default: False


    Returns
    -------
    BBox
        pdfplumber bounding box
    
    Notes
    -----
    In pdfplumber, the origin (0, 0) is at the top-left corner of the page, with
    the x-axis extending to the right and the y-axis extending downward.

    Units are in float points, where 1 point is equal to 1/72 of an inch.
    """
    units = 1 if points else 72
    return BBox(left * units, top * units, right * units, bottom * units)


class PDFXtractr(ABC):
    """Abstract base class definitions for extracting text from PG&E/CPSF BEV-1
    searchable PDF bill.
    """

    counters = {
        # Number of lines corrected.
        'lines corrected': 0,
        # Number of lines with normalized Levenshtein distance > Args.maxscore
        # or no letters or slashes.
        'lines skipped': 0,
        # Total lines
        'lines total': 0,
    }
    """Counters for various statistics."""

    max_score: float = 0
    """Maximum normalized Levenshtein distance of lines corrected by fuzzy matching."""
    min_score: float = 9999
    """Minimum normalized Levenshtein distance > Args.maxscore of skipped lines."""
    min_score_line: str = ''
    """Skipped line with minimum normalized Levenshtein distance > Args.maxscore."""

    @classmethod
    def reset_counters(cls) -> None:
        """Reset counters."""
        for key in cls.counters:
            cls.counters[key] = 0

    def __init__(self) -> None:
        self.page_width: float
        """Page width in inches as measured in Photoshop."""
        self.page_height: float
        """Page height in inches as measured in Photoshop."""
        self.keywords: tuple[str, ...]
        """Keywords to test for searchable PDF bill."""
        self.bboxes: dict[str, BBox]
        """Parts of page to extract."""
        self.page_bbox_names: tuple[tuple[str, ...], ...]
        """page_bbox_names[page_num] = tuple(keys of bboxes on page_num)"""
        self.templates: dict[str, tuple[str, list[str], int]] = {}
        """templates[template] = (item_id: str, non_nums: list[str], num_count: int)"""

    def init_templates(self, line_item_templates: str) -> None:
        """Initialize templates with line items from expected_line_items.

        Parameters
        ----------
        line_items : str
            Correction patterns for line items in extracted text: ^ indicates digit,
            initial # indicates comment, initial + indicates continuation.
            Number of consecutive ^s is not significant.  Templates containing
            both constant digits and digit variables are not supported.
        """
        for template in line_item_templates.splitlines():
            if not template or template[0] == '#':
                # Skip blank lines and comments.
                continue

            if template[0:4] == '=== ':
                continue  # Section header or footer.

            item_id: str = ''.join(
                re.findall(r'[a-zA-Z/]+', template)
            )  # Include "/" for mm/dd/yyyy
            non_nums: list[str] = re.findall(r'[^^]+', template)
            if template[0] == '^':
                non_nums = [''] + non_nums

            num_count: int = len(
                re.findall(r'\^+', template)
            )  # Number of number parts expected in the line.

            self.templates[template] = (item_id, non_nums, num_count)

    @abstractmethod
    def auto_bboxes(self, pages: list[Page]) -> None:
        """Set bbox coordinates based on extracted text position.

        Parameters
        ----------
        pages : list[Pages]
            List of pdfplumber Page instances for the PDF bill.
        """
        return

    def correct_text(self, text: str) -> str:
        """
        Correct extracted text using fuzzy matching.

        Parameters
        -----------
        text : str
            The extracted text to correct.

        Returns
        --------
        str
            The corrected extracted text.

        Notes
        -----
        References:
        https://medium.com/codex/best-libraries-for-fuzzy-matching-in-python-cbb^e^ef^^dd
        """

        def correct_line(non_nums: list[str], line_nums: list[str]) -> str:
            """Correct a line of text.

            Parameters
            -----------
            non_nums : list[str]
                The expected non-numeric parts of the line.
            line_nums : list[str]
                The numeric parts actually found in the line.

            Returns
            --------
            str
                The corrected line of text.
            """
            return ''.join([s + n for s, n in zip_longest(non_nums, line_nums, fillvalue='')])

        corrected_text: list[str] = []
        """List of corrected lines."""
        last_line_numbers: list[str] = []
        """List to store the numeric parts of the previous line."""
        last_closest_key: str = ''
        """The closest template key found for the previous line."""

        for line in text.splitlines(keepends=True):
            line = line.strip()

            if not line:
                continue

            if len(line) >= 4 and line[0:4] == '=== ':
                # No need to correct lines that were not extracted.
                corrected_text.append(line)
                continue

            PDFXtractr.counters['lines total'] += 1

            corrected_line: str = line
            """Corrected line of text."""
            line_item_id: str = ''.join(re.findall(r'[a-zA-Z/]+', corrected_line))
            """"All the letters and "/"s in the line ("/"s included for mm/dd/yyyy dates)."""
            low_score: float = 9999  # Arbitrarily high score for normalized distance
            """Minimum number of changes required to transform extracted text to expected text."""
            closest_key: str = ''
            """Template key of closest matching line item."""

            if not line_item_id:
                logger.debug(f"Skipping line with no letters: {line}")
                PDFXtractr.counters['lines skipped'] += 1
                continue

            for key, (item_id, non_nums, num_count) in self.templates.items():
                score: float = normalized_distance(line_item_id, item_id)
                if score < low_score:
                    low_score = score
                    closest_key = key

            assert closest_key, 'No closest template key found'

            if low_score > Args.maxscore:  # Threshold for fuzzy matching
                logger.debug(f"Skipping line with score {low_score:.2f} > {Args.maxscore}: {line}")
                PDFXtractr.counters['lines skipped'] += 1
                if low_score < PDFXtractr.min_score:
                    PDFXtractr.min_score = low_score
                    PDFXtractr.min_score_line = line
                continue

            PDFXtractr.max_score = max(PDFXtractr.max_score, low_score)

            non_nums: list[str] = self.templates[closest_key][1]
            """Non-number parts in the closest key."""
            num_count: int = self.templates[closest_key][2]
            """Number of number parts expected in the line."""
            line_nums: list[str] = []
            """All the number parts in the line."""

            if num_count > 0:
                # Accept thousands separator commas in number parts
                line_nums: list[str] = re.findall(r'(\d+(?:,?\d{3})*)', corrected_line)
                corrected_line: str = correct_line(non_nums, line_nums)
            else:  # No variable numbers in the template
                corrected_line = closest_key

            # If the closest key is a continuation, append the current line to the
            # first non-number part of the last line, which handles the special case
            # of "Generation - Super Off Peak - <Summer | Winter>".
            #
            # Could generalize by +n at beginning, where n is index of non-number
            # part to append to.

            if closest_key[0] == '+':
                corrected_text.pop()
                non_nums: list[str] = (
                    [self.templates[last_closest_key][1][0] + non_nums[0][1:]]
                    + non_nums[1:]
                    + self.templates[last_closest_key][1][1:]
                )
                corrected_line = correct_line(
                    non_nums,
                    last_line_numbers + line_nums,
                )

            if corrected_line != line:
                logger.info(f'EXT:  {line}')
                ndist = f'{low_score:.2f}'[1:] if low_score < 1 else f'{low_score:.1f}'
                logger.info(f'{ndist}-> {corrected_line}')
                PDFXtractr.counters['lines corrected'] += 1

            corrected_text.append(corrected_line)
            last_line_numbers = line_nums
            last_closest_key = closest_key

        return '\n'.join(corrected_text) + '\n'
