from app.processors.base import BaseFileProcessor
from app.db.collections.files import files_collection
from app.utils.file import extract_text_from_pdf
from bson import ObjectId
import re
from collections import defaultdict
from pathlib import Path

import fitz  # PyMuPDF

# Visit Date pattern (legacy / alternate): "Visit Date: Dec 26, 2025"
VISIT_DATE_PATTERN = re.compile(
    r"Visit\s*Date\s*:?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    re.IGNORECASE,
)
# Document format: "Visit:\n02/10/2020" and "Visit #:\n31" or "visti:#\n31"
VISIT_DATE_INLINE_PATTERN = re.compile(
    r"Visit\s*:\s*(\d{1,2}/\d{1,2}/\d{2,4})",
    re.IGNORECASE,
)
# Multiple patterns for visit number (try in order); "Visit 17", "Visit # 17", "Visit #: 17", "visti:# 31"
# (?!\s*/\d) avoids matching "02" in "Visit: 02/10/2020"
VISIT_NUMBER_PATTERNS = [
    re.compile(r"(?:Visit|visti)\s*#\s*:?\s*(\d+)(?!\s*/\d)", re.IGNORECASE),
    re.compile(r"(?:Visit|visti)\s*#?\s*:?\s*(\d+)(?!\s*/\d)", re.IGNORECASE),
    re.compile(r"(?:Visit|visti)\s+(\d+)(?!\s*/\d)", re.IGNORECASE),
]
# Page number on page: "Page 2", "Page #: 2", "Page: 2"
PAGE_NUMBER_PATTERNS = [
    re.compile(r"Page\s*#\s*:?\s*(\d+)", re.IGNORECASE),
    re.compile(r"Page\s*:?\s*(\d+)", re.IGNORECASE),
]
# For testing: only save this many page images (set to None to save all)
MAX_PAGES_TO_SAVE = 4


def _find_visit_number_in_text(text: str) -> int | None:
    """Try all visit number patterns; return first match or None."""
    for pat in VISIT_NUMBER_PATTERNS:
        m = pat.search(text)
        if m:
            return int(m.group(1))
    return None


def _find_page_number_in_text(text: str) -> int | None:
    """Try all page number patterns; return first match or None."""
    for pat in PAGE_NUMBER_PATTERNS:
        m = pat.search(text)
        if m:
            return int(m.group(1))
    return None


def _visit_date_to_iso(date_str: str) -> str:
    """Convert 'Dec 26, 2025' or '12/26/2025' to ISO date '2025-12-26'."""
    from datetime import datetime
    s = date_str.strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s  # return as-is if no parse


class PDFTextProcessor(BaseFileProcessor):

    def clean_text(self, raw_text: str) -> str:
        lines = raw_text.split("\n")
        cleaned = []
        for line in lines:
            line = line.strip()
            # remove page headers
            if line.startswith("Explanation Of Benefits"):
                continue
            if re.search(r"Page:\s*\d+\s*of\s*\d+", line):
                continue
           
            if line:
                cleaned.append(line)
        return cleaned
        
    def parse_eob(self, lines: list[str]) -> dict:
        patients = []
        current_patient = None

        for line in lines:

            # ----------------------------
            # 1️⃣ Detect New Patient
            # ----------------------------
            patient_match = re.match(r"Patient Name:\s*(.+)", line)
            if patient_match:
                # save previous
                if current_patient:
                    patients.append(current_patient)

                current_patient = {
                    "patient_name": patient_match.group(1).strip(),
                    "claim_id": None,
                    "services_by_dos": defaultdict(list),
                    "totals": {}
                }
                continue

            if not current_patient:
                continue

            # ----------------------------
            # 2️⃣ Detect Claim ID
            # ----------------------------
            claim_match = re.search(r"Claim ID:\s*(\S+)", line)
            if claim_match:
                current_patient["claim_id"] = claim_match.group(1)
                continue

            # ----------------------------
            # 3️⃣ Detect Service Line (Starts with Date)
            # Supports: 02/02/26 or 02/02/2026, then code, units, amounts
            # Example: 02/02/26 11 97140GP 1.0 116.00 94.64
            # Example: 02/02/2026 97140GP 1.0 116.00 94.64
            # ----------------------------
            date_match = re.match(r"(\d{1,2}/\d{1,2}/\d{2,4})\s+(.+)", line)
            if date_match:
                dos = date_match.group(1)
                rest = date_match.group(2)
                parts = rest.split()
                # Need at least: code, units, submitted, negotiated (4+ tokens)
                if len(parts) >= 4:
                    try:
                        # Try layout: [maybe_line_no?] code units submitted negotiated ...
                        def parse_num(s: str) -> float:
                            return float(s.replace(",", ""))

                        if len(parts) >= 5 and parts[0].replace(".", "").isdigit() and not parts[1].replace(".", "").replace("-", "").isdigit():
                            # e.g. 11 97140GP 1.0 116.00 94.64
                            code = parts[1]
                            units = parse_num(parts[2])
                            submitted = parse_num(parts[3])
                            negotiated = parse_num(parts[4])
                        elif parts[1].replace(".", "").isdigit():
                            # e.g. 97140GP 1.0 116.00 94.64
                            code = parts[0]
                            units = parse_num(parts[1])
                            submitted = parse_num(parts[2])
                            negotiated = parse_num(parts[3])
                        else:
                            code = parts[0]
                            units = parse_num(parts[1])
                            submitted = parse_num(parts[2])
                            negotiated = parse_num(parts[3])

                        service = {
                            "code": code,
                            "units": units,
                            "submitted": submitted,
                            "negotiated": negotiated,
                        }
                        current_patient["services_by_dos"][dos].append(service)
                    except (ValueError, IndexError):
                        pass

            # ----------------------------
            # 4️⃣ Detect Issued Amount
            # ----------------------------
            issued_match = re.search(r"ISSUED AMT:\s*\$?([\d,]+\.\d+)", line)
            if issued_match:
                amt = issued_match.group(1).replace(",", "")
                current_patient["totals"]["issued_amount"] = float(amt)

        # Append last patient
        if current_patient:
            patients.append(current_patient)

        return {"patients": patients}

    async def process(self, id: str, file_path: str) -> dict:
        try:
            print("Processing file: PDFTextProcessor")
            print(f"Processing file: {file_path}")
            text = extract_text_from_pdf(file_path)
            cleaned_text = self.clean_text(text)
            parsed = self.parse_eob(cleaned_text)
            # Convert defaultdict to dict for JSON storage
            patients = parsed["patients"]
            for p in patients:
                if "services_by_dos" in p:
                    p["services_by_dos"] = dict(p["services_by_dos"])
            result_data = {"patients": patients, "text_length": len(text)}
            await files_collection.update_one(
                {"_id": ObjectId(id)},
                {"$set": {"status": "completed", "result": result_data}}
            )
            return {"id": id, "text_length": len(text), **result_data}
        except Exception as e:
            await files_collection.update_one(
                {"_id": ObjectId(id)},
                {"$set": {"status": "failed", "error": str(e)}}
            )
            raise e

    async def process_pdf(self, id: str, file_path: str) -> dict:
        """Extract visit number & date from each page. Save images as visit-26-page-20.png using the exact page number from the PDF when present."""
        doc = None
        try:
            doc = fitz.open(file_path)
            visits_data = _extract_pages_with_visits(doc)  # list of (visit_num, date_str, list of (doc_page_num, page_num_from_doc or None))
            output_dir = Path(file_path).resolve().parent
            output_dir.mkdir(parents=True, exist_ok=True)
            total_pages = len(doc)
            visits_result: list[dict] = []
            all_images_count = 0
            for visit_number_doc, visit_date_str, page_list in visits_data:
                visit_date_iso = _visit_date_to_iso(visit_date_str) if visit_date_str else ""
                page_number_doc = page_list[0][0] if page_list else 0
                page_count = len(page_list)
                pages_in_visit: list[dict] = []
                for page_idx, (doc_page_num, page_num_from_doc) in enumerate(page_list, start=1):
                    if MAX_PAGES_TO_SAVE is not None and all_images_count >= MAX_PAGES_TO_SAVE:
                        break
                    # Use exact page number from PDF when extracted, else sequential index
                    page_label = page_num_from_doc if page_num_from_doc is not None else page_idx
                    image_name = f"visit-{visit_number_doc}-page-{page_label}.png"
                    out_path = output_dir / image_name
                    pix = doc[doc_page_num - 1].get_pixmap(dpi=150, alpha=False)
                    pix.save(str(out_path))
                    pages_in_visit.append({"pageNumber": doc_page_num, "pageLabel": page_label, "image": image_name})
                    all_images_count += 1
                visits_result.append({
                    "visitNumber": visit_number_doc,
                    "visitDate": visit_date_iso,
                    "pageNumber": page_number_doc,
                    "pageCount": page_count,
                    "pages": pages_in_visit,
                })
                if MAX_PAGES_TO_SAVE is not None and all_images_count >= MAX_PAGES_TO_SAVE:
                    break
            result_data = {
                "documentId": id,
                "totalPages": total_pages,
                "visits": visits_result,
            }
            await files_collection.update_one(
                {"_id": ObjectId(id)},
                {"$set": {"status": "completed", "result": result_data}},
            )
            return result_data
        except Exception as e:
            await files_collection.update_one(
                {"_id": ObjectId(id)},
                {"$set": {"status": "failed", "error": str(e)}},
            )
            raise e
        finally:
            if doc is not None:
                doc.close()


def _ocr_visit_date_from_image(image_base64: str) -> str | None:
    """Optional: use OpenAI vision to extract 'Visit Date:' from a page image. Returns None if no key or failure."""
    from app.core.data import OPENAI_API_KEY
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=64,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Look at this image. Find the field labeled 'Visit Date:' and return ONLY the date value (e.g. Dec 26, 2025). If not visible return: NONE",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                        },
                    ],
                }
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text or text.upper() == "NONE":
            return None
        return text
    except Exception:
        return None


def _ocr_visit_and_page_from_image(image_base64: str) -> tuple[int | None, int | None]:
    """Use OpenAI vision to extract Visit # and Page # from top of page. Returns (visit_num, page_num) or (None, None)."""
    from app.core.data import OPENAI_API_KEY
    if not OPENAI_API_KEY:
        return (None, None)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=128,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Look at this image of the top of a document page. Find the field for Visit # (or Visit number) and the field for Page # (or Page number). Return ONLY two numbers separated by a comma: visit_number,page_number. Example: 17,2. If only one is visible return it with a comma: 17, or ,2. If neither visible return: NONE",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                        },
                    ],
                }
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text or text.upper() == "NONE":
            return (None, None)
        parts = text.replace(" ", "").split(",")
        visit_num = None
        page_num = None
        if len(parts) >= 1 and parts[0].strip().isdigit():
            visit_num = int(parts[0].strip())
        if len(parts) >= 2 and parts[1].strip().isdigit():
            page_num = int(parts[1].strip())
        return (visit_num, page_num)
    except Exception:
        return (None, None)


def _extract_pages_with_visits(doc: fitz.Document) -> list[tuple[int, str | None, list[tuple[int, int | None]]]]:
    """Extract visit number, date, and page number from each page. Pages with no visit number belong to the previous visit.
    Returns list of (visit_number_from_doc, visit_date_str | None, list of (doc_page_index_1based, page_number_from_doc or None)).
    Uses text patterns first; if visit number not found, uses OCR. Also extracts page number from text or OCR for filename."""
    raw_pages: list[tuple[int, str]] = []
    for i in range(1, len(doc) + 1):
        page = doc[i - 1]
        text = (page.get_text("text") or "").replace("\n", " ").strip()
        text = re.sub(r"\s+", " ", text)
        raw_pages.append((i, text))
    visits: list[tuple[int, str | None, list[tuple[int, int | None]]]] = []
    current_visit_number: int | None = None
    current_visit_date: str | None = None
    current_visit_pages: list[tuple[int, int | None]] = []  # (doc_page_num, page_num_from_doc or None)
    for page_num, text in raw_pages:
        visit_num = _find_visit_number_in_text(text)
        page_num_from_doc = _find_page_number_in_text(text)
        visit_date_inline = VISIT_DATE_INLINE_PATTERN.search(text)
        visit_date_legacy = VISIT_DATE_PATTERN.search(text)
        date_str = None
        if visit_date_inline:
            date_str = visit_date_inline.group(1).strip()
        elif visit_date_legacy:
            date_str = visit_date_legacy.group(1).strip()
        # If text has no visit number (or we want page number from OCR), try OCR on top of page
        ocr_page_num: int | None = None
        if visit_num is None or page_num_from_doc is None:
            try:
                page = doc[page_num - 1]
                rect = page.rect
                clip = fitz.Rect(0, 0, rect.width, rect.height * 0.25)
                pix = page.get_pixmap(clip=clip, dpi=150, alpha=False)
                b64 = __import__("base64").b64encode(pix.tobytes("png")).decode("ascii")
                ocr_visit, ocr_page = _ocr_visit_and_page_from_image(b64)
                if visit_num is None and ocr_visit is not None:
                    visit_num = ocr_visit
                if page_num_from_doc is None and ocr_page is not None:
                    page_num_from_doc = ocr_page
            except Exception:
                pass
        if visit_num is not None:
            if current_visit_number is not None and current_visit_pages:
                visits.append((current_visit_number, current_visit_date, current_visit_pages))
                current_visit_pages = []
            current_visit_number = visit_num
            current_visit_date = date_str
            current_visit_pages.append((page_num, page_num_from_doc))
        else:
            if current_visit_number is not None:
                current_visit_pages.append((page_num, page_num_from_doc))
    if current_visit_pages:
        visits.append((current_visit_number or 1, current_visit_date, current_visit_pages))
    if not visits:
        visits = [(1, None, [(p, None) for p in range(1, len(doc) + 1)])]
    return visits
