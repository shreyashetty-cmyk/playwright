# Doc Formatter Agent — Knowledge Transfer (KT) Document

This document explains the **code structure**, **technologies used**, **how they work together**, and **how to set up the project on a new machine**. Use it when transferring the project (e.g. via zip) to another laptop or onboarding someone new.

---

## 1. What This Project Does (High-Level)

- **Input:** A messy or inconsistent Microsoft Word document (`.docx`).
- **Process:** The backend applies strict formatting rules (font, size, alignment, spacing, headings).
- **Output:** A cleaned `.docx` file that you can download.
- **Ways to trigger:** Manually via Swagger UI in the browser, or automatically via a Playwright script that simulates a user uploading a file and clicking "Execute".

So: **upload → format → download**. The "agent" is the Playwright script that automates the browser part.

---

## 2. Project Structure (Folders and Files)

```
doc_formatter_agent/
│
├── backend/                    # API and formatting logic
│   ├── main.py                 # FastAPI app: upload endpoint, calls formatter, returns file
│   └── formatter.py            # Core logic: reads docx, applies rules, saves new docx
│
├── agent/                      # Browser automation (optional)
│   └── run_agent.py            # Playwright script: opens Swagger, uploads file, clicks Execute
│
├── uploads/                    # Where uploaded files are saved (created at runtime)
├── outputs/                    # Where formatted files are saved (created at runtime)
│
├── requirements.txt            # Python package list
├── README.md                   # Short setup and run instructions
├── KNOWLEDGE_TRANSFER.md       # This document
│
└── .venv/                      # Virtual environment (DO NOT zip this; recreate on new machine)
```

**What to zip when transferring:** Everything **except** `.venv/` (and optionally `__pycache__/`, `uploads/*`, `outputs/*`). On the new laptop you recreate the venv and run `pip install -r requirements.txt` and `playwright install`.

**Where is Playwright?** Playwright is used **only** in **`agent/run_agent.py`**. That script opens the browser, goes to Swagger UI, clicks "Try it out", selects the file, clicks "Execute", and saves the response. The backend (`main.py`, `formatter.py`) does **not** use Playwright.

---

## 3. Technology Stack — What It Uses and Why

| Component | Technology | Purpose |
|-----------|------------|--------|
| **Web framework** | FastAPI | Expose HTTP API (e.g. `POST /format`), automatic OpenAPI/Swagger UI, async support, type hints. |
| **ASGI server** | Uvicorn | Runs the FastAPI app; `--reload` for development. |
| **Document handling** | python-docx | Read/write `.docx` files (paragraphs, runs, fonts, alignment, spacing) without Microsoft Word. |
| **File upload (HTTP)** | python-multipart | Lets FastAPI parse `multipart/form-data` (file uploads). |
| **Browser automation** | Playwright | Drives a real browser (Chromium) to open Swagger, set file input, click Execute — simulates user. |

**Why these choices:** FastAPI + Uvicorn is a common, simple stack for APIs; python-docx is the standard way to manipulate Word docs in Python; Playwright gives reliable, modern browser automation for the "agent" part.

### 3.1 Role of Playwright

Playwright is **not** used for formatting documents. Its role is **browser automation** only:

| Role | What it does |
|------|----------------|
| **Trigger the API without manual clicks** | You can run `python run_agent.py` and the script opens the docs page, selects a file, and clicks Execute so you don’t have to do that in the browser. |
| **Demo / testing** | Useful to show “one click” formatting or to automate tests against the Swagger UI. |
| **Alternative to curl/Postman** | If you prefer not to call the API with curl or another client, the Playwright script acts as a client that uses the same UI a human would. |

The **formatting logic** (font, headings, margins, underlining, etc.) lives entirely in **`backend/formatter.py`**. The backend can be used with or without Playwright: you can always call `POST /format` from Swagger, curl, or another app. Playwright is an optional way to **drive that same API through the browser**.

### 3.2 More ways to use Playwright

You can use Playwright for more than a single-file run:

| Option | What it does | Where |
|--------|----------------|------|
| **Batch formatting** | Format multiple `.docx` files in one run (folder or list of files). The agent reuses the same browser tab: for each file, upload → Execute → save with a unique name. | `agent/run_agent.py` (pass files or a folder path) |
| **One-command run** | Start the FastAPI backend in the background, wait until it’s ready, run the Playwright agent, then exit. One script does “start server + format” so you don’t open two terminals. | `agent/run_all.py` |
| **E2E testing** | Use Playwright in tests to open `/docs`, upload a fixture file, click Execute, and assert the response (status, filename, or file size). | e.g. `tests/test_agent_flow.py` (you can add this) |
| **Custom upload UI** | Build a simple HTML page (e.g. served by FastAPI) with drag‑and‑drop; use Playwright to automate that UI for demos or batch runs. | Requires adding a page and routes in the backend |
| **Screenshots / PDF** | After formatting, open a “result” page or the downloaded file in a viewer and use Playwright to take a screenshot or print to PDF. | Requires a way to render the result in the browser |

**Implemented in this project:** batch formatting (multiple files or a folder) and a one-command runner (`run_all.py`).

---

## 4. In-Depth Code Structure and Flow

### 4.1 End-to-end request flow

1. **User or agent** sends `POST /format` with a file (e.g. `sample.docx`) in the body as `multipart/form-data`.
2. **main.py** receives the file, saves it under `uploads/`, calls `format_document(upload_path, output_path)`.
3. **formatter.py** opens the docx, iterates over every paragraph, applies font/alignment/spacing rules, saves to `outputs/formatted_<filename>.docx`.
4. **main.py** returns that file as the HTTP response (download).

So: **main.py** = HTTP layer; **formatter.py** = document logic.

---

## 5. File-by-File Deep Dive

### 5.1 `backend/formatter.py` — Formatting engine

**Role:** Pure document logic. No HTTP, no paths beyond what it’s given. It reads one `.docx`, applies rules, writes another `.docx`.

**Imports:**

- `Document` from `docx`: opens/saves docx and gives access to `doc.paragraphs`.
- `Pt` from `docx.shared`: font size and spacing in points.
- `WD_ALIGN_PARAGRAPH` from `docx.enum.text`: left/justify alignment constants.
- `qn` from `docx.oxml.ns`: XML qualified names for Word’s internal structure (e.g. East Asian font).

**Key concepts in Word (python-docx):**

- **Document:** One `.docx` file.
- **Paragraph:** A block of text (one or more lines) ending with a paragraph break.
- **Run:** A contiguous span of text with the same formatting. One paragraph can have multiple runs (e.g. bold word in the middle).

**Functions:**

1. **`apply_global_style(run, size=12, bold=False)`**
   - Takes a single **run** and sets:
     - `run.font.name = "Times New Roman"` — Latin font.
     - `run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")` — East Asian font (so CJK and other scripts also use Times New Roman where applicable).
     - `run.font.size = Pt(size)` — font size in points.
     - `run.bold = bold`.
   - So all visible text is forced to Times New Roman, fixed size, and optional bold.

2. **`format_document(input_path, output_path)`**
   - `doc = Document(input_path)` — open the uploaded file.
   - For each **paragraph** in `doc.paragraphs`:
     - `text = para.text.strip()` — full paragraph text, trimmed.
     - If `text` is empty: `para.clear()` and skip (removes empty paragraphs / extra blank lines).
     - **Heading heuristic:** if `text.isupper()` OR `len(text) < 40` → treat as heading:
       - Set style to Normal, alignment LEFT.
       - For each run in the paragraph: `apply_global_style(run, size=14, bold=True)`.
     - **Else** → body:
       - Alignment JUSTIFY.
       - For each run: `apply_global_style(run, size=12)`.
     - Then for **every** non-empty paragraph: set `space_before`, `space_after` to 0 pt, and `line_spacing` to 1.5.
   - `doc.save(output_path)` — write the result to `outputs/formatted_<name>.docx`.

**Summary:** One function styles runs (font/size/bold); the other walks paragraphs, classifies heading vs body, applies that style, and normalizes spacing. All edits are in-memory until `doc.save()`.

---

### 5.2 `backend/main.py` — FastAPI application

**Role:** HTTP API: receive file, save it, call formatter, return the formatted file. Also ensures `uploads/` and `outputs/` exist.

**Imports:**

- `os`: path joining and `makedirs`.
- `FastAPI`, `UploadFile`, `File`: app, file parameter, and declaring file input.
- `FileResponse`: to stream the generated file back as the response.
- `format_document`: from the local `formatter` module.

**Constants:**

- `UPLOAD_DIR = "uploads"`, `OUTPUT_DIR = "outputs"`.
- Directories are created at startup with `os.makedirs(..., exist_ok=True)`. Paths are relative to the process current working directory (so you must run from `backend/` or set cwd accordingly).

**Single endpoint: `POST /format`**

- **Parameter:** `file: UploadFile = File(...)` — one required file in the request body (multipart/form-data). FastAPI + python-multipart parse it.
- **Logic:**
  1. `input_path = os.path.join(UPLOAD_DIR, file.filename)` — e.g. `uploads/sample.docx`.
  2. `output_path = os.path.join(OUTPUT_DIR, f"formatted_{file.filename}")` — e.g. `outputs/formatted_sample.docx`.
  3. `await file.read()` then write to `input_path` — persist uploaded file to disk.
  4. `format_document(input_path, output_path)` — run the formatting engine (synchronous).
  5. `return FileResponse(output_path, media_type="...", filename=f"formatted_{file.filename}")` — send the file so the client gets a download named `formatted_sample.docx`.

**Important:** The server reads from and writes to paths under `backend/` if you run uvicorn from `backend/`. So `uploads/` and `outputs/` are created next to `main.py` unless you change working directory or use absolute paths.

---

### 5.3 `agent/run_agent.py` — Browser automation (Playwright)

**Role:** Simulate a user: open Swagger UI, choose a file, click Execute. Used for demos or automation; not required for the API itself.

**Imports:**

- `sync_playwright` from `playwright.sync_api`: context manager to start/stop Playwright and use the synchronous API.

**Constant:**

- `FILE_TO_UPLOAD = "sample.docx"` — must exist in the **current working directory** when you run the script (typically `agent/`). So you need a file named `sample.docx` in the `agent/` folder (or you change the path).

**Flow:**

1. `sync_playwright()` → start Playwright.
2. `p.chromium.launch(headless=False)` — open a visible Chromium window.
3. `browser.new_page()` — one tab.
4. `page.goto("http://127.0.0.1:8000/docs")` — open FastAPI’s Swagger UI (must have backend running on port 8000).
5. `page.set_input_files('input[type="file"]', FILE_TO_UPLOAD)` — find the file input in Swagger and set its file to `sample.docx` (path relative to cwd).
6. `page.click("text=Execute")` — click the Execute button.
7. `page.wait_for_timeout(5000)` — wait 5 seconds so the download can complete (browser may download the file to the default Downloads folder).
8. `browser.close()`.

**Dependency:** Backend must be running at `http://127.0.0.1:8000`. The script does not start the server; it only drives the browser.

---

### 5.4 `requirements.txt`

```
fastapi
uvicorn
python-docx
playwright
python-multipart
```

- **fastapi** — web framework.
- **uvicorn** — ASGI server to run the app.
- **python-docx** — create/read/update `.docx`.
- **playwright** — browser automation (used only by `agent/run_agent.py`).
- **python-multipart** — required by FastAPI to accept `multipart/form-data` (file uploads).

After `pip install -r requirements.txt` you must run `playwright install` once to download the browser binaries (e.g. Chromium).

---

## 6. How the Pieces Work Together

- **Formatter** is independent: given two paths, it reads one docx and writes another. No knowledge of HTTP or uploads.
- **Main** is the only HTTP layer: it receives the file, decides paths, calls the formatter, and returns the result. It uses the formatter as a black box.
- **Agent** is a client: it does not import the backend; it only talks to it via the browser and the same API a human would use (Swagger).

So you can:
- Use the API from curl, Postman, or another app without running the agent.
- Change formatting rules only in `formatter.py` without touching `main.py` or the agent.
- Replace the agent with another client (e.g. another script that uses `requests` to POST the file) without changing the backend.

---

## 7. Setup on a New Laptop (After Transfer)

1. **Unzip** the project (excluding `.venv` if you didn’t zip it).
2. **Terminal:** go to project root.
   ```bash
   cd /path/to/doc_formatter_agent
   ```
3. **Create and activate virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```
4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install
   ```
5. **Run backend** (from project root or from `backend/`):
   ```bash
   cd backend
   uvicorn main:app --reload
   ```
   Swagger: `http://127.0.0.1:8000/docs`
6. **Optional — run agent:** In another terminal, with venv activated and a `sample.docx` in `agent/`:
   ```bash
   cd agent
   python run_agent.py
   ```

**Common issues:**

- **Import error for `formatter`:** Run uvicorn from the `backend/` directory so `formatter` is on the module path.
- **Playwright "browser not found":** Run `playwright install` after pip install.
- **Agent can’t find file:** Put `sample.docx` in `agent/` or set `FILE_TO_UPLOAD` to an absolute path.

---

## 8. Extension Points (For Your Knowledge)

- **Formatting rules:** All in `formatter.py`. You can add more paragraph types, regex-based heading detection, or margins/page setup.
- **New API endpoints:** Add in `main.py` (e.g. health check, list of formatted files); keep file I/O and formatting in formatter or a separate module.
- **AI/LLM:** Could add a step before or inside `format_document` that uses an LLM to classify paragraphs (e.g. title, heading, body, caption) then apply styles accordingly.
- **Batch processing:** In `main.py`, accept multiple files or a zip, loop over them, call `format_document` for each, return a zip of formatted files.
- **Agent:** You could use `requests` to POST the file to `http://127.0.0.1:8000/format` and save the response to disk instead of using Playwright, if you don’t need browser UI automation.

---

## 9. Quick Reference

| What | Where |
|------|--------|
| Change font/size/alignment/spacing rules | `backend/formatter.py` |
| Add/change API routes or upload behavior | `backend/main.py` |
| Change automation steps (e.g. different URL, different button) | `agent/run_agent.py` |
| Add Python dependencies | `requirements.txt` then `pip install -r requirements.txt` |
| Uploaded files on disk | `backend/uploads/` (when run from `backend/`) |
| Formatted files on disk | `backend/outputs/` |

---

This document is the **in-depth code structure, what the project uses, and how it uses it** for knowledge transfer to another laptop or team member. For short run instructions, use `README.md`.
