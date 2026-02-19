# Doc Formatter Agent

Upload a messy `.docx` → get a cleaned one (Times New Roman, headings, spacing, margins, underlining). Trigger via browser (Swagger) or a Playwright script.

---

## Document capabilities (what gets formatted)

Yes — it **formats the whole doc**. Here’s what the formatter does:

| Capability | What it does |
|------------|----------------|
| **Font** | All text → **Times New Roman** (including East Asian). |
| **Title** | First short line → **16 pt, bold, underlined, centered**; space after; next paragraph starts on a **new page**. |
| **Headings** | Section lines (numbered like 1.1, keywords like ABSTRACT/INTRODUCTION, Chapter N, short lines) → **14 pt, bold, underlined, left**; space before/after. |
| **Body** | Normal paragraphs → **12 pt, justified**, 1.5 line spacing; no extra space before/after. |
| **Captions** | Lines starting with “Figure”/“Table” → **10 pt, italic, centered**; small spacing. |
| **Margins** | Every section → **1"** top/bottom, **1.25"** left/right. |
| **Spacing** | Empty paragraphs removed; no extra space before/after; consistent line spacing by type. |
| **Detection** | **Rule-based:** regex (1.1, Chapter N), keywords (ABSTRACT, REFERENCES, etc.), length/caps. **Optional AI (Gemini):** label each paragraph as title/heading/body/caption, then apply the styles above. |

So: **font, size, bold, italic, underline, alignment, margins, page break, and spacing** are all applied. Tables and images inside the doc are **not** modified (only paragraph text is styled).

---

## What to run & what it does (short)

| What you run | How | What it does |
|--------------|-----|--------------|
| **ONE command (everything)** | `cd agent` then `python run_all_process.py` | Starts backend → classifies + formats + summarizes → saves formatted `.docx` + `*_summary.txt` → stops backend. Needs `GEMINI_API_KEY`. Put `sample.docx` in `agent/` first. |
| **One-command (browser)** | `cd agent` then `python run_all.py` | Starts the backend, opens browser, formats `sample.docx`, saves result in `agent/`, stops backend. Put `sample.docx` in `agent/` first. |
| **Backend only** | `cd backend` then `uvicorn main:app --reload` | Starts the API. You then open http://127.0.0.1:8000/docs and upload/format by hand. |
| **Agent only** | `cd agent` then `python run_agent.py` | Backend must already be running. Opens browser, uploads `sample.docx`, clicks Execute, saves formatted file in `agent/`. |
| **Batch (many files)** | `cd agent` then `python run_agent.py file1.docx file2.docx` or `python run_agent.py path/to/folder/` | Same as agent only, but formats each file (or every `.docx` in the folder). Backend must be running. |
| **All-in-one (AI pipeline)** | `cd agent` then `python run_process.py` (or `run_process.py file.docx` / `run_process.py folder/`) | One request: classify + format with Gemini + summarize. Saves formatted `.docx` and `*_summary.txt`. No browser. Needs `GEMINI_API_KEY` and backend running. |

**First-time setup (once):**  
`cd doc_formatter_agent` → `python3 -m venv .venv` → `source .venv/bin/activate` → `pip install -r requirements.txt` → `playwright install`

---

## Project Structure

- `backend/`: FastAPI application and formatting logic
- `agent/`: Playwright browser automation script
- `uploads/`: Temporary upload storage
- `outputs/`: Generated formatted documents
- `requirements.txt`: Python dependencies

## Setup

1. Create and activate the virtual environment:

```bash
cd doc_formatter_agent
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
playwright install
```

3. Run the FastAPI backend:

```bash
cd backend
uvicorn main:app --reload
```

4. Open the interactive docs in your browser:

```text
http://127.0.0.1:8000/docs
```

5. Run the Playwright agent from another terminal (with the virtualenv activated) after placing a `sample.docx` next to `agent/run_agent.py`:

```bash
cd agent
python run_agent.py
```

## More Playwright options

- **One command (start backend + run agent):**  
  From project root or `agent/`: `python run_all.py`  
  Starts the backend, waits until it’s ready, runs the agent, then stops the backend.

- **Batch format:**  
  Format multiple files or a whole folder via the same Swagger UI flow:
  ```bash
  cd agent
  python run_agent.py file1.docx file2.docx
  python run_agent.py path/to/folder/   # all .docx in that folder
  ```
  Backend must be running. Formatted files are saved in `agent/`.

