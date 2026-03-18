# process_pdf Flowchart

Flow for `PDFTextProcessor.process_pdf(id, file_path)` — splitting a PDF into visit-based page images using vision (Gemini/OpenAI) to detect Visit #, Visit Date, and Page # on each page.

```mermaid
flowchart TB
    A([Start process_pdf]) --> B[Open PDF with fitz]
    B --> C[Create pages_dir, init visits_dict, buffer_pages, current_visit = None]
    C --> D["For each page i = 0 .. total_pages-1"]

    D -->|next page| E[Update DB: status = page i+1/total_pages]
    E --> F[Render page → temp_i.png, encode to base64]
    F --> G["_detect_visit_from_image() → visit_number, visit_date, page_number"]

    G --> H{visit_number None &<br/>visit_date None &<br/>current_visit None?}
    H -->|Yes| I["CASE 1: Skip"]
    I --> I1[Delete temp image]
    I1 --> D

    H -->|No| J{visit_number None &<br/>visit_date present &<br/>current_visit None?}
    J -->|Yes| K["CASE 2: Buffer"]
    K --> K1[Append to buffer_pages]
    K1 --> D

    J -->|No| L{visit_number present?}
    L -->|Yes| M["CASE 3: New visit"]
    M --> M1[Set current_visit_number, current_visit_date]
    M1 --> M2{Buffer not empty?}
    M2 -->|Yes| M3[Flush buffer: rename → visit-N-page-L.png, add to visits_dict]
    M3 --> M4[Clear buffer_pages]
    M2 -->|No| M4
    M4 --> M5[Rename current page → visit-N-page-L.png, add to visits_dict]
    M5 --> D

    L -->|No| N{current_visit set &<br/>visit_date ≠ current_visit_date?}
    N -->|Yes| O["CASE 4: New segment"]
    O --> O1[Reset current_visit, clear state]
    O1 --> O2[Append page to buffer_pages]
    O2 --> D

    N -->|No| P["CASE 5: Continuation"]
    P --> P1[current_visit set]
    P1 --> P2[Rename → visit-current-page-L.png, append to visits_dict]
    P2 --> D

    D -->|no more pages| Q[Build visits_result from visits_dict]
    Q --> R[Update DB: status=completed, result]
    R --> S([Return result_data])
```

## Case summary

| Case | Condition | Action |
|------|-----------|--------|
| **1** | `visit_number` and `visit_date` and `current_visit_number` all None | Skip page (delete temp image). |
| **2** | `visit_date` present, `visit_number` None, no current visit | Buffer page (wait for a page that has visit number). |
| **3** | `visit_number` present | Start/continue that visit: flush buffer into this visit, save current page as visit-N-page-L.png, add to `visits_dict`. |
| **4** | No visit number, current visit set, but `visit_date` is different from current | New segment: reset state, buffer this page. |
| **5** | No visit number, current visit set (same segment) | Continuation: save as visit-current-page-L.png, append to current visit’s pages. |

## Data flow

- **buffer_pages**: Pages that have a visit date but no visit number yet; assigned to a visit when a later page supplies the visit number (Case 3).
- **visits_dict**: `{ visit_number → { visitDate, pages: [{ pageNumber, pageLabel, image }] } }`.
- **current_visit_number / current_visit_date**: Track the “active” visit for continuation (Case 5) and new-segment detection (Case 4).
