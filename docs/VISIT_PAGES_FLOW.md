# How visit pages are displayed (UI + FastAPI)

## Overview

When you **click a visit** in the client, the UI loads that visit’s **page list** from the API, then shows each page by loading **image URLs** that point back to the API. The API reads data from MongoDB and serves image files from disk.

---

## 1. UI flow (therapi-ai-client)

### When a visit is clicked

1. **Click handler** (in `App.jsx`):
   - The visit button calls `onClick={() => setSelectedVisitNumber(v.visitNumber)}`.
   - So `selectedVisitNumber` becomes e.g. `17`.

2. **Effect runs** (same file, `useEffect` with `[selectedFileId, selectedVisitNumber]`):
   - If both `selectedFileId` and `selectedVisitNumber` are set, it calls:
   - `getVisitPages(selectedFileId, selectedVisitNumber)` from `api.js`.

3. **API call** (`api.js`):
   - `getVisitPages(fileId, visitNumber)` does:
   - `GET {API_BASE}/files/{file_id}/visit/{visit_number}`
   - Example: `GET http://localhost:8000/files/69ae87b55a2f19249689e4fc/visit/17`
   - Response is stored in state via `.then(setVisitData)`.

4. **Rendering the section** (when `visitData` is set):
   - The “Visit X pages” section is shown only when `selectedVisitNumber != null` and `visitData` exists.
   - It shows:
     - Visit date: `visitData.visitDate`
     - A scrollable list: `visitData.pages.map(...)`.

5. **Each page in the list**:
   - For each `page` in `visitData.pages`:
     - Image: `<img src={pageImageUrl(visitData.file_id, page.image)} ... />`
     - Label: “Page {page.pageLabel ?? page.pageNumber}”
   - `pageImageUrl(fileId, imagePath)` (in `api.js`) builds:
     - `imagePath` from the API is like `"pages/visit-17-page-1.png"`.
     - It strips the `"pages/"` prefix and builds:
     - `GET {API_BASE}/files/{file_id}/pages/{filename}`
     - Example: `http://localhost:8000/files/69ae87b55a2f19249689e4fc/pages/visit-17-page-1.png`
   - The browser requests that URL for each `<img>`, and the FastAPI server serves the PNG file.

So in the UI:

- **One API call** loads the visit (including the list of pages and their `image` paths).
- **One HTTP request per page image** to the same API (file-serving endpoint).

---

## 2. FastAPI flow (vitafy-ai-v2)

### A. Get visit and page list: `GET /files/{file_id}/visit/{visit_number}`

**Handler:** `get_visit_pages(file_id, visit_number)` in `app/app.py`.

1. Validate `file_id` as MongoDB ObjectId.
2. Load the file document from MongoDB:
   - `files_collection.find_one({"_id": oid}, projection={"name", "status", "result"})`.
3. From `doc["result"]` get the `visits` list (stored when the PDF was processed).
4. Find the visit where `v["visitNumber"] == visit_number`.
5. Return JSON:
   - `file_id`, `document_name`, `visitNumber`, `visitDate`, `pageCount`
   - `pages`: array of `{ pageNumber, pageLabel, image }`, where `image` is like `"pages/visit-17-page-1.png"`.

**Where `result.visits` comes from:** The RQ worker (PDF processor) builds this when processing the PDF: each visit has `visitNumber`, `visitDate`, and `pages` with `pageNumber`, `pageLabel`, and `image: "pages/visit-{N}-page-{M}.png"`. That result is saved in the file document in MongoDB.

---

### B. Serve a page image: `GET /files/{file_id}/pages/{path}`

**Handler:** `serve_visit_page_image(file_id, path)` in `app/app.py`.

1. Validate `file_id` as ObjectId.
2. Ensure `path` is a single filename (no `/` or `..`) to avoid path traversal.
3. Resolve file path on disk:
   - `STORAGE_DIR / "uploads" / file_id / "pages" / path`
   - Example: `./storage/uploads/69ae87b55a2f19249689e4fc/pages/visit-17-page-1.png`
4. Check the resolved path is under the file’s upload directory and that the file exists.
5. Return the file with `FileResponse(..., media_type="image/png")`.

So:

- **Visit endpoint** returns metadata + list of page image paths.
- **Pages endpoint** serves the actual PNG files from `storage/uploads/<file_id>/pages/`.

---

## 3. Data shape (summary)

**From `GET /files/{file_id}/visit/{visit_number}`:**

```json
{
  "file_id": "69ae87b55a2f19249689e4fc",
  "document_name": "example.pdf",
  "visitNumber": 17,
  "visitDate": "2025-01-15",
  "pageCount": 5,
  "pages": [
    { "pageNumber": 1, "pageLabel": 1, "image": "pages/visit-17-page-1.png" },
    { "pageNumber": 2, "pageLabel": 2, "image": "pages/visit-17-page-2.png" }
  ]
}
```

**Page image URL (built in UI):**

- `page.image` = `"pages/visit-17-page-1.png"`
- Final URL = `{API_BASE}/files/{file_id}/pages/visit-17-page-1.png`
- Browser loads that URL → FastAPI serves the file from `storage/uploads/<file_id>/pages/visit-17-page-1.png`.

---

## 4. Flow diagram

```
[User clicks "Visit 17"]
        │
        ▼
setSelectedVisitNumber(17)
        │
        ▼
useEffect([selectedFileId, selectedVisitNumber])
        │
        ▼
getVisitPages(fileId, 17)
        │
        ▼
GET /files/{file_id}/visit/17  ──────────► FastAPI: get_visit_pages()
        │                                    │
        │                                    ├─ MongoDB: find file doc, get result.visits
        │                                    └─ return { visitNumber, visitDate, pages: [...] }
        │
        ▼
setVisitData(response)
        │
        ▼
Render: visitData.pages.map(page => (
  <img src={pageImageUrl(file_id, page.image)} />
))
        │
        │  For each page, browser requests:
        ▼
GET /files/{file_id}/pages/visit-17-page-1.png  ─► FastAPI: serve_visit_page_image()
                                                      │
                                                      └─ FileResponse(storage/uploads/.../pages/visit-17-page-1.png)
```

So: **one call** to get the visit and its page list, then **one request per image** to display the pages.
