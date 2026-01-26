'''
evbillocr -- Extract text from selected pages of the PDF bill file.

See https://mindee.github.io/doctr/latest/using_doctr/using_models.html#id2

Location detection model test results, January 2025:

Default det_arch = 'fast_base' fails on --pages 35 2318custbill07162024.pdf:
    Generation Generation - - Off On Peak Peak - - Winter Summer 0.000000 0.000000 kWh \
        kWh @ $0.0 $0.23725 08035 0.00 0.00

det_arch = 'db_resnet34' fails on --pages 35 2318custbill07162024.pdf:
    San Francisco Utility Users' Tax 7.500%)

det_arch = 'db_resnet50' fails on 2318custbill01082025:
    Overage Fees ) kW @ $2.48000 0.00
    Fix: Overage Fees 0

det_arch = 'db_mobilenet_v3_large' fails on 2318custbill11072024.pdf:
    Power Charge ndifference Adjustment

det_arch = 'linknet_resnet18' fails on 2318custbill08142024.pdf:
    Subscription Level (10kW/block) 10 blocks @ . 0000 month

det_arch = 'linknet_resnet34' fails on 2318custbill08142024.pdf:
    Generation Super Off Peak 2.977500 kWh @ 3 $0.06518 $0.19

det_arch = 'linknet_resnet50' fails on 2318custbill08142024.pdf:
    Overage Fees kW @ $2.48000 0.00
    Franchis e Fee Surcharge 0.01

det_arch = 'fast_tiny' fails on 2318custbill10072024.pdf:
    Subscription Level (10kW/block) 1 block @ 0.7333 month @ $ 12.41 $9.10
    Fix: replace $ <digit> with $<digit>
    10/01/2024 -  -1 10/31/2024

det_arch = 'fast_small' fails on 2318custbill11072024.pdf:
    10/01/2024 -  - 10 0/31/2024
    Peak 3.363000 kWh @ 3 $0.38372 1.29
    10/01/2024 -  - 1 0/31/2024
'''

__author__ = 'Keith Gorlen'

import sys
import logging
from pathlib import Path
import re
from collections import namedtuple
from typing import Any


SCRIPT_DIR: Path = Path(__file__).absolute().parent
"""Path to directory containing this Python script."""
sys.path.append(str(SCRIPT_DIR))
"""Allow evbilling CLI to import modules from script directory."""

# pylint: disable=wrong-import-position

from __init__ import __version__
from evargs import Args
import numpy as np

# pylint: enable=wrong-import-position

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

logger = logging.getLogger(f'evbilling.{__name__}')


def extract_text(bill_path: Path, out_subdir: Path) -> tuple[str, str]:
    """_summary_

    Parameters
    ----------
    bill_path : Path
        _description_
    out_subdir : Path
        _description_

    Returns
    -------
    tuple[str, str]
        _description_
    """
    """Extract text from selected pages of the PDF bill file.

    Parameters
    ----------
    bill_path : Path
        Path of PG&E bill PDF file.
    out_subdir : Path
        Path of output directory.

    Returns
    -------
    tuple(pge_page : str, cpsf_page : str).
        OCR text of the specified PDF bill.


    Raises
    ------
    LookupError
        Sidecar file not found
    ValueError
        Invalid --pages option
    ValueError
        Page number out of range
    ValueError
        Page n: ocr_predictor(resolve_blocks=False) returned n blocks
    LookupError
        ocr_predictor(resolve_blocks=False) returned no blocks
    Notes
    -----
    OCR text from a billfile-OCR.txt sidecar file is used if it exists. Correct
    OCR errors by manually editing the sidecar file and rerunning evbilling.py.

    """
    det_arch = 'db_resnet50'
    reco_arch = 'crnn_vgg16_bn'  # Default

    # Check for sidecar text file

    sidecar_path: Path = out_subdir.joinpath(bill_path.stem + '-OCR.txt')
    sidecar_text = None

    if not (Args.forceocr or Args.showocr):

        try:
            with open(sidecar_path, encoding='utf-8') as ocrtextfile:
                logger.info(f'Reading OCR text from sidecar file {sidecar_path} ...')
                sidecar_text = ocrtextfile.read()
                p0, p1 = sidecar_text.split('\f')
                return (p0, p1)

        except IOError as err:
            logger.debug(f'{err} in open({sidecar_path}), running OCR ...')

    if sidecar_text is None and Args.forceocr is False and Args.showocr is False:
        raise LookupError(f'{sidecar_path} sidecar file not found; --ocr required')

    # Parameters for PG&E bills

    ps_w: int = 2549  # page width in pixels as measured in Photoshop
    ps_h: int = 3218  # page height in pixels as measured in Photoshop
    # line_h = 9/ps_h               # minimum distance between lines as measured in Photoshop
    delta_y_threshold: float = (
        20 / ps_h
    )  # vertical distance threshold in pixels for words in the same line

    Point = namedtuple('Point', 'x y')

    class Geometry:
        """docTR block geometry.

        Notes
        -----
        In Python docTR, geometry coordinates are typically measured as
        normalized values relative to the dimensions of the image they are
        extracted from. This means that coordinates are expressed as fractions
        of the width and height of the image, ranging from 0 to 1. This approach
        allows the coordinates to be resolution-independent, making it easier to
        work with images of different sizes.

        """

        def __init__(self, tl: Point, br: Point) -> None:
            """Initialize block geometry instance.

            Parameters
            ----------
            tl : Point
                x-y coordinates of block top left
            br : Point
                x-y coordinates of block bottom right

            """
            self.tl = tl
            self.br = br

        def __str__(self) -> str:
            """Return block Geometry as string."""
            return f'tl=({self.tl.x:.4f},{self.tl.y:.4f}) br=({self.br.x:.4f},{self.br.y:.4f})'

    # Word = namedtuple('Word', 'value page geometry')

    # Parts of page to extract
    block_geometries = {
        # Top-right corner of the page
        'header': Geometry(tl=Point(1600 / ps_w, 0.0), br=Point(1.0, 300 / ps_h)),
        # Middle-left part of the page
        'details': Geometry(tl=Point(50 / ps_w, 350 / ps_h), br=Point(1600 / ps_w, 2450 / ps_h)),
        # Middle-right part of the page, overridden by --autoblock option
        'service info': Geometry(tl=Point(1600 / ps_w, 1150 / ps_h), br=Point(1.0, 1400 / ps_h)),
        # # Middle-right part of the page, bills before April 2024
        # 'service info': Geometry(tl=Point(1600/ps_w, 350/ps_h), br=Point(1.0, 1400/ps_h)),
        # Bottom-right part of the page
        'footer': Geometry(tl=Point(1600 / ps_w, 3000 / ps_h), br=Point(1.0, 1.0)),
    }

    # page_block_names[page_num] = tuple(keys of block_geometries on page_num)
    page_block_names: tuple[tuple[str, ...], ...] = (
        ('header', 'details', 'service info', 'footer'),  # PG&E page
        ('header', 'details', 'footer'),  # CleanPowerSF page
    )

    pge_page, cpsf_page = divmod(Args.pages, 10)
    if Args.pages > 99 or pge_page == 0 or cpsf_page == 0 or pge_page >= cpsf_page:
        raise ValueError(f'Invalid --pages option {Args.pages}')

    text = ''  # extracted text
    max_dy = 0  # maximum delta-y of line y coordinates
    max_dy_text = ''  # text of line with maximum delta-y

    logger.info(f'Running OCR on {bill_path} ...')

    logger.info('Importing doctr.io ...')
    from doctr.io import DocumentFile  # pylint: disable=import-outside-toplevel

    logger.info('Importing doctr.models ...')
    from doctr.models import ocr_predictor  # pylint: disable=import-outside-toplevel

    logger.info(f'Python DocTR detection model: {det_arch}, recognition model: {reco_arch}')

    # pylint: disable=possibly-used-before-assignment (E0606)
    model = ocr_predictor(det_arch=det_arch, pretrained=True, resolve_blocks=False)
    doc: list[np.ndarray] = DocumentFile.from_pdf(bill_path)
    # pylint: enable=possibly-used-before-assignment (E0606)

    if cpsf_page > len(doc):
        raise ValueError(f'Page number {cpsf_page} out of range')

    ocr_result = model([doc[page - 1] for page in (pge_page, cpsf_page)])

    if Args.showocr:
        ocr_result.show()  # Show detected locations of words on page

    # Determine text block geometries from locations of key phrases

    if Args.autoblock:

        for line in ocr_result.pages[0].blocks[0].lines:  # Lines on PG&E Details page
            s = ' '.join(word.value for word in line.words)
            if re.search(r'Service Information', s):
                default_geometry = block_geometries['service info']
                logger.info(f'Service Information block default location {default_geometry}.')
                line_geometry = Geometry(tl=Point(*line.geometry[0]), br=Point(*line.geometry[1]))
                block_h = default_geometry.br.y - default_geometry.tl.y
                block_geometries['service info'] = Geometry(
                    tl=Point(default_geometry.tl.x, line_geometry.tl.y),
                    br=Point(1.0, line_geometry.br.y + block_h),
                )
                logger.info(
                    f'Service Information block location set to {block_geometries["service info"]}.'
                )

    # Assemble the words in blocks into lines

    for page_num, page, block_names in zip(
        (pge_page, cpsf_page), ocr_result.pages, page_block_names
    ):

        # Resolve_blocks=False should return one block
        if len(page.blocks) > 1:
            raise ValueError(
                f'Page {page_num}: ocr_predictor(resolve_blocks=False) '
                f'returned {len(page.blocks)} blocks'
            )
        elif len(page.blocks) == 0:
            raise LookupError(
                f'ocr_predictor(resolve_blocks=False) '
                f'returned no blocks; check page {page_num} '
                f'of bill file {Args.bill_path}'
            )

        for block_name in block_names:
            block = block_geometries[block_name]
            text += f"=== Page {page_num} {block_name} ===\n"

            # words = list of all words in a block on the page sorted by y coordinate
            words: list[Any] = sorted(
                (
                    word
                    for line in page.blocks[0].lines
                    for word in line.words
                    if (
                        block.tl.x <= word.geometry[0][0] <= block.br.x
                        and block.tl.y <= word.geometry[0][1] <= block.br.y
                        and block.tl.x <= word.geometry[1][0] <= block.br.x
                        and block.tl.y <= word.geometry[1][1] <= block.br.y
                    )
                ),
                key=lambda word: word.geometry[0][1],
            )

            if len(words) == 0:
                text += '<NONE>\n'
                continue

            # Reorganize the words in a block into lines

            current_words = [words[0]]
            for word in words[1:] + [None]:
                # Check if the current word is part of the last line vertically
                if (
                    word is not None
                    and abs(word.geometry[0][1] - current_words[-1].geometry[0][1])
                    < delta_y_threshold
                ):
                    current_words.append(word)  # Extend current line
                else:  # End of a line
                    ordered_words = sorted(current_words, key=lambda w: w.geometry[0][0])
                    linetext = f'{" ".join(word.value for word in ordered_words)}'
                    text += linetext + '\n'
                    current_words = [word]  # Start a new line

                    if len(ordered_words) > 1:  # Track the max delta-y seen in all lines
                        word_y = [word.geometry[0][1] for word in ordered_words]
                        dy = max(abs(ay - by) for ay, by in zip(word_y, word_y[1:]))
                        if dy > max_dy:
                            max_dy, max_dy_text = dy, linetext

        text += '\f'  # Insert form-feed page separator

    text = text[:-1]  # text without trailing form-feed

    logger.info(
        f'Delta-y threshold: {delta_y_threshold:0.5f}, '
        f'max delta-y: {max_dy:0.5f} for "{max_dy_text}".'
    )

    logger.debug(f'Uncorrected OCR text:\n{text}')

    # Fix "obvious" OCR errors

    if Args.fixocr:
        # Remove space after decimal point: ddd. ddd -> ddd.ddd
        text = re.sub(r'(\d+\.)\s*(\d+)', r'\1\2', text)
        # Insert missing '@' between units and rate, e.g. kWh $ -> kWh @ $
        text = re.sub(r'(blocks|month|kW|kWh)\s+(\$?\d+)', r'\1 @ \2', text)
        # Correct '@' identified as 'a' or ')' between units and rate, e.g.: kWh a $ -> kWh @ $
        text = re.sub(r'(blocks|month|kW|kWh)\s[^@]\s(\$?\d+)', r'\1 @ \2', text)
        # Insert missing spaces around '@' between units and rate, e.g.: month @$
        text = re.sub(r'(blocks|month|kW|kWh)\s?@\s?(\$?\d+)', r'\1 @ \2', text)
        # Insert missing space after '-mm/dd/yyy': -10/09/2023 -> - 10/09/2023
        text = re.sub(rf'-{RE_DATE}', r'- \1', text)
        # Change date period separator to '-': mm/dd/yyy = mm/dd/yyyy -> mm/dd/yyy - mm/dd/yyyy
        text = re.sub(rf'{RE_PERIOD}', r'\1 - \2', text)
        # Insert missing minus after 'Credit ': Credit 234.28 -> Credit -234.28
        text = re.sub(r'Credit\s(\d+)', r'Credit -\1', text)
        # Insert missing '()' around 'Level 10kW/block'
        text = re.sub(r'Level \(?10kW/block\)?', 'Level (10kW/block)', text)
        # Change ' ) ' to ' 0 '
        text = re.sub(
            rf'Overage Fees [^ ]+ kW @ {RE_RATES} 0.00', r'Overage Fees 0 kW @ $\1 0.00', text
        )

        # Correct location detection errors

        # Remove space and repeated character after word: Gene eration -> Generation
        text = re.sub(r'([A-Z][a-z]*)([a-z]) \2', r'\1\2', text)
        # Remove space and repeated digit after decimal point: 7.3 31 -> 7.31
        text = re.sub(r'(\d\.)(\d) \2', r'\1\2', text)
        # Remove space and repeated decimal point after decimal point: 104. .46 -> 104.46
        text = re.sub(r'(\d\.) \.(\d)', r'\1\2', text)
        # Remove 'l' at end of word: Franchisel Fee -> Franchise Fee
        text = re.sub(r'\bFranchise\w+\b', r'Franchise', text)
        # Remove space after $
        text = re.sub(r'\$ (\d)', r'$\1', text)
        # CTax -> C Tax
        text = re.sub(r'\bCTax\b', r'C Tax', text)

    logger.info(f'Writing OCR text to sidecar file {sidecar_path} ...')

    with open(sidecar_path, 'w', encoding='utf-8') as ocrtextfile:
        ocrtextfile.write(text)

    p0, p1 = text.split('\f')
    return (p0, p1)
