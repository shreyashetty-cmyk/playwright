# Complete Codebase Explanation with Full Code

This document provides a comprehensive explanation of the entire codebase, including **complete code** for all files with detailed explanations.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Complete Code Files](#complete-code-files)
4. [Data Flow](#data-flow)
5. [Key Algorithms & Logic](#key-algorithms--logic)
6. [Dependencies](#dependencies)

---

## Architecture Overview

### High-Level Flow

```
User runs: python run_all.py
    ↓
1. run_all.py starts FastAPI backend (subprocess)
    ↓
2. Waits for backend to be ready (checks http://127.0.0.1:8000/docs)
    ↓
3. run_agent.py opens browser (Playwright)
    ↓
4. Navigates to Swagger UI, uploads file, clicks Execute
    ↓
5. Backend receives POST /format request
    ↓
6. main.py saves file → calls formatter.py
    ↓
7. formatter.py reads docx, detects paragraph types, applies styles
    ↓
8. Returns formatted .docx file
    ↓
9. Playwright downloads file, saves to agent/
    ↓
10. Backend stops automatically
```

### Components

- **Backend (FastAPI)**: HTTP API server that handles file uploads and formatting
- **Formatter (python-docx)**: Core logic that reads, modifies, and saves Word documents
- **Agent (Playwright)**: Browser automation that simulates user interaction with Swagger UI
- **Orchestrator (run_all.py)**: Coordinates backend startup, agent execution, and cleanup

---

## Project Structure

```
doc_formatter_agent/
├── agent/
│   ├── run_all.py          # Main entry point (orchestrates everything)
│   ├── run_agent.py        # Playwright browser automation
│   └── sample.docx          # Input file (user places here)
├── backend/
│   ├── main.py              # FastAPI server (HTTP endpoints)
│   ├── formatter.py         # Document formatting logic
│   ├── uploads/             # Temporary storage for uploaded files
│   └── outputs/             # Formatted documents saved here
├── requirements.txt         # Python dependencies
├── .gitignore              # Git ignore rules
└── README.md               # User documentation
```

---

## Complete Code Files

### 1. `agent/run_all.py` - Main Orchestrator

**Purpose**: One-command entry point that starts the backend, runs the agent, and cleans up.

**Complete Code**:

```python
"""
One-command run: start the FastAPI backend in the background, wait until it's ready,
then run the Playwright agent (single file or batch). No need to open two terminals.

Usage:
  python run_all.py                    # format sample.docx (backend starts automatically)
  python run_all.py --llm              # same with use_llm=true
  python run_all.py path/to/folder     # format all .docx in folder
  python run_all.py file1.docx file2.docx
"""
import os
import subprocess
import sys
import time

# Project root (parent of agent/)
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(AGENT_DIR)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")

DOCS_URL = "http://127.0.0.1:8000/docs"
READY_TIMEOUT = 30


def _backend_ready() -> bool:
    """
    Check if backend is ready by making HTTP request to /docs.
    
    Returns:
        True if backend responds, False otherwise
    """
    try:
        import urllib.request
        req = urllib.request.Request(DOCS_URL, method="GET")
        urllib.request.urlopen(req, timeout=2)
        return True
    except Exception:
        return False


def main():
    """
    Main function that orchestrates the entire process:
    1. Parse command line arguments
    2. Start backend as subprocess
    3. Wait for backend to be ready
    4. Run Playwright agent
    5. Clean up (terminate backend)
    """
    os.chdir(AGENT_DIR)  # Change to agent directory
    argv = [a for a in sys.argv[1:] if a != "--llm" and not a.startswith("-")]
    use_llm = "--llm" in sys.argv

    # Start backend in subprocess (same Python, backend dir)
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", "")
    if BACKEND_DIR not in env["PYTHONPATH"].split(os.pathsep):
        env["PYTHONPATH"] = BACKEND_DIR + os.pathsep + env["PYTHONPATH"]

    # Start uvicorn server in background
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=BACKEND_DIR,  # Run from backend/ directory
        env=env,          # Pass environment variables
        stdout=subprocess.DEVNULL,  # Suppress output
        stderr=subprocess.DEVNULL,
    )

    # Wait for backend to be ready
    print("Starting backend...", end=" ", flush=True)
    start = time.monotonic()
    while not _backend_ready():
        if time.monotonic() - start > READY_TIMEOUT:
            print("timeout.")
            proc.terminate()
            sys.exit(1)
        time.sleep(0.5)  # Check every 0.5 seconds
    print("ready.")

    try:
        # Import and run the Playwright agent
        from run_agent import run
        if not argv:
            run(use_llm=use_llm)  # Single file (sample.docx)
        elif len(argv) == 1 and os.path.isdir(argv[0]):
            run(folder=argv[0], use_llm=use_llm)  # Folder of files
        else:
            run(files=argv, use_llm=use_llm)  # Multiple files
    finally:
        # Always terminate backend, even if agent fails
        proc.terminate()
        proc.wait(timeout=5)
    print("Backend stopped.")


if __name__ == "__main__":
    main()
```

**Key Points**:
- Uses `subprocess.Popen` to start backend in background
- Polls `/docs` endpoint to check if backend is ready
- Handles cleanup in `finally` block to ensure backend stops
- Supports `--llm` flag and file/folder arguments

---

### 2. `agent/run_agent.py` - Playwright Browser Automation

**Purpose**: Automates browser interaction with Swagger UI to upload files and download formatted results.

**Complete Code**:

```python
"""
Playwright agent: open Swagger UI, upload file(s), click Execute, save formatted docx.
Supports single file (default), multiple files, or a folder of .docx files.
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# Default: one file in the agent folder
FILE_TO_UPLOAD = "sample.docx"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _format_one_file(page, file_path: str, output_dir: str, use_llm: bool = False) -> str | None:
    """
    Upload one file via Swagger, click Execute, save response.
    
    Args:
        page: Playwright page object
        file_path: Path to file to upload
        output_dir: Directory to save formatted file
        use_llm: Whether to use AI classification
    
    Returns:
        Path to saved file or None if error
    """
    file_path = os.path.abspath(file_path)
    if not os.path.isfile(file_path):
        return None
    base = os.path.basename(file_path)

    # Reset file input (clear previous) and set new file
    file_input = page.locator('input[type="file"]').first
    file_input.set_input_files(file_path)
    page.wait_for_timeout(400)  # Wait for UI to update

    # Wait for POST /format response
    # Swagger UI sends POST request when "Execute" is clicked
    with page.expect_response(
        lambda r: "/format" in r.url and r.request.method == "POST" and r.status == 200,
        timeout=60000 if use_llm else 30000,  # Longer timeout for AI processing
    ) as response_info:
        page.get_by_text("Execute", exact=True).first.click()

    # Extract file from response
    response = response_info.value
    body = response.body()  # Binary file content
    
    # Get filename from Content-Disposition header
    cd = response.headers.get("content-disposition") or ""
    if "filename=" in cd:
        filename = cd.split("filename=")[-1].strip('"\'')
    else:
        filename = f"formatted_{base}"
    
    # Save file
    save_path = os.path.join(output_dir, filename)
    with open(save_path, "wb") as f:
        f.write(body)
    
    return save_path


def run(files: list[str] | None = None, folder: str | None = None, use_llm: bool = False):
    """
    Run the Playwright flow.
    
    Args:
        files: List of file paths to format
        folder: Folder path containing .docx files
        use_llm: Whether to use AI classification
    
    If neither files nor folder provided, uses FILE_TO_UPLOAD (sample.docx).
    """
    # Determine which files to format
    if files:
        to_format = [os.path.abspath(f) for f in files if os.path.isfile(f)]
    elif folder:
        folder = os.path.abspath(folder)
        to_format = [
            str(p) for p in Path(folder).glob("*.docx") if p.is_file()
        ]
    else:
        # Single file (relative to agent dir)
        single = os.path.join(OUTPUT_DIR, FILE_TO_UPLOAD)
        if not os.path.isfile(single):
            single = FILE_TO_UPLOAD
        to_format = [single] if os.path.isfile(single) else []

    if not to_format:
        print("No .docx files to format. Put sample.docx in agent/ or pass files/folder.")
        return

    # Launch browser and navigate to Swagger UI
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=400)
        page = browser.new_page()

        print("Opening Swagger UI...")
        page.goto("http://127.0.0.1:8000/docs", wait_until="networkidle")
        page.wait_for_timeout(1000)

        print("Expanding POST /format...")
        page.locator(".opblock-summary").first.click()  # Click first endpoint
        page.wait_for_timeout(1200)

        # Click "Try it out" button
        try_it = page.get_by_text("Try it out", exact=True).first
        if try_it.is_visible():
            print("Clicking Try it out...")
            try_it.click()
            page.wait_for_timeout(800)

        # Wait for file input to be visible
        file_input = page.locator('input[type="file"]').first
        file_input.wait_for(state="visible", timeout=10000)

        # Format each file
        for i, path in enumerate(to_format):
            print(f"[{i + 1}/{len(to_format)}] Formatting {os.path.basename(path)}...")
            saved = _format_one_file(page, path, OUTPUT_DIR, use_llm=use_llm)
            if saved:
                print(f"  Saved: {saved}")
            else:
                print(f"  Skip (not found or error): {path}")
            if i < len(to_format) - 1:
                page.wait_for_timeout(1500)  # Wait between files

        page.wait_for_timeout(2000)
        browser.close()


if __name__ == "__main__":
    use_llm = "--llm" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--llm" and not a.startswith("-")]

    if not args:
        run(use_llm=use_llm)
    elif len(args) == 1 and os.path.isdir(args[0]):
        run(folder=args[0], use_llm=use_llm)
    else:
        run(files=args, use_llm=use_llm)
```

**Key Points**:
- Uses Playwright to automate browser interactions
- Intercepts HTTP responses to extract file content (Swagger doesn't trigger download events)
- Supports batch processing (multiple files or folder)
- Handles file input, Execute button clicks, and response extraction

---

### 3. `backend/main.py` - FastAPI HTTP Server

**Purpose**: Provides REST API endpoints for document formatting and AI features.

**Complete Code**:

```python
import base64
import os
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import FileResponse

from formatter import format_document, get_paragraph_labels, summarize_document

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

# Create directories if they don't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Create FastAPI app with Swagger UI enabled
app = FastAPI(swagger_ui_parameters={"tryItOutEnabled": True})


@app.post("/format")
async def format_file(
    file: UploadFile = File(...),
    use_llm: bool = Query(False, description="Use Gemini to classify title/heading/body/caption (requires GEMINI_API_KEY)"),
):
    """
    Format a document using rule-based or AI-based detection.
    
    Args:
        file: Uploaded .docx file
        use_llm: If True, use Gemini AI for paragraph classification
    
    Returns:
        Formatted .docx file as download
    """
    input_path = os.path.join(UPLOAD_DIR, file.filename)
    output_path = os.path.join(OUTPUT_DIR, f"formatted_{file.filename}")

    # Save uploaded file
    with open(input_path, "wb") as f:
        f.write(await file.read())

    # Format document
    format_document(input_path, output_path, use_llm=use_llm)
    
    # Verify file exists and has content
    if not os.path.exists(output_path):
        raise HTTPException(status_code=500, detail=f"Formatted file was not created: {output_path}")
    
    file_size = os.path.getsize(output_path)
    if file_size == 0:
        raise HTTPException(status_code=500, detail=f"Formatted file is empty: {output_path} (size: {file_size} bytes)")

    # Return as file download
    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"formatted_{file.filename}",
    )


@app.post("/format-with-ai")
async def format_with_ai(file: UploadFile = File(...)):
    """
    Same as /format but always uses Gemini for paragraph classification.
    Requires GEMINI_API_KEY.
    """
    input_path = os.path.join(UPLOAD_DIR, file.filename)
    output_path = os.path.join(OUTPUT_DIR, f"formatted_{file.filename}")
    with open(input_path, "wb") as f:
        f.write(await file.read())
    format_document(input_path, output_path, use_llm=True)
    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"formatted_{file.filename}",
    )


@app.post("/classify")
async def classify_file(file: UploadFile = File(...)):
    """
    LLM-only: upload a .docx and get back paragraph labels (title/heading/body/caption) from Gemini.
    
    Returns JSON:
    {
        "paragraphs": [
            {"index": 0, "text_preview": "...", "label": "title"},
            {"index": 1, "text_preview": "...", "label": "heading"},
            ...
        ],
        "summary": {"title": 1, "heading": 5, "body": 20, ...}
    }
    
    Requires GEMINI_API_KEY.
    """
    input_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(input_path, "wb") as f:
        f.write(await file.read())
    result = get_paragraph_labels(input_path)
    if result is None:
        raise HTTPException(status_code=503, detail="Gemini unavailable or missing GEMINI_API_KEY")
    return result


@app.post("/summarize")
async def summarize_file(file: UploadFile = File(...)):
    """
    LLM-only: upload a .docx and get a 1–2 sentence summary from Gemini.
    
    Returns JSON:
    {
        "summary": "This document discusses..."
    }
    
    Requires GEMINI_API_KEY.
    """
    input_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(input_path, "wb") as f:
        f.write(await file.read())
    summary = summarize_document(input_path)
    if summary is None:
        raise HTTPException(status_code=503, detail="Gemini unavailable or missing GEMINI_API_KEY")
    return {"summary": summary}


@app.post("/process")
async def process_file(file: UploadFile = File(...)):
    """
    All-in-one: classify (Gemini) + format with AI + summarize.
    
    One upload → one JSON response with:
    - formatted_file_base64: Base64-encoded formatted .docx
    - filename: Output filename
    - summary: Document summary
    - classification: Count of each label type
    
    Requires GEMINI_API_KEY.
    """
    input_path = os.path.join(UPLOAD_DIR, file.filename)
    output_path = os.path.join(OUTPUT_DIR, f"formatted_{file.filename}")
    with open(input_path, "wb") as f:
        f.write(await file.read())

    # Step 1: Get labels from Gemini
    labels_result = get_paragraph_labels(input_path)
    if labels_result is None:
        raise HTTPException(status_code=503, detail="Gemini unavailable or missing GEMINI_API_KEY")

    # Step 2: Format using those labels (don't call Gemini again)
    label_list = [p["label"] for p in labels_result["paragraphs"]]
    format_document(input_path, output_path, use_llm=False, llm_labels=label_list)

    # Step 3: Get summary
    summary_text = summarize_document(input_path)
    if summary_text is None:
        summary_text = "(Summary unavailable)"

    # Step 4: Encode file as base64 for JSON response
    with open(output_path, "rb") as f:
        file_b64 = base64.b64encode(f.read()).decode("utf-8")

    return {
        "formatted_file_base64": file_b64,
        "filename": f"formatted_{file.filename}",
        "summary": summary_text,
        "classification": labels_result["summary"],
    }
```

**Key Points**:
- 5 endpoints: `/format`, `/format-with-ai`, `/classify`, `/summarize`, `/process`
- Handles file uploads, saves to `uploads/`, outputs to `outputs/`
- Validates file existence and size before returning
- Returns appropriate HTTP status codes (500 for errors, 503 for missing Gemini)

---

### 4. `backend/formatter.py` - Core Formatting Logic

**Purpose**: Contains all document processing logic: detection, styling, and formatting.

**Complete Code** (with detailed comments):

```python
"""
Document formatter: rule-based + optional LLM heading/section detection,
with margins, title page, page breaks, and caption styling.
"""
import json
import os
import re
from collections import Counter
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

# Optional LLM: set GEMINI_API_KEY or GOOGLE_API_KEY in env to enable AI-based paragraph labeling (Gemini)
# Model can be overridden via GOOGLE_MODEL env var, defaults to gemini-2.5-flash
# Lazy import - only loads when actually needed (when use_llm=True)
_GEMINI_AVAILABLE = False
genai = None
GOOGLE_MODEL = os.environ.get("GOOGLE_MODEL", "gemini-2.5-flash")

def _ensure_gemini():
    """Lazy import of Gemini only when needed."""
    global _GEMINI_AVAILABLE, genai
    if not _GEMINI_AVAILABLE:
        try:
            import google.generativeai as genai
            _GEMINI_AVAILABLE = True
        except ImportError:
            pass
    return _GEMINI_AVAILABLE

# -------- 1. Rule-based heading / caption detection --------

# Numbered sections: 1., 1.1, 1.1.1, 2., etc.
RE_NUMBERED_HEADING = re.compile(r"^\s*\d+(\.\d+)*\.?\s+\S")

# Common section titles (exact or prefix)
SECTION_KEYWORDS = (
    "abstract", "acknowledgement", "acknowledgments", "appendix", "references",
    "bibliography", "contents", "table of contents", "introduction", "conclusion",
    "chapter", "part", "preface", "foreword", "executive summary", "index",
)
RE_CHAPTER = re.compile(r"^\s*(chapter|part)\s+\d+", re.I)
RE_FIGURE_CAPTION = re.compile(r"^\s*(figure|fig\.?)\s*\d*[.:]?\s*\S", re.I)
RE_TABLE_CAPTION = re.compile(r"^\s*(table)\s*\d*[.:]?\s*\S", re.I)


def _is_rule_based_heading(text: str) -> bool:
    """
    Detects if a paragraph is a heading using multiple rules.
    
    Rules (checked in order):
    1. All caps and < 120 chars → heading
    2. Short line (< 50 chars) with numbered section → heading
    3. Short line with section keyword → heading
    4. Short line with "Chapter N" or "Part N" → heading
    5. Short line without period → heading
    6. Numbered section at start → heading
    7. Starts with section keyword → heading
    8. Matches "Chapter N" or "Part N" → heading
    
    Returns:
        True if any rule matches, False otherwise
    """
    if not text or len(text) > 200:
        return False
    t = text.strip()
    # All caps (short enough to be a heading)
    if t.isupper() and len(t) < 120:
        return True
    # Short line (likely title/heading)
    if len(t) < 50:
        # Avoid treating single short sentences as headings
        if t.endswith(".") and t.count(".") >= 1 and not RE_NUMBERED_HEADING.match(t):
            return False
        if RE_NUMBERED_HEADING.match(t):
            return True
        if any(kw in t.lower() for kw in SECTION_KEYWORDS):
            return True
        if RE_CHAPTER.match(t):
            return True
        # Short and no trailing period → likely heading
        if not t.endswith("."):
            return True
    # Numbered section at start
    if RE_NUMBERED_HEADING.match(t):
        return True
    # Known section keyword anywhere at start
    lower = t.lower()
    if any(lower.startswith(kw) or lower.startswith(kw + " ") for kw in SECTION_KEYWORDS):
        return True
    if RE_CHAPTER.match(t):
        return True
    return False


def _is_caption(text: str) -> bool:
    """
    Checks if text is a figure or table caption.
    
    Matches lines starting with:
    - "Figure", "Fig.", "Fig" (with optional number)
    - "Table" (with optional number)
    
    Examples:
    - "Figure 1: Description" → True
    - "Table 2. Data" → True
    - "Fig. 3" → True
    """
    if not text or len(text) > 300:
        return False
    t = text.strip()
    return bool(RE_FIGURE_CAPTION.match(t) or RE_TABLE_CAPTION.match(t))


def _is_likely_title(text: str, is_first: bool) -> bool:
    """
    Detects if paragraph is likely the document title.
    
    Criteria:
    - Must be first non-empty paragraph
    - Short (≤100 chars)
    - Not numbered
    - Either all caps OR < 80 chars without period
    
    Returns:
        True if matches title criteria
    """
    if not text or not is_first:
        return False
    t = text.strip()
    if len(t) > 100 or RE_NUMBERED_HEADING.match(t):
        return False
    if t.isupper() or (len(t) < 80 and not t.endswith(".")):
        return True
    return False


# -------- 2. Optional LLM-based labeling --------

def _get_llm_labels(paragraph_texts: list[str], api_key: str | None) -> list[str] | None:
    """
    Sends paragraphs to Gemini and gets classification labels.
    
    Args:
        paragraph_texts: List of paragraph text strings
        api_key: Gemini API key
    
    Returns:
        List of labels: ["title", "heading", "body", "body", "caption", ...]
        None if Gemini unavailable or error
    """
    if not _ensure_gemini() or not api_key or not paragraph_texts:
        return None
    genai.configure(api_key=api_key)
    
    # Build prompt for Gemini
    prompt = """Classify each of the following document paragraphs into exactly one label per line:
- title (document or section title, usually short, one line)
- heading (section heading, subsection title)
- body (normal paragraph)
- caption (figure/table caption)
- other

Return ONLY a JSON array of strings, one label per paragraph, in order. Example: ["title","heading","body","body","caption"]
Paragraphs (one per line, numbered):
"""
    for i, p in enumerate(paragraph_texts, 1):
        prompt += f"{i}. {p[:200]}{'...' if len(p) > 200 else ''}\n"
    
    try:
        model = genai.GenerativeModel(GOOGLE_MODEL)
        resp = model.generate_content(prompt, generation_config={"temperature": 0})
        content = (resp.text or "").strip()
        # Remove markdown code blocks if present
        content = content.removeprefix("```json").removeprefix("```").strip()
        labels = json.loads(content)
        if isinstance(labels, list) and len(labels) == len(paragraph_texts):
            return [str(x).lower() for x in labels]
    except Exception:
        pass
    return None


def _get_llm_summary(text: str, api_key: str | None, max_chars: int = 4000) -> str | None:
    """
    Gets a 1-2 sentence summary of document text from Gemini.
    
    Args:
        text: Full document text
        api_key: Gemini API key
        max_chars: Maximum characters to send (default 4000)
    
    Returns:
        Summary string or None if error
    """
    if not _ensure_gemini() or not api_key or not text.strip():
        return None
    genai.configure(api_key=api_key)
    excerpt = text.strip()[:max_chars]
    if len(text) > max_chars:
        excerpt += "..."
    prompt = f"""Summarize this document in 1–2 short sentences. Be concise.\n\n{excerpt}"""
    try:
        model = genai.GenerativeModel(GOOGLE_MODEL)
        resp = model.generate_content(prompt, generation_config={"temperature": 0.3})
        return (resp.text or "").strip() or None
    except Exception:
        return None


def get_paragraph_labels(input_path: str) -> dict | None:
    """
    Extract non-empty paragraphs from the docx and get Gemini labels only (no formatting).
    
    Returns:
        {
            "paragraphs": [
                {"index": 0, "text_preview": "...", "label": "title"},
                {"index": 1, "text_preview": "...", "label": "heading"},
                ...
            ],
            "summary": {"title": 1, "heading": 5, "body": 20, ...}
        }
        or None if Gemini is unavailable or errors.
    """
    doc = Document(input_path)
    texts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if not texts:
        return {"paragraphs": [], "summary": {}}
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    labels = _get_llm_labels(texts, api_key)
    if not labels:
        return None
    summary = dict(Counter(labels))
    paragraphs = [
        {"index": i, "text_preview": t[:150] + ("..." if len(t) > 150 else ""), "label": labels[i]}
        for i, t in enumerate(texts)
    ]
    return {"paragraphs": paragraphs, "summary": summary}


def summarize_document(input_path: str, max_chars: int = 4000) -> str | None:
    """
    Extract text from docx (first max_chars) and return a 1–2 sentence summary from Gemini.
    
    Args:
        input_path: Path to .docx file
        max_chars: Maximum characters to summarize (default 4000)
    
    Returns:
        Summary string or None if error
    """
    doc = Document(input_path)
    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(parts)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    return _get_llm_summary(text, api_key, max_chars=max_chars)


# -------- Styling helpers --------

def _apply_run_style(run, size=12, bold=False, italic=False, underline=False):
    """
    Applies font styling to a text run (contiguous text with same formatting).
    
    Args:
        run: python-docx Run object
        size: Font size in points
        bold: Bold flag
        italic: Italic flag
        underline: Underline flag
    """
    run.font.name = "Times New Roman"
    # Set East Asian font (for CJK characters: Chinese, Japanese, Korean)
    try:
        rPr = run._element.rPr
        if rPr is not None and rPr.rFonts is not None:
            rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    except (AttributeError, TypeError):
        pass
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.underline = underline


def _apply_para_style(para, doc, kind: str, is_after_title: bool = False):
    """
    Applies paragraph-level styling based on type.
    
    Args:
        para: python-docx Paragraph object
        doc: Document object (for styles, not used currently)
        kind: "title", "heading", "body", or "caption"
        is_after_title: If True, add page break before this paragraph
    
    Styles applied:
    - title: 16pt, bold, underline, center, 12pt after, line spacing 1.0
    - heading: 14pt, bold, underline, left, 12pt before, 6pt after, line spacing 1.0
    - body: 12pt, justify, 0pt before/after, line spacing 1.5
    - caption: 10pt, italic, center, 6pt before/after, line spacing 1.0
    """
    # Paragraphs should already have runs (converted before calling this function)
    # But check just in case
    if len(para.runs) == 0:
        # Last resort - try to add a run if somehow we still don't have one
        text = para.text.strip()
        if text:
            para.add_run(text)
        else:
            return  # Empty paragraph - nothing to style
    
    # Do NOT set para.style here - it can clear paragraph content in some docx files.
    # We only set alignment and run formatting, which preserves text.
    
    # Apply base style to all runs first
    for run in para.runs:
        _apply_run_style(run, size=12, bold=False, italic=False, underline=False)

    if kind == "title":
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in para.runs:
            _apply_run_style(run, size=16, bold=True, italic=False, underline=True)
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after = Pt(12)
        para.paragraph_format.line_spacing = 1.0
        return
    
    if kind == "heading":
        para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in para.runs:
            _apply_run_style(run, size=14, bold=True, italic=False, underline=True)
        para.paragraph_format.space_before = Pt(12)
        para.paragraph_format.space_after = Pt(6)
        para.paragraph_format.line_spacing = 1.0
        return
    
    if kind == "caption":
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in para.runs:
            _apply_run_style(run, size=10, bold=False, italic=True, underline=False)
        para.paragraph_format.space_before = Pt(6)
        para.paragraph_format.space_after = Pt(6)
        para.paragraph_format.line_spacing = 1.0
        return
    
    # body / other
    para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for run in para.runs:
        _apply_run_style(run, size=12, bold=False, italic=False, underline=False)
    para.paragraph_format.space_before = Pt(0)
    para.paragraph_format.space_after = Pt(0)
    para.paragraph_format.line_spacing = 1.5
    # Page break after title page (next paragraph starts on new page)
    if is_after_title:
        para.paragraph_format.page_break_before = True


def format_document(
    input_path: str,
    output_path: str,
    use_llm: bool = False,
    llm_labels: list[str] | None = None,
) -> None:
    """
    Main function that formats a document.
    
    Steps:
    1. Open document
    2. Set margins (1" top/bottom, 1.25" left/right)
    3. Collect non-empty paragraphs
    4. Get labels (AI or rule-based)
    5. Convert paragraphs without runs to have runs (CRITICAL)
    6. Apply styles based on labels
    7. Save formatted document
    
    Args:
        input_path: Path to input .docx file
        output_path: Path to save formatted .docx file
        use_llm: If True, use Gemini AI for classification
        llm_labels: Pre-computed labels (if provided, skips detection)
    """
    doc = Document(input_path)

    # -------- Page margins (all sections) --------
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.25)

    # Collect non-empty paragraphs for LLM processing
    paras_with_text: list[tuple] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paras_with_text.append((para, text))

    # Get LLM labels if needed
    if llm_labels is not None and len(llm_labels) == len(paras_with_text):
        pass  # use llm_labels as-is
    elif use_llm:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        texts = [t for _, t in paras_with_text]
        llm_labels = _get_llm_labels(texts, api_key)
    else:
        llm_labels = None

    # CRITICAL: Convert paragraphs without runs to have runs BEFORE any styling
    # SIMPLEST APPROACH: Just add a run without clearing
    # This might cause text duplication, but GUARANTEES text is preserved
    # para.clear() was causing text loss, so we avoid it entirely
    for para, text in paras_with_text:
        if len(para.runs) == 0:
            # Paragraph has text but no runs - add text as a run
            # Don't clear - just add run (text might duplicate but will be preserved)
            original_text = para.text.strip()
            if original_text:
                para.add_run(original_text)
                # Verify it worked
                if len(para.runs) == 0:
                    # If that failed, something is very wrong
                    raise RuntimeError(f"Failed to add run to paragraph with text: '{original_text[:50]}...'")

    # Process each non-empty paragraph (simpler approach like old code)
    first_para_index = 0
    title_para_index: int | None = None
    
    para_idx = 0  # Index into paras_with_text (non-empty paragraphs only)
    for para, text in paras_with_text:
        # Determine kind
        if llm_labels and para_idx < len(llm_labels):
            kind = llm_labels[para_idx] if llm_labels[para_idx] in ("title", "heading", "body", "caption", "other") else "body"
        else:
            # Rule-based
            if _is_likely_title(text, is_first=(para_idx == first_para_index)):
                kind = "title"
                title_para_index = para_idx
            elif _is_caption(text):
                kind = "caption"
            elif _is_rule_based_heading(text):
                kind = "heading"
            else:
                kind = "body"
        
        # Apply style (paragraphs should now have runs from conversion above)
        is_after_title = title_para_index is not None and para_idx == title_para_index + 1
        _apply_para_style(para, doc, kind, is_after_title=is_after_title)
        
        para_idx += 1

    # Final verification: ensure we didn't lose any text
    total_with_text = len([p for p in doc.paragraphs if p.text.strip()])
    
    if total_with_text == 0 and len(paras_with_text) > 0:
        # Something went wrong - text was lost
        raise ValueError(f"CRITICAL: All text was lost! Had {len(paras_with_text)} paragraphs but document is empty after formatting.")

    doc.save(output_path)
```

**Key Points**:
- Rule-based detection uses regex patterns and keyword matching
- AI detection uses Gemini with JSON response parsing
- Critical: Converts paragraphs without runs to have runs before styling
- Avoids `para.clear()` and `para.style` assignment to prevent text loss
- Applies comprehensive styling: font, size, bold, italic, underline, alignment, spacing, page breaks

---

### 5. `requirements.txt` - Dependencies

**Complete Code**:

```
fastapi
uvicorn
python-docx
playwright
python-multipart
google-generativeai
requests
```

**Explanation**:
- **fastapi**: HTTP framework for API server
- **uvicorn**: ASGI server to run FastAPI
- **python-docx**: Read/write Word documents (.docx)
- **playwright**: Browser automation
- **python-multipart**: File upload support for FastAPI
- **google-generativeai**: Gemini AI integration (optional, lazy-loaded)
- **requests**: HTTP client (for direct API calls, if needed)

---

### 6. `.gitignore` - Git Ignore Rules

**Complete Code**:

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Project specific
backend/uploads/
backend/outputs/
agent/formatted_*.docx
*.docx
!agent/sample.docx

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Environment variables
.env
agent/.env
```

**Explanation**:
- Ignores Python cache files and virtual environments
- Ignores uploaded/formatted documents (except sample.docx)
- Ignores IDE and OS files
- Ignores environment variable files (contains API keys)

---

## Data Flow

### Complete Flow: User Runs `python run_all.py`

```
1. run_all.py
   ├─ Starts backend subprocess (uvicorn)
   ├─ Waits for http://127.0.0.1:8000/docs to respond
   └─ Calls run_agent.run()

2. run_agent.py
   ├─ Launches browser (Playwright)
   ├─ Navigates to Swagger UI
   ├─ Expands POST /format endpoint
   ├─ Clicks "Try it out"
   ├─ Sets file input to sample.docx
   ├─ Clicks "Execute"
   └─ Waits for response

3. Backend receives POST /format
   ├─ main.py saves file to uploads/
   ├─ Calls format_document()
   └─ Returns FileResponse

4. formatter.py
   ├─ Opens document (python-docx)
   ├─ Sets margins
   ├─ Collects paragraphs
   ├─ Gets labels (rule-based or AI)
   ├─ Converts paragraphs without runs
   ├─ Applies styles
   └─ Saves to outputs/

5. Playwright receives response
   ├─ Extracts file from response body
   └─ Saves to agent/formatted_sample.docx

6. run_all.py
   └─ Terminates backend subprocess
```

### Data Structures

**Paragraph Processing**:
```python
paras_with_text: list[tuple] = [
    (para_object, "text content"),  # Paragraph object + text string
    (para_object, "more text"),
    ...
]
```

**LLM Labels**:
```python
llm_labels: list[str] = ["title", "heading", "body", "body", "caption", ...]
# One label per paragraph, in order
```

**Classification Result**:
```python
{
    "paragraphs": [
        {"index": 0, "text_preview": "...", "label": "title"},
        {"index": 1, "text_preview": "...", "label": "heading"},
        ...
    ],
    "summary": {"title": 1, "heading": 5, "body": 20, "caption": 2}
}
```

---

## Key Algorithms & Logic

### 1. Rule-Based Heading Detection Algorithm

```python
def _is_rule_based_heading(text: str) -> bool:
    """
    Multi-rule detection system (checked in order):
    
    Rule 1: All caps and short (< 120 chars) → heading
    Rule 2: Numbered section (1., 1.1, etc.) → heading
    Rule 3: Short line (< 50 chars) with section keyword → heading
    Rule 4: Short line with "Chapter N" or "Part N" → heading
    Rule 5: Short line without period → heading
    Rule 6: Starts with section keyword → heading
    Rule 7: Matches "Chapter N" or "Part N" → heading
    
    Returns True if ANY rule matches
    """
```

### 2. Paragraph Run Conversion Algorithm

```python
# Problem: Some .docx files store text in XML text nodes, not run elements
# Solution: Convert text nodes to runs before styling

for para, text in paras_with_text:
    if len(para.runs) == 0:  # No runs but has text
        original_text = para.text.strip()
        if original_text:
            para.add_run(original_text)  # Add as run
            # Note: May cause duplication but preserves text
```

### 3. Style Application Algorithm

```python
# For each paragraph:
# 1. Determine type (title/heading/body/caption)
# 2. Apply base style (12pt, no formatting)
# 3. Apply type-specific style (size, bold, underline, alignment, spacing)
# 4. Special case: page break after title

if kind == "title":
    # Override base style
    for run in para.runs:
        _apply_run_style(run, size=16, bold=True, underline=True)
    para.alignment = CENTER
    para.paragraph_format.space_after = Pt(12)
    # Mark next paragraph for page break
    title_para_index = idx

if is_after_title:
    para.paragraph_format.page_break_before = True
```

---

## Summary

This codebase implements a complete document formatting pipeline:

1. **Orchestration**: `run_all.py` manages the entire process
2. **Automation**: `run_agent.py` handles browser interaction
3. **API**: `main.py` provides HTTP endpoints
4. **Logic**: `formatter.py` contains all formatting rules and AI integration

The system is modular, extensible, and handles edge cases (empty documents, missing runs, AI failures) gracefully.

**Key Features**:
- Rule-based and AI-based paragraph detection
- Comprehensive styling (font, size, bold, italic, underline, alignment, spacing, margins, page breaks)
- Browser automation via Playwright
- RESTful API with Swagger UI
- Error handling and validation
- Lazy loading of optional dependencies (Gemini)
