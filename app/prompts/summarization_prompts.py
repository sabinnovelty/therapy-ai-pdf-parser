FULL_SUMMARY_TEMPLATE = """
"{case_data}"

Please summarize the following notes directly to me, the {onBehalfOf} in a structured format, focusing on key actions and communications. Include the following sections:

1. Initial Request: Briefly explain the initial issue or request.
2. Key Updates: Highlight major actions taken, communications, and progress in chronological order, including dates.
3. Current Status: Summarize the present situation or outcome of the case.

Do not expose any ids

Complete the sentence at the end with a full stop.
Give html format
"""

SHORT_SUMMARY_TEMPLATE = """
"{case_data}"

Please summarize the following case notes directly to me, the {onBehalfOf} in a paragraph format.

Do not expose any ids
Keep it simple and short.
Complete the sentence at the end with a full stop.
"""

ADVOCATE_SUMMARY_TEMPLATE = """
As a Healthcare Advocate, summarize this case in one concise paragraph (max 4-5 sentences):
{case_data}

Provide a brief overview, mention 2-3 key events, and state the current status. 
Strict Rules: No IDs, no HTML, no bullet points, no headers. One single paragraph only.
"""