# Docx Tools Usage Guide

This guide explains how to use the custom docx tools (`doc_tools.py`) with your Gemini agent.

## Available Tools

### 1. `create_master_doc` — Create a complete Word report

**What it does:**
- Creates a new `.docx` file from scratch
- Applies Times New Roman 12pt globally
- Adds title page, header, footer
- Supports headings (H1=17pt, H2=13pt), body text, bullets, tables, hyperlinks, images

**Example agent task:**
```
Research Ringg AI's pricing and team. Create a report called "Ringg_Report" with:
- Title page: "Ringg AI Analysis"
- H1: "Pricing Information"
- A table with columns: ["Plan", "Price", "Features"] and rows from the website
- H1: "Team"
- Bullet list of team members
- Hyperlinks to their LinkedIn profiles
```

**Content blocks format:**
```python
content_blocks = [
    {"type": "h1", "text": "Introduction"},
    {"type": "text", "text": "This is body text"},
    {"type": "text", "text": "Bold text", "bold": True},
    {"type": "bullets", "items": ["Item 1", "Item 2", "Item 3"]},
    {
        "type": "table",
        "headers": ["Name", "Price"],
        "rows": [["Basic", "$10"], ["Pro", "$50"]]
    },
    {
        "type": "link",
        "pre_text": "Visit: ",
        "label": "Ringg AI Website",
        "url": "https://ringg.ai"
    },
    {"type": "image", "path": "/path/to/screenshot.png", "width_inches": 4.0}
]
```

### 2. `append_section_to_doc` — Add sections incrementally

**What it does:**
- Opens an existing `.docx` file
- Appends a Heading 2 (13pt bold) + body paragraph
- Saves the document

**Example agent task:**
```
Append a new section to "Ringg_Report.docx" with heading "New Features" 
and body "Ringg AI recently added support for custom models."
```

### 3. `insert_image_into_doc` — Embed screenshots/diagrams

**What it does:**
- Opens an existing `.docx` file
- Inserts an image from a file path
- Saves the document

**Example agent task:**
```
Take a screenshot of the pricing page, save it as "pricing.png", 
then insert it into "Ringg_Report.docx" with width 4 inches.
```

### 4. `get_doc_text` — Read document for LLM analysis

**What it does:**
- Reads all text from an existing `.docx` file
- Returns plain text (all paragraphs concatenated)

**Example agent task:**
```
Read "Ringg_Report.docx", summarize the key points, 
then append a new section called "Summary" with that summary.
```

## Complete Workflow Example

**Task:** "Research a company's pricing, create a report, then add a summary section"

**What the agent does:**
1. Navigates to company website (browser-use)
2. Extracts pricing data (browser-use DOM reading)
3. Calls `create_master_doc("Company_Report", "Company Pricing Analysis", content_blocks=[...])`
4. Calls `get_doc_text("Company_Report")` to read what was created
5. Analyzes the text (Gemini reasoning)
6. Calls `append_section_to_doc("Company_Report", "Summary", "...")` with the summary

## Integration with Your Existing Code

Your current `word_formatter_agent.py` formats **Google Docs** in a browser.

This new `word_report_agent.py` + `doc_tools.py` generates **standalone .docx files** on disk.

**You can use both:**
- `word_formatter_agent.py` → Format existing Google Docs
- `word_report_agent.py` → Generate new Word reports from web research

## Cost Considerations

With `max_steps=20` and `max_actions_per_step=2`:
- ~20 LLM calls (one per step)
- Each call includes tool descriptions (your 4 docx tools)
- Estimated cost: **$0.05–$0.15 per report** (well under your $0.20 target)
