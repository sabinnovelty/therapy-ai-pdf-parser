_DETECT_VISIT_PROMPT = """
Look at this document page image and extract exactly three values.

1) VISIT NUMBER (visit_number)
   - Return a number ONLY when you see a **clearly labeled field** on the page where the label is one of:
     'Visit #', 'Visit #:', 'Visit Number', 'Visits', 'Visits :', 'Visit No.', or 'Visit' / 'Visti' (typo) followed by '#' and then the number.
   - The label and the number must appear together (same line or label on one line, number on the next). The number is the value of that specific field.
   - Examples to ACCEPT (label + value clearly present):
       Visit #: 17
       Visit #
       17
       Visit No. 26
       Visti # 31
       Visits:   32
       visit number: 33
       visits number: 10

   - DO NOT return a number for visit_number in these cases—return NONE:
     * You do NOT see any label like "Visit #", "Visit Number", "Visit No.", "Visits",'visit number',vis or "Visti #" on the page.
     * The only numbers on the page are from "Page X", "p.X", "X of Y"—those are page numbers, not visit numbers.
     * A number appears in body text, narrative, or elsewhere without being the value of a clearly labeled Visit # / Visit Number field.
     * You are guessing or inferring—when in doubt, return NONE.
   - If the Visit # / Visit Number pattern is not clearly present, return NONE. Do not return a random number.

2) VISIT DATE (visit_date)
   - Return a date ONLY when you see a clearly labeled visit-date field on the page. If you do NOT see any of the labels below with a date value, return NONE for visit_date. Do not use a date from elsewhere (e.g. header, DOB, other forms).
   - Accepted labels (the date must be the value of one of these):
     'Visit Date', 'Date of Daily Note', 'Date of Visit', 'Date of Daily Note:', 'Date', or 'Visit' (with date on next line).
   - The date may appear on the same line OR the next line.

   - COMMON PATTERN: When the document shows "Visit:" (or "Visit") on one line and a date on the NEXT line, that date is the visit_date:
       Visit:
       12/15/2025   → output visit_date as 12/15/2025 (the full date)
       Visit:
       02/10/2020   → output visit_date as 02/10/2020
     You MUST copy the ENTIRE date (MM/DD/YYYY). Never output only 12 or 12/ or 02/ — always include day and year: 12/15/2025.

   - Other formats to accept:
       Visit Date: 02/10/2020
       Date of Visit - 12/26/2025
       Date:
       March 5, 2024  → output as 03/05/2024
       Date of Daily Note:
       01/15/2023
       DOS: 7/4/2022
       Service Date - August 21, 2021

   - DISAMBIGUATION: If label is "Visit" (no #) AND the value on same/next line looks like a DATE (e.g. 12/15/2025) → it is visit_date. If label contains "#" (Visit #) → it is visit_number, not visit_date.

   - Output the visit_date as a SINGLE value in MM/DD/YYYY form. Write the full year with all 4 digits and no spaces (e.g. 02/10/2020, 12/15/2025).
   - CRITICAL: The year must be exactly 4 digits with no spaces: 2025 not 202, not 20, not 2, not 12/15/2 or 12/15/2 025. If you see 12/15/2025 on the page, output exactly 12/15/2025. Never truncate the year. If the full date is not visible, return NONE.

   - Return NONE for visit_date when:
       * No label like "Visit Date", "Date of Daily Note", "Date of Visit", "Visit:" (with date below), or "Date" is present on the page.
       * The only dates on the page are DOB, admission/discharge, or other non-visit-date fields.
       * You would be guessing or inferring—when in doubt, return NONE.
   - DO NOT use: Birth dates (DOB); Admission/Discharge dates unless clearly labeled as Visit Date; dates from headers or other forms.

3) PAGE NUMBER (page_number)
   - Extract the numeric page number from common page indicators anywhere on the page (top, bottom, left, or right).

   - Accept ALL of the following formats (case-insensitive):
       Page 1
       Page #: 2
       Page: 11
       Page 2 of 10
       Page 3 of 7
       p.1
       p.2
       Pg 5
       pg.6
       1 of 89
       2 of 89
       3/12
       1 OF 5
       2 Of 10

   - IMPORTANT RULES:
       - Treat "of", "OF", "Of" the SAME (case-insensitive).
       - For formats like "X of Y" or "X/Y", ALWAYS return ONLY the FIRST number (X).
           Examples:
               "Page 2 of 10" → 2
               "3 of 12" → 3
               "1 OF 5" → 1
               "2/8" → 2

       - For formats like "p.1", "Pg 2", return the number after the prefix.
           Examples:
               "p.1" → 1
               "Pg 5" → 5

       - Ignore any surrounding text—ONLY extract the page number integer.

   - DO NOT:
       - Do not confuse Visit Number with Page Number.
       - Do not return the total page count (Y in "X of Y").

   - If no page number is clearly visible, return NONE.

Return ONLY three values separated by commas: visit_number,visit_date,page_number
- For visit_number use ONLY a single integer or NONE (no words, no "Visit 17").
- For visit_date use exactly one value in MM/DD/YYYY form (e.g. 02/10/2020). Never output only part of the date (e.g. 02 or 02/). If no full date is visible, use NONE.
- Use NONE for any value not clearly present.

Examples of expected outputs (always three comma-separated values; date is full MM/DD/YYYY):
26,02/10/2020,7
NONE,12/26/2025,3
17,12/15/2025,1
17,NONE,11
NONE,NONE,NONE
31,12/26/2025,NONE

When the page shows "Visit:" with "12/15/2025" on the next line, output: visit_number (or NONE), 12/15/2025, page_number. Never output 12 or 12/ for the date.

CRITICAL for visit_number:
- Only output a number when you SEE a labeled field on the page such as "Visit #", "Visit Number", "Visit No.", "Visits", or "Visti #" with a number as its value.
- If that pattern is not found, output NONE. Do not guess or return a number from elsewhere on the page (e.g. page numbers, other IDs, or text). Wrong visit numbers cause wrong grouping—when unsure, always use NONE.

CRITICAL for visit_date:
- Only output a date when you SEE one of these labels on the page with a date as its value: "Visit Date", "Date of Daily Note", "Date of Visit", "Visit:" (with date on next line), or "Date".
- If the page has NO such visit-date label, output NONE for visit_date. Do not use a date from headers, DOB, or any other field. When in doubt, return NONE.
"""

# Debug: ask Gemini to return all text it sees on the page (to inspect why visit number might be missed)
DEBUG_EXTRACT_PAGE_TEXT_PROMPT = """
Look at this document page image and return ALL text you can see on the page.
- Include every label and value (e.g. "Visit #", "Visit Date", "Page #", and their values).
- Preserve the order and structure as much as possible; use newlines between lines.
- Include headers, field names, and numbers. Do not summarize—transcribe what you see.
- If something is unclear or partially visible, include it with a note in parentheses.
"""