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

    
  
    async def process(self, id: str, file_path: str) -> dict:
        """Simple synchronous flow: for each page, get visit number from model. If not found, skip. If found, save as visit-{number}-page-{number}.png. No buffering or continuation."""
        doc = None
        try:
            doc = fitz.open(file_path)
            output_dir = Path(file_path).resolve().parent
            pages_dir = output_dir / "pages"
            pages_dir.mkdir(parents=True, exist_ok=True)
            total_pages = len(doc)
            # visit_number -> next page label to use (1-based) for filename
            next_page_label_per_visit: dict[int, int] = {}
            visits_dict: dict[int, dict] = {}
            all_images_count = 0

            for i in range(total_pages):
                # if MAX_PAGES_TO_SAVE is not None and all_images_count >= MAX_PAGES_TO_SAVE:
                #     break
                await files_collection.update_one(
                    {"_id": ObjectId(id)},
                    {"$set": {"status": f"page {i + 1}/{total_pages}"}},
                )
                page = doc[i]
                temp_image = pages_dir / f"temp_{i}.png"
                pix = page.get_pixmap(dpi=150, alpha=False)
                pix.save(str(temp_image))
                image_b64 = __import__("base64").b64encode(pix.tobytes("png")).decode("ascii")

                visit_number, visit_date, page_number = _detect_visit_from_image(image_b64)
                print(f"[Page {i + 1}/{total_pages}] visit_number={visit_number}, visit_date={visit_date!r}, page_number={page_number}")

                if visit_number is None:
                    temp_image.unlink(missing_ok=True)
                    print(f"[Page {i + 1}/{total_pages}] skipped (no visit number)")
                    continue

                page_label = next_page_label_per_visit.get(visit_number, 1)
                next_page_label_per_visit[visit_number] = page_label + 1

                final_name = f"visit-{visit_number}-page-{page_label}.png"
                final_path = pages_dir / final_name
                if temp_image.exists():
                    os.rename(str(temp_image), str(final_path))
                else:
                    pix.save(str(final_path))
                print(f"[Page {i + 1}/{total_pages}] saved as {final_name}")

                if visit_number not in visits_dict:
                    visit_date_iso = _visit_date_to_iso(visit_date) if visit_date else ""
                    visits_dict[visit_number] = {"visitDate": visit_date_iso, "pages": []}
                visits_dict[visit_number]["pages"].append({
                    "pageNumber": i + 1,
                    "pageLabel": page_label,
                    "image": f"pages/{final_name}",
                })
                all_images_count += 1

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
    """Try Gemini first if key is set; else or on all-None result use OpenAI. Returns (visit_number, visit_date_str, page_number)."""
    from app.core.data import GEMINI_API_KEY, OPENAI_API_KEY
    if GEMINI_API_KEY:
        out = _detect_visit_from_image_gemini(image_base64)
        if out != (None, None, None):
            return out
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


