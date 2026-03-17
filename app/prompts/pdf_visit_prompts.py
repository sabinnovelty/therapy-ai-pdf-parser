_DETECT_VISIT_PROMPT = """
Look at this document page image and extract exactly three values.

1) VISIT NUMBER (visit_number)
   - Use the number that is the value for a field labeled: 'Visit #', 'Visit #:', 'Visit Number', 'Visits', 'Visits :', 'Visit No.', or the word 'Visit' (or common typo 'Visti' / 'visti') followed by # or a number. It is the visit ID (e.g. 17, 26, 31), not a page index.
   - The number may appear next to or under such a label. Also accept labels like "Visit #:" with the number on the next line.
   - DO NOT use: numbers from 'Page 2', 'Page #: 2', 'p.2', '2 of 9', 'page 2 of 10', or any page counter—those are PAGE numbers.
   - If you see a clearly labeled Visit # / Visit Number / Visti # field, return that number only (e.g. 31). If you truly do not see any such field, return NONE.

2) VISIT DATE (visit_date)
   - Use dates under labels like 'Visit Date', 'Date of Daily Note', 'Date of Visit', or 'Date'. Format as MM/DD/YYYY or Month DD, YYYY.
   - If not visible, return NONE.

3) PAGE NUMBER (page_number)
   - The numeric page of the document: from 'Page 1', 'Page #: 2', 'p.11', '1 of 89', etc. Return only the number (e.g. 1, 2, 11).
   - If not visible, return NONE.

Return ONLY three values separated by commas: visit_number,visit_date,page_number
- For visit_number use ONLY a single integer or NONE (no words, no "Visit 17"—just 17 or NONE).
- Use NONE for any value not clearly present. Examples:
26,02/10/2020,7
NONE,12/26/2025,3
17,NONE,11
NONE,NONE,NONE
31,12/26/2025,NONE

CRITICAL: If the only number you see is from 'Page X' or 'p.X' or 'X of Y', do NOT put it in visit_number. Put it only in page_number, and use NONE for visit_number.
"""

# Debug: ask Gemini to return all text it sees on the page (to inspect why visit number might be missed)
DEBUG_EXTRACT_PAGE_TEXT_PROMPT = """
Look at this document page image and return ALL text you can see on the page.
- Include every label and value (e.g. "Visit #", "Visit Date", "Page #", and their values).
- Preserve the order and structure as much as possible; use newlines between lines.
- Include headers, field names, and numbers. Do not summarize—transcribe what you see.
- If something is unclear or partially visible, include it with a note in parentheses.
"""