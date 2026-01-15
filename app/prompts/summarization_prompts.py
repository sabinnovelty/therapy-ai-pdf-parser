ADVOCATE_SUMMARY_TEMPLATE1 = """
As a Healthcare Advocate, provide a conscise summary this case in one (at max one concise paragraph):
{case_data}

Strict Rules: no HTML.
"""

ADVOCATE_SUMMARY_TEMPLATE = """
Role: Healthcare Advocate.
Task: Provide a high-density, maximum 1 paragraph and at max 4 lines recap of the provided case notes. 
Constraint: The recap must be significantly shorter than the original text. NO HTML and no "status" required. Omit phrases like "The notes indicate that..." or "The patient is..."

Notes: {case_data}
"""