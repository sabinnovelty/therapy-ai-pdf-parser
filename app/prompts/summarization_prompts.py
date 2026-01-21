ADVOCATE_SUMMARY_TEMPLATE = """
Role: Senior Healthcare Advocate Documentation Specialist.
Task: Provide a high-density, single-paragraph recap of the notes below using the absolute minimum number of lines possible (maximum 4). Synthesize and merge all related details into long, information-dense sentences to avoid trivial fragments. No fluff. Every line must end with ...
Constraint: The recap must be significantly shorter than the original text. NO HTML, no status and ignore trivial metadata like email, timestamp, greetings etc. Omit phrases like "The notes indicate that..." or "The patient is...".

Notes: {case_data}
"""

PATIENT_SUMMARY_TEMPLATE = """
Role: Senior Healthcare Advocate Documentation Specialist.
Task: Provide a high-density, single-paragraph recap of the notes below using the absolute minimum number of lines possible (maximum 4). Synthesize and merge all related details into long, information-dense sentences to avoid trivial fragments. No fluff. Every line must end with ...
Constraint: The recap must be significantly shorter than the original text. NO HTML, no status and ignore trivial metadata like email, timestamp, greetings etc. Omit phrases like "The notes indicate that..." or "The patient is...".

Notes: {case_data}
"""