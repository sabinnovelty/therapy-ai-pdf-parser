Here is the architectural analysis formatted as a **System Design Specification**. You can copy and paste this directly into your project documentation, PRD (Product Requirement Document), or technical proposal.

---

# Technical Strategy: Healthcare Advocacy RAG Architecture

## 1. Executive Summary

A standard monolithic RAG (Retrieval-Augmented Generation) approach is **insufficient** for Healthcare Advocacy. Advocacy requires not just information retrieval, but reasoning, verification, and action.

**Recommendation:** Adopt a **Router-Based Agentic Architecture**. This splits the workflow into specialized "lanes" to handle private plan data, public medical knowledge, and real-time provider data separately.

---

## 2. Core Architectural Components

### A. The "Traffic Controller" (Semantic Router)

You must implement a routing layer before any retrieval happens. This prevents "pollution" (sending PHI to Google) and ensures accuracy (not using a generic web search to answer specific benefit questions).

* **Input:** User Query (e.g., "Why was my claim denied?").
* **Mechanism:** A lightweight classifier (BERT or LLM Prompt) detects intent.
* **Output:** Routes to one of three specific Agents.

### B. The Three Agent Lanes

#### Lane 1: The Plan Agent (Private RAG)

* **Purpose:** Answers questions about specific coverage, deductibles, and exclusions.
* **Data Source:** User-uploaded Plan Documents (PDFs), EOBs (Explanation of Benefits).
* **Search Strategy:** **Hybrid Search (Vector + Keyword)**.
* *Why:* Vector search finds concepts ("physiotherapy coverage"). Keyword search finds exact codes ("CPT 99213", "Section 15").


* **Critical Requirement:** Strict adherence to source documents (Temperature = 0).

#### Lane 2: The Action Agent (Tool Use)

* **Purpose:** Performs lookups and drafts documents.
* **Data Source:** External APIs.
* **Tools:**
* `NPI_Registry_Tool`: Verifies if a doctor is real and active.
* `CMS_Code_Lookup`: Validates billing codes.
* `Appeals_Drafter`: Uses templates to write letters based on retrieved facts.


* **Why:** RAG cannot query live databases; Agents with tools can.

#### Lane 3: The General Med Agent (External Search)

* **Purpose:** Answers general medical context questions.
* **Data Source:** Google Search API / PubMed / Trusted Medical Sites.
* **Example:** "What are the side effects of this medication?" or "Is this treatment standard for diabetes?"
* **Constraint:** PII/PHI must be stripped before hitting this lane.

---

## 3. Implementation Logic Flow

### Step 1: Input & Sanitization

* Receive User Query.
* **PII Masking:** Redact Name/Member ID immediately if the route is external.

### Step 2: Intent Classification (Routing)

* **Logic:**
* If query contains "My plan", "Coverage", "Deductible"  **Route to Plan Agent**.
* If query contains "Draft appeal", "Find doctor", "Check status"  **Route to Action Agent**.
* If query contains "What is [Condition]", "Side effects"  **Route to General Med Agent**.



### Step 3: Execution & Synthesis

* **Plan Agent:** Retrieves chunks  Reranks  LLM Synthesizes with Citations.
* **Action Agent:** Calls API  Returns JSON result  LLM interprets for user.
* **General Agent:** Web Search  Summarizes top 3 medical sources.

---

## 4. Critical Technical Risks & Mitigations

| Risk Area | The Problem | Technical Mitigation |
| --- | --- | --- |
| **Hallucination** | LLM invents coverage benefits. | **Citation Enforcement:** The model must link every claim to a specific PDF page/paragraph. |
| **Terminology** | "Sugar Doctor" vs. "Endocrinologist". | **Query Expansion:** Use an LLM step to translate layperson terms into medical taxonomy before searching. |
| **Stale Data** | Provider directories in PDF are outdated. | **API-First Approach:** Never RAG a directory. Always use a live API tool for provider lookups. |
| **Privacy** | Leaking PHI to public web search. | **Strict Routing Guardrails:** General Web Search lane must have a PII-scrubbing middleware. |

---

## 5. Decision Verdict

**Is Hybrid Architecture Applicable?**
**Yes.** It is mandatory. Relying solely on vector search will fail on exact matches (Plan IDs, CPT Codes). You need a Vector DB + Keyword Index (BM25) + Structured SQL (for benefit tables).

**Is Routing Required?**
**Yes.** Mixing "Plan Logic" with "Google Search" in one context window invites hallucination. Separation of concerns via routing ensures the AI knows when to look at the contract vs. when to look at the world.

---

**Next Step:**
Would you like me to generate the **System Prompt** for the "Router" component so you can test how it classifies different healthcare queries?