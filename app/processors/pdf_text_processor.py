from app.processors.base import BaseFileProcessor
from app.db.collections.files import files_collection
from app.utils.file import extract_text_from_pdf
from bson import ObjectId
import re
from collections import defaultdict


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