# Doc Formatter Agent

Automated document formatter for `.docx` files. Upload a document → get a formatted one with consistent styling (Times New Roman, headings, spacing, margins, underlining). Uses Playwright for browser automation.

---

## Quick Start

**One command to format a document:**

```bash
cd agent
python run_all.py
```

This will:
1. Start the FastAPI backend automatically
2. Open Swagger UI in your browser
3. Format `sample.docx` (place it in `agent/` folder first)
4. Save the formatted file to `agent/formatted_sample.docx`
5. Stop the backend automatically

**Put your document in `agent/` folder as `sample.docx` before running.**

---

## Document Capabilities (Existing Features)

The formatter applies styling to **paragraph text only**. Tables and images inside the document are **not** modified.

### Styling applied by paragraph type

| Type | Font | Size | Bold | Italic | Underline | Alignment | Space before | Space after | Line spacing | Other |
|------|------|------|------|--------|-----------|------------|--------------|-------------|--------------|--------|
| **Title** | Times New Roman | 16 pt | Yes | No | Yes | Center | 0 pt | 12 pt | 1.0 | Next paragraph gets **page break before** |
| **Heading** | Times New Roman | 14 pt | Yes | No | Yes | Left | 12 pt | 6 pt | 1.0 | — |
| **Body** | Times New Roman | 12 pt | No | No | No | Justify | 0 pt | 0 pt | 1.5 | — |
| **Caption** | Times New Roman | 10 pt | No | Yes | No | Center | 6 pt | 6 pt | 1.0 | — |

### Margins (all sections)

- **Top / Bottom:** 1 inch  
- **Left / Right:** 1.25 inches  

### How paragraph type is detected (rule-based)

- **Title:** First non-empty paragraph that is short (≤100 chars), not numbered, and either all caps or no trailing period (≤80 chars).
- **Heading:** Any of:
  - Numbered sections: `1.`, `1.1`, `1.1.1`, `2.`, etc. (regex: `^\s*\d+(\.\d+)*\.?\s+\S`)
  - All caps and &lt; 120 characters
  - Short line (&lt; 50 chars) and not ending in `.` or matches section keywords
  - Section keywords: **abstract**, **acknowledgement(s)**, **appendix**, **references**, **bibliography**, **contents**, **table of contents**, **introduction**, **conclusion**, **chapter**, **part**, **preface**, **foreword**, **executive summary**, **index**
  - Lines matching “Chapter N” or “Part N”
- **Caption:** Lines starting with **Figure**, **Fig.**, or **Table** (with optional number), e.g. `Figure 1:`, `Table 2.`
- **Body:** Everything else.

### Optional AI detection (Gemini)

If you use `--llm` or call `/format-with-ai` or `/process`, the backend can use **Gemini** to label each paragraph as **title**, **heading**, **body**, **caption**, or **other**, then apply the styles above. Requires `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) in the environment.

### What is not changed

- **Tables:** structure and content are not modified.  
- **Images / embedded objects:** not modified.  
- **Headers / footers:** not modified by the formatter.

---

## Usage

### Basic Usage (One Command)

```bash
cd agent
python run_all.py
```

Formats `agent/sample.docx` and saves to `agent/formatted_sample.docx`.

### Format Multiple Files

```bash
cd agent
python run_all.py file1.docx file2.docx
```

### Format All Files in a Folder

```bash
cd agent
python run_all.py path/to/folder/
```

### Use AI Classification (Optional)

If you have a `GEMINI_API_KEY` set in your environment:

```bash
cd agent
python run_all.py --llm
```

This uses Gemini AI to classify paragraphs as title/heading/body/caption before formatting.

---

## Setup (First Time)

1. **Clone the repository:**

```bash
git clone https://github.com/shreyashetty-cmyk/playwright.git
cd playwright
```

2. **Create and activate virtual environment:**

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**

```bash
pip install -r requirements.txt
playwright install
```

4. **Place your document:**

Put your `.docx` file in the `agent/` folder as `sample.docx`.

5. **Run:**

```bash
cd agent
python run_all.py
```

---

## Project Structure

```
doc_formatter_agent/
├── agent/
│   ├── run_all.py          # Main script (one command to run everything)
│   ├── run_agent.py         # Playwright automation script
│   └── sample.docx          # Place your document here
├── backend/
│   ├── main.py              # FastAPI server
│   ├── formatter.py         # Document formatting logic
│   ├── uploads/             # Temporary upload storage
│   └── outputs/             # Generated formatted documents
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

---

## API Endpoints

All endpoints are available when the backend is running. Open **http://127.0.0.1:8000/docs** for interactive Swagger UI.

| Endpoint | Input | Output | Uses Gemini? |
|----------|--------|--------|--------------|
| **POST /format** | File upload + optional `?use_llm=true` | Formatted `.docx` file (download) | Optional |
| **POST /format-with-ai** | File upload | Formatted `.docx` file (download) | Yes |
| **POST /classify** | File upload | JSON: `paragraphs` (index, text_preview, label), `summary` (counts) | Yes |
| **POST /summarize** | File upload | JSON: `summary` (1–2 sentence summary) | Yes |
| **POST /process** | File upload | JSON: `formatted_file_base64`, `filename`, `summary`, `classification` | Yes |

- **Formatting only (no Gemini):** Use `POST /format` without `use_llm`, or run `python run_all.py` (default).
- **Formatting with AI labels:** Use `POST /format?use_llm=true` or `POST /format-with-ai`, or run `python run_all.py --llm`.
- **Classify / summarize / process:** Require `GEMINI_API_KEY` (or `GOOGLE_API_KEY`); return 503 if missing or unavailable.

---

## Requirements

- Python 3.8+
- Playwright (installed via `playwright install`)
- Dependencies listed in `requirements.txt`

Optional:
- `GEMINI_API_KEY` environment variable for AI-based classification

---

## Output

Formatted documents are saved to:
- `backend/outputs/formatted_<filename>.docx` (where API saves it)
- `agent/formatted_<filename>.docx` (where Playwright downloads it)

Both files contain the same formatted content.

---

## Troubleshooting

**Document is empty after formatting?**
- Make sure your input document has text in paragraphs (not just images/tables)
- Check that `sample.docx` exists in the `agent/` folder

**Backend won't start?**
- Make sure port 8000 is not already in use
- Check that you're in the `backend/` directory when running uvicorn manually

**Playwright errors?**
- Run `playwright install` to install browser binaries
- Make sure you're using the virtual environment where Playwright is installed

---

## License

This project is open source and available for use.
