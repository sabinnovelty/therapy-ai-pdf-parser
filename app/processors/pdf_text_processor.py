from app.processors.base import BaseFileProcessor
from app.db.collections.files import files_collection
from app.utils.file import extract_text_from_pdf
from bson import ObjectId
import os
import re
from collections import defaultdict
from pathlib import Path
from app.prompts.pdf_visit_prompts import _DETECT_VISIT_PROMPT

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
MAX_PAGES_TO_SAVE = 10


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


def _get_visit_date_from_text(text: str) -> str | None:
    """Extract visit date from text. Same patterns as _DETECT_VISIT_PROMPT: 'Visit Date: ...' or 'Visit: MM/DD/YYYY'."""
    if not text or not text.strip():
        return None
    m = VISIT_DATE_PATTERN.search(text)
    if m:
        return m.group(1).strip()
    m = VISIT_DATE_INLINE_PATTERN.search(text)
    if m:
        return m.group(1).strip()
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
        import os
        import base64
        import fitz
        from pathlib import Path
        from bson import ObjectId

        doc = None

        try:
            doc = fitz.open(file_path)

            output_dir = Path(file_path).resolve().parent
            pages_dir = output_dir / "pages"
            pages_dir.mkdir(parents=True, exist_ok=True)

            total_pages = len(doc)

            visits_dict = {}

            current_visit_number = None
            current_visit_page_counter = 1
            current_visit_date = None  # date of the visit we're currently in (for continuation check)
            used_page_numbers_in_visit = set()  # document page numbers already used in filename (avoid duplicates)

            buffer_pages = []

            for i in range(total_pages):

                await files_collection.update_one(
                    {"_id": ObjectId(id)},
                    {"$set": {"status": f"page {i+1}/{total_pages}"}},
                )

                page = doc[i]

                temp_image = pages_dir / f"temp_{i}.png"

                pix = page.get_pixmap(dpi=150, alpha=False)
                pix.save(str(temp_image))

                image_b64 = base64.b64encode(pix.tobytes("png")).decode("ascii")

                visit_number, visit_date, page_number = _detect_visit_from_image(image_b64)

                print(
                    f"[Page {i+1}] visit_number={visit_number}, visit_date={visit_date}, page_number={page_number}"
                )

                # -------------------------------------------------
                # CASE 1: Nothing found → skip
                # -------------------------------------------------
                if visit_number is None and visit_date is None and current_visit_number is None:
                    temp_image.unlink(missing_ok=True)
                    print(f"[Page {i+1}] skipped (no visit info)")
                    continue

                # -------------------------------------------------
                # CASE 2: Visit date but no visit number → buffer
                # -------------------------------------------------
                if visit_number is None and visit_date is not None and current_visit_number is None:
                    buffer_pages.append(
                        {
                            "index": i,
                            "temp_path": temp_image,
                            "visit_date": visit_date,
                            "page_number": page_number,  # page number found on PDF (for filename/label)
                        }
                    )

                    print(f"[Page {i+1}] buffered waiting for visit number")
                    continue

                # -------------------------------------------------
                # CASE 3: Visit number found
                # -------------------------------------------------
                if visit_number is not None:

                    current_visit_number = visit_number
                    current_visit_page_counter = 1
                    used_page_numbers_in_visit = set()
                    current_visit_date = (
                        visit_date
                        if visit_date
                        else (buffer_pages[0]["visit_date"] if buffer_pages else None)
                    )

                    def _page_num_for_filename(doc_page_num: int | None, fallback: int) -> int:
                        """Use document page number if available and not already used; else fallback."""
                        if doc_page_num is not None and doc_page_num not in used_page_numbers_in_visit:
                            used_page_numbers_in_visit.add(doc_page_num)
                            return doc_page_num
                        return fallback

                    # process buffered pages first
                    if buffer_pages:

                        print(f"Processing {len(buffer_pages)} buffered pages")

                        for buf in buffer_pages:
                            doc_pnum = buf.get("page_number")
                            label = _page_num_for_filename(doc_pnum, current_visit_page_counter)
                            final_name = f"visit-{visit_number}-page-{label}.png"
                            final_path = pages_dir / final_name

                            os.rename(buf["temp_path"], final_path)

                            if visit_number not in visits_dict:
                                visit_date_iso = (
                                    _visit_date_to_iso(buf["visit_date"])
                                    if buf["visit_date"]
                                    else ""
                                )

                                visits_dict[visit_number] = {
                                    "visitDate": visit_date_iso,
                                    "pages": [],
                                }

                            visits_dict[visit_number]["pages"].append(
                                {
                                    "pageNumber": buf["index"] + 1,
                                    "pageLabel": doc_pnum if doc_pnum is not None else current_visit_page_counter,
                                    "image": f"pages/{final_name}",
                                }
                            )

                            current_visit_page_counter += 1

                        buffer_pages.clear()

                    doc_pnum = page_number
                    label = _page_num_for_filename(doc_pnum, current_visit_page_counter)
                    final_name = f"visit-{visit_number}-page-{label}.png"
                    final_path = pages_dir / final_name

                    os.rename(temp_image, final_path)

                    if visit_number not in visits_dict:
                        visit_date_iso = _visit_date_to_iso(visit_date) if visit_date else ""

                        visits_dict[visit_number] = {
                            "visitDate": visit_date_iso,
                            "pages": [],
                        }

                    visits_dict[visit_number]["pages"].append(
                        {
                            "pageNumber": i + 1,
                            "pageLabel": doc_pnum if doc_pnum is not None else current_visit_page_counter,
                            "image": f"pages/{final_name}",
                        }
                    )

                    current_visit_page_counter += 1

                    print(f"[Page {i+1}] saved as {final_name}")

                    continue

                # -------------------------------------------------
                # CASE 4: Page has a visit date but no visit number → not continuation of previous; reset and buffer (new segment)
                # -------------------------------------------------
                if (
                    visit_number is None
                    and current_visit_number is not None
                    and visit_date is not None
                    and (
                        current_visit_date is None
                        or visit_date.strip() != current_visit_date.strip()
                    )
                ):
                    current_visit_number = None
                    current_visit_page_counter = 1
                    current_visit_date = None
                    used_page_numbers_in_visit = set()
                    buffer_pages.append(
                        {
                            "index": i,
                            "temp_path": temp_image,
                            "visit_date": visit_date,
                            "page_number": page_number,
                        }
                    )
                    print(f"[Page {i+1}] new date, buffered (not continuation of previous visit)")
                    continue

                # -------------------------------------------------
                # CASE 5: Continuation page (same visit, no new visit number)
                # -------------------------------------------------
                if visit_number is None and current_visit_number is not None:
                    doc_pnum = page_number
                    if doc_pnum is not None and doc_pnum not in used_page_numbers_in_visit:
                        used_page_numbers_in_visit.add(doc_pnum)
                        label = doc_pnum
                    else:
                        label = current_visit_page_counter

                    final_name = f"visit-{current_visit_number}-page-{label}.png"
                    final_path = pages_dir / final_name

                    os.rename(temp_image, final_path)

                    visits_dict[current_visit_number]["pages"].append(
                        {
                            "pageNumber": i + 1,
                            "pageLabel": doc_pnum if doc_pnum is not None else current_visit_page_counter,
                            "image": f"pages/{final_name}",
                        }
                    )

                    current_visit_page_counter += 1

                    print(f"[Page {i+1}] continuation saved as {final_name}")

                    continue

            visits_result = [
                {
                    "visitNumber": vnum,
                    "visitDate": data["visitDate"],
                    "pageNumber": data["pages"][0]["pageNumber"] if data["pages"] else 0,
                    "pageCount": len(data["pages"]),
                    "pages": data["pages"],
                }
                for vnum, data in sorted(visits_dict.items())
            ]

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

def _detect_visit_from_image_textract(image_base64: str) -> tuple[int | None, str | None, int | None]:
    """Use AWS Textract to get text from the page image, then apply same patterns as _DETECT_VISIT_PROMPT
    (visit number, visit date, page number). Returns (visit_number, visit_date_str, page_number)."""
    from app.core.data import (
        AWS_ACCESS_KEY_ID,
        AWS_REGION,
        AWS_SECRET_ACCESS_KEY,
        AWS_TEXTRACT_ENABLED,
    )
    if not AWS_TEXTRACT_ENABLED:
        return (None, None, None)
    try:
        import base64
        import boto3
        image_bytes = base64.b64decode(image_base64)
        # Use credentials from config when set; otherwise boto3 uses env / profile / IAM role
        client_kwargs = {"region_name": AWS_REGION}
        if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
            client_kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
        client = boto3.client("textract", **client_kwargs)
        resp = client.detect_document_text(Document={"Bytes": image_bytes})
        lines = []
        for block in resp.get("Blocks", []):
            if block.get("BlockType") == "LINE":
                text = (block.get("Text") or "").strip()
                if text:
                    lines.append(text)
        combined = " ".join(lines)
        combined = re.sub(r"\s+", " ", combined).strip()
        # Print Textract raw output (truncate if long)
        _max_preview = 500
        preview = combined[:_max_preview] + ("..." if len(combined) > _max_preview else "")
        print("[Textract] output (%d lines, %d chars): %s" % (len(lines), len(combined), repr(preview)))
        visit_number = _find_visit_number_in_text(combined)
        visit_date = _get_visit_date_from_text(combined)
        page_number = _find_page_number_in_text(combined)
        print("[Textract] parsed visit_number=%s visit_date=%s page_number=%s" % (
            visit_number, visit_date, page_number))
        return (visit_number, visit_date, page_number)
    except Exception as e:
        print("[Textract] error: %s" % (e,))
        if "UnrecognizedClientException" in type(e).__name__ or "security token" in str(e).lower():
            print("[Textract] hint: check AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (invalid or expired token)")
        return (None, None, None)


def _detect_visit_from_image_gemini(image_base64: str) -> tuple[int | None, str | None, int | None]:
    """Use Gemini to extract Visit #, Visit date, and Page # from a full page image.
    Returns (visit_number, visit_date_str, page_number) - any can be None if not found.
    Visit number is ONLY from fields labeled 'Visit #' / 'Visit Number'; never from page numbers."""
    from app.core.data import GEMINI_API_KEY
    if not GEMINI_API_KEY:
        return (None, None, None)
    try:
        import base64
        import io
        import google.generativeai as genai
        from PIL import Image
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        image_bytes = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(image_bytes))
        resp = model.generate_content(
            [_DETECT_VISIT_PROMPT, img],
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=128,
                temperature=0,
            ),
        )
        raw = (resp.text or "").strip()
        if not raw or raw.upper() == "NONE":
            print("[Gemini] raw:", raw or "(empty/NONE)")
            print("[Gemini] parsed: visit_number=None, visit_date=None, page_number=None")
            return (None, None, None)
        parts = [p.strip() for p in raw.split(",")]
        while len(parts) < 3:
            parts.append("NONE")
        visit_num = None
        if parts[0].replace("NONE", "").strip().isdigit():
            visit_num = int(parts[0].strip())
        visit_date = None if parts[1].upper() == "NONE" else parts[1].strip()
        page_num = _parse_page_number_from_response(parts[2] if len(parts) > 2 else "NONE")
        print("[Gemini] raw:", raw)
        print("[Gemini] parsed: visit_number=%s, visit_date=%s, page_number=%s" % (visit_num, visit_date, page_num))
        return (visit_num, visit_date, page_num)
    except Exception:
        return (None, None, None)


def _detect_visit_from_image(image_base64: str) -> tuple[int | None, str | None, int | None]:
    """Use AWS Textract first (same patterns as _DETECT_VISIT_PROMPT). If disabled or no result, fall back to OpenAI. Gemini no longer used."""
    from app.core.data import AWS_TEXTRACT_ENABLED, OPENAI_API_KEY
    if AWS_TEXTRACT_ENABLED:
        out = _detect_visit_from_image_textract(image_base64)
        if out != (None, None, None):
            return out
        if OPENAI_API_KEY:
            print("[Vision] Textract returned no result, using OpenAI fallback")
    if OPENAI_API_KEY:
        return _detect_visit_from_image_openai(image_base64)
    return (None, None, None)


def _detect_visit_from_image_openai(image_base64: str) -> tuple[int | None, str | None, int | None]:
    """Use OpenAI vision to extract Visit #, Visit date, and Page # from a full page image.
    Returns (visit_number, visit_date_str, page_number) - any can be None if not found."""
    from app.core.data import OPENAI_API_KEY
    if not OPENAI_API_KEY:
        return (None, None, None)
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
                            "text": _DETECT_VISIT_PROMPT,
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                        },
                    ],
                }
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
        if not raw or raw.upper() == "NONE":
            return (None, None, None)
        parts = [p.strip() for p in raw.split(",")]
        while len(parts) < 3:
            parts.append("NONE")
        visit_num = None
        if parts[0].replace("NONE", "").strip().isdigit():
            visit_num = int(parts[0].strip())
        visit_date = None if parts[1].upper() == "NONE" else parts[1].strip()
        page_num = _parse_page_number_from_response(parts[2] if len(parts) > 2 else "NONE")
        return (visit_num, visit_date, page_num)
    except Exception:
        return (None, None, None)


def _parse_page_number_from_response(s: str) -> int | None:
    """Extract numeric page from model response. Handles 'p.11' -> 11, 'p.1' -> 1, '11', 'Page 11', etc."""
    if not s or s.upper() == "NONE":
        return None
    s = s.strip()
    if s.isdigit():
        return int(s)
    m = re.search(r"\d+", s)
    if m:
        return int(m.group(0))
    return None


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
