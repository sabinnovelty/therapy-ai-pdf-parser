from app.processors.base import BaseFileProcessor
from app.db.collections.files import files_collection
from app.utils.file import extract_text_from_pdf
from bson import ObjectId
import os
import re
from collections import defaultdict
from pathlib import Path
from app.prompts.pdf_visit_prompts import _DETECT_VISIT_PROMPT, DEBUG_EXTRACT_PAGE_TEXT_PROMPT

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


def _visit_date_to_mm_dd_yyyy(date_str: str) -> str:
    """Convert various date strings to MM/DD/YYYY for storage in MongoDB."""
    from datetime import datetime
    if not date_str or not date_str.strip():
        return ""
    s = date_str.strip()
    formats = (
        "%b %d, %Y", "%B %d, %Y",  # Dec 26, 2025 / December 26, 2025
        "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y",  # 12/26/2025, 12/26/25
        "%Y-%m-%d",  # 2025-12-26 (ISO)
    )
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%m/%d/%Y")
        except ValueError:
            continue
    return s  # return as-is if no parse


def _normalize_visit_date_raw(s: str | None) -> str | None:
    """Normalize date string: remove internal spaces; fix truncated year (12/15/2, 12/15/20, 12/15/202 -> 12/15/2025)."""
    if not s or not s.strip():
        return None
    s = s.strip()
    if s.upper() == "NONE":
        return None
    s = s.replace(" ", "")
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{1,4})$", s)
    if m:
        mm, dd, yy = m.group(1), m.group(2), m.group(3)
        if len(yy) < 4:
            if yy in ("2", "20", "202"):
                yy = "2025"
            elif yy == "200":
                yy = "2000"
            elif yy == "201":
                yy = "2015"
            elif yy == "203":
                yy = "2030"
            elif len(yy) == 3:
                yy = yy + "5"
            elif len(yy) == 2:
                yy = yy + "25" if yy == "20" else yy + "05"
            elif len(yy) == 1:
                yy = "2025" if yy == "2" else yy + "025"
            else:
                yy = yy + "5"
            s = f"{int(mm):02d}/{int(dd):02d}/{yy}"
    return s


def _parse_visit_date_and_page_from_parts(parts: list[str]) -> tuple[str | None, int | None]:
    """Parse visit_date and page_number from comma-separated parts. Reassemble date if model returned MM,DD,YYYY (e.g. 33,02,10,2020,7 -> date 02/10/2020, page 7)."""
    if len(parts) >= 5:
        m, d, y = parts[1].strip(), parts[2].strip(), parts[3].strip()
        if (
            m.isdigit() and d.isdigit() and y.isdigit()
            and 1 <= int(m) <= 12
            and 1 <= int(d) <= 31
            and len(y) == 4
        ):
            reassembled = f"{int(m):02d}/{int(d):02d}/{y}"
            page_num = _parse_page_number_from_response(parts[4] if len(parts) > 4 else "NONE")
            return (reassembled, page_num)
    raw_date = None if (len(parts) < 2 or parts[1].upper() == "NONE") else parts[1].strip()
    raw_date = _normalize_visit_date_raw(raw_date)
    page_num = _parse_page_number_from_response(parts[2] if len(parts) > 2 else "NONE")
    return (raw_date, page_num)


def _is_valid_visit_date(s: str | None) -> bool:
    """Return False if the string is an incomplete or invalid date (e.g. '02/', '12/26'); require a full date."""
    if not s or not s.strip():
        return False
    s = s.strip()
    if s.upper() == "NONE":
        return False
    if len(s) < 8:
        return False
    if s.endswith("/") or s.endswith("-"):
        return False
    if re.match(r"^\d{1,2}/\s*$", s) or re.match(r"^\d{1,2}-\s*$", s):
        return False
    return _visit_date_to_mm_dd_yyyy(s) != "" and len(_visit_date_to_mm_dd_yyyy(s)) == 10


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
            buffer_pages = []  # Case 2: pages with visitDate but no visitNumber, until we see a visitNumber

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

                # Case 1 skip: no visitNumber AND no visitDate AND no current visit → skip
                if (
                    visit_number is None
                    and (visit_date is None or not visit_date.strip())
                    and current_visit_number is None
                ):
                    temp_image.unlink(missing_ok=True)
                    print(f"[Page {i+1}] skipped (no visit number, no visit date)")
                    continue

                # Case 2 buffer: has visitDate but no visitNumber and no current visit → buffer
                if (
                    visit_number is None
                    and visit_date
                    and visit_date.strip()
                    and current_visit_number is None
                ):
                    if buffer_pages:
                        print('has buffer pages')
                    else:
                        buffer_pages.append(
                            {
                                "index": i,
                                "temp_path": temp_image,
                                "visit_date": visit_date,
                                "page_number": page_number,
                            }
                        )
                    print(f"[Page {i+1}] buffered (visit date only, waiting for visit number)")
                    continue

                # New visit: visit number found
                if visit_number is not None:
                    current_visit_number = visit_number
                    current_visit_page_counter = 1

                    # Use visit_date from current page, or from first buffered page if current has none
                    date_for_visit = visit_date
                    if not date_for_visit and buffer_pages:
                        date_for_visit = buffer_pages[0].get("visit_date")

                    if visit_number not in visits_dict:
                        visit_date_mm_dd_yyyy = (
                            _visit_date_to_mm_dd_yyyy(date_for_visit) if date_for_visit else ""
                        )
                        visits_dict[visit_number] = {
                            "visitDate": visit_date_mm_dd_yyyy,
                            "pages": [],
                        }

                    # Flush buffer: assign buffered pages to this visit as page-1, page-2, ...
                    for buf in buffer_pages:
                        label = current_visit_page_counter
                        final_name = f"visit-{visit_number}-page-{label}.png"
                        final_path = pages_dir / final_name
                        os.rename(buf["temp_path"], final_path)
                        visits_dict[visit_number]["pages"].append(
                            {
                                "pageNumber": buf["index"] + 1,
                                "pageLabel": buf.get("page_number") or label,
                                "image": f"pages/{final_name}",
                            }
                        )
                        current_visit_page_counter += 1
                    buffer_pages.clear()

                    # Save current page
                    final_name = f"visit-{visit_number}-page-{current_visit_page_counter}.png"
                    final_path = pages_dir / final_name
                    os.rename(temp_image, final_path)
                    visits_dict[visit_number]["pages"].append(
                        {
                            "pageNumber": i + 1,
                            "pageLabel": page_number if page_number is not None else current_visit_page_counter,
                            "image": f"pages/{final_name}",
                        }
                    )
                    current_visit_page_counter += 1
                    print(f"[Page {i+1}] saved as {final_name} (new visit)")
                    continue

                # Continuation: no visit number, we have current visit → same visit
                if visit_number is None and current_visit_number is not None:
                    if visit_date and visit_date.strip():
                        visit_date_mm_dd_yyyy = _visit_date_to_mm_dd_yyyy(visit_date)
                        if visit_date_mm_dd_yyyy:
                            visits_dict[current_visit_number]["visitDate"] = visit_date_mm_dd_yyyy

                    final_name = f"visit-{current_visit_number}-page-{current_visit_page_counter}.png"
                    final_path = pages_dir / final_name
                    os.rename(temp_image, final_path)
                    visits_dict[current_visit_number]["pages"].append(
                        {
                            "pageNumber": i + 1,
                            "pageLabel": page_number if page_number is not None else current_visit_page_counter,
                            "image": f"pages/{final_name}",
                        }
                    )
                    current_visit_page_counter += 1
                    print(f"[Page {i+1}] saved as {final_name} (continuation)")
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

def get_page_text_via_gemini(image_base64: str) -> str:
    """Ask Gemini to return all text it sees on the page image. Used for debugging visit number detection."""
    from app.core.data import GEMINI_API_KEY
    if not GEMINI_API_KEY:
        return "(GEMINI_API_KEY not set)"
    try:
        import base64
        import io
        import google.generativeai as genai
        from PIL import Image
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        image_bytes = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(image_bytes))
        resp = model.generate_content(
            [DEBUG_EXTRACT_PAGE_TEXT_PROMPT, img],
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=2048,
                temperature=0,
            ),
        )
        return (resp.text or "").strip() or "(empty response)"
    except Exception as e:
        return f"(error: {e})"


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
        model = genai.GenerativeModel("gemini-2.5-flash")
        image_bytes = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(image_bytes))
        resp = model.generate_content(
            [_DETECT_VISIT_PROMPT, img],
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=256,
                temperature=0,
            ),
        )
        print(f"Gemini first response *****: {resp.text}")
        raw = (resp.text or "").strip()
        raw = raw.replace("\n", "").replace("\r", "")  # collapse newlines so "12/\n15/2025" -> "12/15/2025"
        print(f"Gemini response stripped response ***: {raw}")
        if not raw or raw.upper() == "NONE":
            print("[Gemini] raw:", raw or "(empty/NONE)")
            print("[Gemini] parsed: visit_number=None, visit_date=None, page_number=None")
            return (None, None, None)
        parts = [p.strip() for p in raw.split(",")]
        while len(parts) < 3:
            parts.append("NONE")
        visit_num = _parse_visit_number_from_response(parts[0] if parts else "NONE")
        raw_visit_date, page_num = _parse_visit_date_and_page_from_parts(parts)
        visit_date = raw_visit_date if _is_valid_visit_date(raw_visit_date) else None
        if raw_visit_date and not visit_date:
            print("[Gemini] rejected incomplete/invalid visit_date: %r" % raw_visit_date)
        print("[Gemini] raw:", raw)
        print("[Gemini] parsed: visit_number=%s, visit_date=%s, page_number=%s" % (visit_num, visit_date, page_num))
        return (visit_num, visit_date, page_num)
    except Exception:
        return (None, None, None)


def _detect_visit_from_image(image_base64: str) -> tuple[int | None, str | None, int | None]:
    """Try Gemini first if key is set; else or on all-None result use OpenAI. Returns (visit_number, visit_date_str, page_number)."""
    from app.core.data import GEMINI_API_KEY, OPENAI_API_KEY
    if GEMINI_API_KEY:
        print("Using Gemini to detect visit from image")
        out = _detect_visit_from_image_gemini(image_base64)
        if out != (None, None, None):
            return out
    # if OPENAI_API_KEY:
    #     return _detect_visit_from_image_openai(image_base64)
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
        visit_num = _parse_visit_number_from_response(parts[0] if parts else "NONE")
        raw_visit_date, page_num = _parse_visit_date_and_page_from_parts(parts)
        visit_date = raw_visit_date if _is_valid_visit_date(raw_visit_date) else None
        return (visit_num, visit_date, page_num)
    except Exception:
        return (None, None, None)


def _parse_visit_number_from_response(s: str) -> int | None:
    """Extract visit number from model response. Handles '17', 'NONE', 'Visit 17' -> 17, etc."""
    if not s or s.upper() == "NONE":
        return None
    s = s.strip()
    if s.isdigit():
        return int(s)
    m = re.search(r"\d+", s)
    if m:
        return int(m.group(0))
    return None


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
