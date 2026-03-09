# Word Document Formatter Agent

Automates formatting of **Google Docs** and **Word Online** via natural language. The agent uses [Browser-Use](https://github.com/browser-use/browser-use) with Google Gemini to open your document in a real browser, follow your instructions, verify results, and save.

## Architecture

- **User input**: Document URL + plain-English formatting instructions (+ Google API key)
- **word_formatter_agent.py**: Orchestrates the LLM and browser agent
- **LLM**: Google Gemini reasons about the UI, plans actions, reads screenshots
- **Browser-Use**: Wraps Playwright; provides `click()`, `type()`, `scroll()`, `screenshot()`, etc.
- **Chromium (Playwright)**: Real browser; Google Docs / Word Online run inside it

## Setup

### 1. Environment

```bash
cd word-formatter
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. (Optional) Set up environment variables

Create a `.env` file from the example:

```bash
cp .env.example .env
# Edit .env and add your API key(s)
```

The script will automatically load `GOOGLE_API_KEY` from `.env`. This way you don't need to enter your API key every time.

- **Interactive mode**: If an API key is found in `.env`, you'll be asked if you want to use it (default: yes).
- **Batch mode**: API key from `.env` is used automatically if `--api-key` is not provided.

**Note**: `.env` is gitignored — your keys won't be committed. `.env.example` is tracked as a template.

### 4. First run (login)

```bash
python word_formatter_agent.py
```

- Enter Google API key (or use one from `.env`)
- Paste document URL and formatting instructions
- When the browser opens, **log in to Google or Microsoft manually** if prompted
- Optionally enable **persistent browser profile** so the session is saved to `browser_profile/`

### 5. Later runs

- If you use the persistent profile, the saved session is reused and you won’t need to log in again.
- For batch mode, use `--profile` to use the same profile.

## Usage

### Interactive

```bash
python word_formatter_agent.py
```

You’ll be prompted for provider, API key, document URL, and formatting instructions (plain English).

### Batch / CI

```bash
python word_formatter_agent.py \
  --url "https://docs.google.com/document/d/XXXX/edit" \
  --instructions instructions.txt \
  --headless
```

- **`--url`**: Google Docs or Word Online document URL  
- **`--instructions`**: Path to a text file with formatting instructions  
- **`--headless`**: Run browser without a visible window  
- **`--profile`**: Use persistent profile (e.g. `browser_profile/`)  
- **`--api-key`**: Google API key (default: from `GOOGLE_API_KEY` env var)

Example files are included:
- **`example_document.txt`**: Sample document content you can copy into Google Docs/Word Online
- **`example_instructions.txt`**: Complete formatting instructions demonstrating various capabilities

Example `instructions.txt`:

```
Set the document title "Introduction to Machine Learning" to Arial font, size 24pt, bold, and center it.
Set all chapter headings (Chapter 1, Chapter 2) to Arial font, size 18pt, bold, and color them dark blue.
Set all section headings to Arial font, size 16pt, bold, and italic.
Set all body paragraphs to Times New Roman font, size 12pt.
Justify all body paragraphs (align text to both left and right margins).
Set line spacing to 1.5 for the entire document.
Add a Table of Contents after the title page, before Chapter 1.
Add page numbers in the footer, centered.
```

## Formatting capabilities (examples)

| Instruction type        | How the agent applies it |
|-------------------------|---------------------------|
| Font / size             | Toolbar font/size boxes, Format menu |
| Bold / italic / underline | Ctrl+B / Ctrl+I / Ctrl+U or toolbar |
| Alignment               | Format > Align & indent (Docs) / Home (Word) |
| Line spacing            | Format > Line & paragraph spacing |
| Heading styles          | Paragraph styles → Update style |
| Table of contents       | Insert > Table of contents (Docs) / References > TOC (Word) |
| Page numbers / headers  | Insert > Headers & footers |
| Page break              | Insert > Break > Page break or Ctrl+Enter |

The system prompt includes detailed strategies for both Google Docs and Word Online.

## Security

- API keys are prompted interactively or read from env; they are not written to disk by the script.
- If you use a `.env` file, add `.env` to `.gitignore`.
- `browser_profile/` holds your Google/Microsoft session cookies — treat it like a password and do not commit it.

## Limitations

- **Auth**: The agent cannot complete sign-in (MFA, OAuth, CAPTCHA). Use a persistent profile: log in once manually, then re-run with the same profile.
- **Suggesting mode**: In Google Docs, the agent should switch to Editing mode if needed.
- **Read-only docs**: The agent may try “Open with Google Docs” when the link opens in view-only mode.
- **Slow / large docs**: You can increase `max_steps` (e.g. to 100+) and timeouts in the script for complex documents.

## File layout

```
word-formatter/
├── word_formatter_agent.py   # Main agent
├── requirements.txt
├── README.md
├── .gitignore
├── .env.example              # Template for API key
├── example_document.txt      # Sample document content
├── example_instructions.txt  # Sample formatting instructions
└── browser_profile/          # Created when using persistent profile (do not commit)
```

## License

Use and modify as needed for your project.
