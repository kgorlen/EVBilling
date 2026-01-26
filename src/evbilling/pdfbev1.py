'''
pdfbev1 -- Definitions for extracting text from PG&E/CPSF BEV-1 searchable PDF bill.
'''

__author__ = 'Keith Gorlen'

import sys
import logging
from pathlib import Path


SCRIPT_DIR: Path = Path(__file__).absolute().parent
"""Path to directory containing this Python script."""
sys.path.append(str(SCRIPT_DIR))
"""Allow evbilling CLI to import modules from script directory."""

# pylint: disable=wrong-import-position

from __init__ import __version__
from pdfplumber.page import Page
from pdfxtractr import PDFXtractr, bbox

# pylint: enable=wrong-import-position

#
# Global constants
#

logger = logging.getLogger(f'evbilling.{__name__}')


class PDFBEV1(PDFXtractr):
    """Definitions for extracting text from PG&E/CPSF BEV-1 searchable PDF bill."""

    line_item_templates: str = """
# PG&E line items:
=== Page ^ header ===
Account No: ^^^^^^^^^^-^
Statement Date: ^^/^^/^^^^
Due Date: ^^/^^/^^^^
=== Page ^ details ===
Details of PG&E Electric Delivery Charges
^^/^^/^^^^ - ^^/^^/^^^^ (^^ billing days)
^^/^^/^^^^ to ^^/^^/^^^^ (^^ billing days)
Service Agreement ID: ^^^^^^^^^^
Rate Schedule: BEV1 Bus Low Use EV
^^/^^/^^^^ - ^^/^^/^^^^
^^/^^/^^^^ to ^^/^^/^^^^
Subscription Charges
Subscription Level (^^kW/block) ^ block @ ^.^^^^ month @ $^^.^^ $^^.^^
Subscription Level (^^kW/block) ^ blocks @ ^.^^^^ month @ $^^.^^ $^^.^^
Overage Fees ^ kW @ $^.^^^^^ ^^.^^
Energy Charges
Peak ^^.^^^^^^ kWh @ $^.^^^^^ ^^.^^
Off Peak ^^^.^^^^^^ kWh @ $^.^^^^^ ^^.^^
Super Off Peak ^^.^^^^^^ kWh @ $^.^^^^^ ^^.^^
Generation Credit -^^.^^
Power Charge Indifference Adjustment ^^.^^
Franchise Fee Surcharge ^^.^^
San Francisco Utility Users' Tax (^.^^^%) ^^.^^
SF Prop C Tax Surcharge ^^.^^
Total PG&E Electric Delivery Charges $^^.^^
^^^^ Vintaged Power Charge Indifference Adjustment
=== Page ^ service info ===
Service Information
Meter # ^^^^^^^^^^
Total Usage ^^^.^^^^^^ kWh
Rotating Outage Block ^^
=== Page ^ footer ===
Page ^ of ^

# CleanPowerSF line items:
=== Page ^ header ===
Account No: ^^^^^^^^^^-^
Statement Date: ^^/^^/^^^^
Due Date: ^^/^^/^^^^
=== Page ^ details ===
Details of CleanPowerSF Electric Generation Charges
Details of CleanPowerSF Electric Generation 
+Charges
^^/^^/^^^^ - ^^/^^/^^^^ (^^ billing days)
^^/^^/^^^^ to ^^/^^/^^^^ (^^ billing days)
Service Agreement ID: ^^^^^^^^^^ ESP Customer Number: ^^^^^^^^^^
^^/^^/^^^^ - ^^/^^/^^^^
^^/^^/^^^^ to ^^/^^/^^^^
^^/^^/^^^^
Rate Schedule: B-EV-1
Generation - Super Off Peak - ^^.^^^^^^ kWh @ $^.^^^^^ $^^.^^
+Summer 
Generation - Super Off Peak - Summer ^^.^^^^^^ kWh @ $^.^^^^^ $^^.^^
Generation - Off Peak - Summer ^^^.^^^^^^ kWh @ $^.^^^^^ $^^.^^
Generation - On Peak - Summer ^^.^^^^^^ kWh @ $^.^^^^^ $^^.^^
Generation - Super Off Peak - ^^.^^^^^^ kWh @ $^.^^^^^ $^^.^^
+Winter 
Generation - Super Off Peak - Winter ^^.^^^^^^ kWh @ $^.^^^^^ $^^.^^
Generation - Off Peak - Winter ^^^.^^^^^^ kWh @ $^.^^^^^ $^^.^^
Generation - On Peak - Winter ^^.^^^^^^ kWh @ $^.^^^^^ $^^.^^
Net Charges ^^.^^
Local Utility Users Tax ^^.^^
Energy Commission Surcharge ^^.^^
Total CleanPowerSF Electric 
+Generation Charges $^^.^^
=== Page ^ footer ===
Page ^ of ^
"""
    """
    Correction patterns for line items in extracted text: ^ indicates digit,
    initial # indicates comment, initial + indicates continuation.  Number of
    consecutive ^s is not significant.
    """

    def __init__(self) -> None:
        super().__init__()
        """Initialize PDFBEV1 instance."""
        self.page_width = 8.5
        """Page width in inches as measured in Photoshop."""
        self.page_height = 11
        """Page height in inches as measured in Photoshop."""
        self.keywords = ('Account', 'Statement', 'Due', 'Date')
        self.bboxes = {
            # Top-right corner of the page:
            'header': bbox(5 + 3 / 8, 0, self.page_width, 1),
            # Middle-left part of the page:
            'details': bbox(0, 1, 5 + 3 / 8, 8 + 1 / 4),
            # Middle-right part of the page, overridden by auto_bbox():
            'service info': bbox(5 + 3 / 8, 1, self.page_width, 8 + 1 / 4),
            # Bottom-right part of the page:
            'footer': bbox(5 + 3 / 8, 10 + 1 / 4, self.page_width, self.page_height),
            }
        self.page_bbox_names: tuple[tuple[str, ...], ...] = (
            ('header', 'details', 'service info', 'footer'),  # PG&E page
            ('header', 'details', 'footer'),  # CleanPowerSF page
        )
        """page_bbox_names[page_num] = tuple(keys of bboxes on page_num)"""

        # Initialize checker with line items from expected_line_items.
        self.init_templates(PDFBEV1.line_item_templates)

    def auto_bboxes(self, pages: list[Page]) -> None:
        """Set block geometries based on extracted text position.

        Parameters
        ----------
        pages : list[Pages]
            List of pdfplumber Page instances for the PDF bill.

        Raises
        --------
        LookupError
            If the Service Information block is not found.
        """
        for page in pages:
            service_info = page.within_bbox(self.bboxes['service info'])
            lines = service_info.extract_text_lines(return_chars=False)
            for line in lines:
                if 'Service Information' in line['text']:
                    default = self.bboxes['service info']
                    self.bboxes['service info'] = bbox(
                        default.left, line['top'] - 2, default.right, default.bottom, points=True
                    )
                    return

        raise LookupError('Service Information block not found for auto_bboxes().')
