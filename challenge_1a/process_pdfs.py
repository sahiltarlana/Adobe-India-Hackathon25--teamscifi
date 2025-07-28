from pathlib import Path
import json
import re
from collections import Counter
from typing import Dict, List, Tuple, Optional
import numpy as np
import pdfplumber
import fitz
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams, LTTextBox, LTTextLine, LTChar
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator
from pdfminer.pdfpage import PDFPage

class HybridPDFHeadingExtractor:
    """
    Uses multiple libraries (pdfplumber, PyMuPDF) to cross-validate and extract headings with maximum accuracy.
    """

    def __init__(self):
        self.heading_patterns = [
            r'^(Chapter\s+\d+|CHAPTER\s+\d+)',
            r'^(\d+\.(\d+\.)*\s+[A-Z])',
            r'^([A-Z][A-Z\s]{8,}$)',
            r'^([A-Z][a-z]+(\s+[A-Z][a-z]+)*):?\s*$',
            r'^(Appendix\s+[A-Z]:?)',
            r'^([IVX]+\.\s+[A-Z])',  # Roman numerals
        ]

    def extract_with_pdfplumber(self, pdf_path: str) -> Dict:
        """Extract text blocks with precise positioning using pdfplumber."""
        results = {"pages": [], "fonts": []}
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_data = []
                    chars = page.chars
                    text_blocks = self._group_chars_by_proximity(chars)
                    for block in text_blocks:
                        if len(block['text'].strip()) > 0:
                            page_data.append({
                                'text': block['text'].strip(),
                                'font': block['font'],
                                'size': block['size'],
                                'bold': block['bold'],
                                'page': page_num + 1,
                                'bbox': block['bbox'],
                                'x0': block['x0'],
                                'top': block['top']
                            })
                            results["fonts"].append((block['font'], block['size'], block['bold']))
                    results["pages"].append(page_data)
        except Exception as e:
            print(f"Error in pdfplumber extraction for {pdf_path}: {str(e)}")
        return results

    def _group_chars_by_proximity(self, chars: List) -> List[Dict]:
        """Group characters into text blocks based on proximity and formatting."""
        if not chars:
            return []
        sorted_chars = sorted(chars, key=lambda c: (c['top'], c['x0']))
        blocks = []
        current_block = {
            'text': '',
            'font': sorted_chars[0]['fontname'],
            'size': sorted_chars[0]['size'],
            'bold': 'Bold' in sorted_chars[0]['fontname'],
            'x0': sorted_chars[0]['x0'],
            'top': sorted_chars[0]['top'],
            'bbox': [sorted_chars[0]['x0'], sorted_chars[0]['top'], sorted_chars[0]['x1'], sorted_chars[0]['bottom']]
        }
        for i, char in enumerate(sorted_chars):
            if i == 0:
                current_block['text'] = char['text']
                continue
            same_line = abs(char['top'] - current_block['top']) < 3
            same_font = char['fontname'] == current_block['font']
            same_size = abs(char['size'] - current_block['size']) < 0.5
            close_horizontal = char['x0'] - current_block['bbox'][2] < 10
            if same_line and same_font and same_size and close_horizontal:
                current_block['text'] += char['text']
                current_block['bbox'][2] = char['x1']
                current_block['bbox'][3] = max(current_block['bbox'][3], char['bottom'])
            else:
                if current_block['text'].strip():
                    blocks.append(current_block)
                current_block = {
                    'text': char['text'],
                    'font': char['fontname'],
                    'size': char['size'],
                    'bold': 'Bold' in char['fontname'],
                    'x0': char['x0'],
                    'top': char['top'],
                    'bbox': [char['x0'], char['top'], char['x1'], char['bottom']]
                }
        if current_block['text'].strip():
            blocks.append(current_block)
        return blocks

    def extract_with_pymupdf(self, pdf_path: str) -> Dict:
        """Extract text blocks with font analysis using PyMuPDF."""
        results = {"pages": [], "fonts": []}
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                blocks = page.get_text("dict")
                page_data = []
                for block in blocks["blocks"]:
                    if "lines" in block:
                        for line in block["lines"]:
                            line_text = ""
                            line_font = None
                            line_size = 0
                            line_flags = 0
                            for span in line["spans"]:
                                line_text += span["text"]
                                if line_font is None:
                                    line_font = span["font"]
                                    line_size = span["size"]
                                    line_flags = span["flags"]
                            if line_text.strip():
                                page_data.append({
                                    'text': line_text.strip(),
                                    'font': line_font,
                                    'size': round(line_size, 1),
                                    'bold': bool(line_flags & 2**4),
                                    'page': page_num + 1,
                                    'bbox': line["bbox"]
                                })
                                results["fonts"].append((line_font, line_size, bool(line_flags & 2**4)))
                results["pages"].append(page_data)
            doc.close()
        except Exception as e:
            print(f"Error in PyMuPDF extraction for {pdf_path}: {str(e)}")
        return results

    def cross_validate_headings(self, pdfplumber_data: Dict, pymupdf_data: Dict) -> List[Dict]:
        """Cross-validate headings between pdfplumber and PyMuPDF extractions."""
        hierarchy1, body_size1 = self._analyze_font_hierarchy(pdfplumber_data["fonts"])
        hierarchy2, body_size2 = self._analyze_font_hierarchy(pymupdf_data["fonts"])
        consensus_headings = []
        for page_num in range(min(len(pdfplumber_data["pages"]), len(pymupdf_data["pages"]))):
            page1 = pdfplumber_data["pages"][page_num]
            page2 = pymupdf_data["pages"][page_num]
            for item1 in page1:
                text1 = item1["text"].strip()
                for item2 in page2:
                    text2 = item2["text"].strip()
                    if self._texts_similar(text1, text2):
                        heading_level1 = self._classify_heading(item1, hierarchy1, body_size1)
                        heading_level2 = self._classify_heading(item2, hierarchy2, body_size2)
                        if heading_level1 and heading_level2:
                            final_level = self._get_conservative_level(heading_level1, heading_level2)
                            consensus_headings.append({
                                "level": final_level,
                                "text": text1,
                                "page": page_num + 1,
                                "confidence": "high"
                            })
                        elif heading_level1 or heading_level2:
                            level = heading_level1 or heading_level2
                            if self._passes_strict_heading_tests(text1):
                                consensus_headings.append({
                                    "level": level,
                                    "text": text1,
                                    "page": page_num + 1,
                                    "confidence": "medium"
                                })
        seen = set()
        unique_headings = [h for h in consensus_headings if not (h["text"] in seen or seen.add(h["text"]))]
        return sorted(unique_headings, key=lambda x: (x["page"], x["text"]))

    def _texts_similar(self, text1: str, text2: str) -> bool:
        """Check if two texts are similar enough to be considered the same."""
        text1_clean = re.sub(r'\s+', ' ', text1.lower().strip())
        text2_clean = re.sub(r'\s+', ' ', text2.lower().strip())
        if text1_clean == text2_clean:
            return True
        if len(text1_clean) > 5 and len(text2_clean) > 5:
            return text1_clean in text2_clean or text2_clean in text1_clean
        return False

    def _analyze_font_hierarchy(self, fonts: List[Tuple]) -> Tuple[Dict, float]:
        """Analyze font patterns to determine heading hierarchy."""
        font_counter = Counter(fonts)
        body_font = font_counter.most_common(1)[0][0]
        body_size = body_font[1]
        hierarchy = {}
        sizes = [f[1] for f in fonts if f[1] > 0]  # Avoid invalid sizes
        if not sizes:
            return hierarchy, body_size
        size_percentiles = {
            95: np.percentile(sizes, 95),
            85: np.percentile(sizes, 85),
            75: np.percentile(sizes, 75),
            65: np.percentile(sizes, 65)
        }
        for font, size, bold in set(fonts):
            if size >= size_percentiles[95]:
                hierarchy[(font, size, bold)] = "H1"
            elif size >= size_percentiles[85] or (bold and size >= body_size * 1.1):
                hierarchy[(font, size, bold)] = "H2"
            elif size >= size_percentiles[75] or (bold and size >= body_size):
                hierarchy[(font, size, bold)] = "H3"
            elif size >= size_percentiles[65] or bold:
                hierarchy[(font, size, bold)] = "H4"
            else:
                hierarchy[(font, size, bold)] = "body"
        return hierarchy, body_size

    def _classify_heading(self, item: Dict, hierarchy: Dict, body_size: float) -> Optional[str]:
        """Classify if an item is a heading."""
        text = item["text"].strip()
        if len(text) < 3 or len(text) > 200:
            return None
        font_key = (item["font"], item["size"], item["bold"])
        font_level = hierarchy.get(font_key, "body")
        if font_level == "body" and item["size"] <= body_size * 1.02:
            return None
        for pattern in self.heading_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return font_level if font_level != "body" else "H1"
        if font_level in ["H1", "H2", "H3", "H4"]:
            if self._looks_like_heading(text):
                return font_level
        return None

    def _looks_like_heading(self, text: str) -> bool:
        """Advanced heading detection logic."""
        if text.istitle() or text.isupper():
            return True
        if text[0].isupper() and len(text.split()) <= 15:
            return True
        if re.match(r'^\d+\.', text):
            return True
        return False

    def _passes_strict_heading_tests(self, text: str) -> bool:
        """Strict tests for heading candidacy."""
        if not text or not text[0].isupper():
            return False
        if len(text) < 5 or len(text) > 150:
            return False
        special_chars = sum(1 for c in text if not c.isalnum() and c not in ' -.,:()')
        if special_chars > len(text) * 0.3:
            return False
        return True

    def _get_conservative_level(self, level1: str, level2: str) -> str:
        """Get the more conservative (higher) heading level."""
        level_order = {"H1": 1, "H2": 2, "H3": 3, "H4": 4}
        if level1 in level_order and level2 in level_order:
            return level1 if level_order[level1] <= level_order[level2] else level2
        return level1 or level2

    def extract_title_advanced(self, pdfplumber_data: Dict, pymupdf_data: Dict) -> str:
        """Extract title using both libraries."""
        candidates = []
        for data_source in [pdfplumber_data, pymupdf_data]:
            if data_source["pages"]:
                first_page = data_source["pages"][0]
                for item in first_page[:10]:
                    text = item["text"].strip()
                    if 10 <= len(text) <= 200 and item["size"] >= 14:
                        candidates.append((text, item["size"]))
        if candidates:
            title = max(candidates, key=lambda x: x[1])[0]
            title = re.sub(r'\s+', ' ', title).strip()
            return title
        return "Untitled Document"

    def process_pdf(self, pdf_path: str) -> Dict:
        """Process a single PDF to extract title and headings."""
        pdfplumber_data = self.extract_with_pdfplumber(pdf_path)
        pymupdf_data = self.extract_with_pymupdf(pdf_path)
        headings = self.cross_validate_headings(pdfplumber_data, pymupdf_data)
        title = self.extract_title_advanced(pdfplumber_data, pymupdf_data)
        return {
            "title": title,
            "outline": [
                {"level": h["level"], "text": h["text"], "page": h["page"]}
                for h in headings if h["level"] in ["H1", "H2", "H3"]
            ]
        }

def process_pdfs():
    """
    Process all PDFs in /app/input and generate JSON files in /app/output.
    """
    input_dir = Path("/app/input")
    output_dir = Path("/app/output")
    output_dir.mkdir(exist_ok=True)
    extractor = HybridPDFHeadingExtractor()
    for pdf_file in input_dir.glob("*.pdf"):
        try:
            print(f"Processing {pdf_file.name}...")
            result = extractor.process_pdf(str(pdf_file))
            output_file = output_dir / f"{pdf_file.stem}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"Generated {output_file.name}")
        except Exception as e:
            print(f"Error processing {pdf_file.name}: {str(e)}")

if __name__ == "__main__":
    process_pdfs()