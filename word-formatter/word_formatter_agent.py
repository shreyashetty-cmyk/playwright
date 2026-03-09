"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         BROWSER USE — WORD DOCUMENT FORMATTER  (GEMINI, ~150 CALLS)         ║
╚══════════════════════════════════════════════════════════════════════════════╝

SETUP (run once):
  pip install browser-use langchain-google-genai playwright rich python-dotenv
  playwright install chromium

RUN:
  python word_formatter_agent.py
"""

import asyncio
import os
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from dotenv import load_dotenv

load_dotenv()

from browser_use import Agent, Browser, ChatGoogle
from doc_tools import controller  # custom docx formatting tools (create_master_doc, etc.)

console = Console()

# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """
You are a Google Docs formatting agent controlling a real Chrome browser.
Your goal is to apply every formatting instruction exactly once, using at
most 20 reasoning steps and 2 UI actions per step. Every action must count.

━━━ GLOBAL STRATEGY ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Always click inside the white document body before using any shortcut.
2. Prefer BULK operations:
   - Use Ctrl+A for global font/size/spacing changes.
   - Use “Update style to match” to change all headings/body text at once.
3. Use Ctrl+F to jump to specific text (chapter titles, “Conclusion”, etc.).
4. After each major action, visually verify it worked (toolbar + document).

━━━ SELECTION & NAVIGATION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Select ALL text:     click body → Ctrl+A
- Select a paragraph:  triple-click inside it
- Find text:           Ctrl+F → type text → Enter → Escape → caret moves there
- Move to start of line: Home
- Page break:          caret at line start → Ctrl+Enter

━━━ FONT & SIZE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
After selecting the target text:
1. Font family:
   - Click the font dropdown in the toolbar (shows e.g. “Arial”).
   - Triple-click inside to select the name.
   - Type the new font (e.g. “Times New Roman”, “Arial”) and press Enter.
2. Font size:
   - Click the size box (shows e.g. “11”).
   - Triple-click to select the number.
   - Type the new size (e.g. “12”, “18”, “24”) and press Enter.

━━━ BASIC STYLES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
After selecting text:
- Bold:        Ctrl+B
- Italic:      Ctrl+I
- Underline:   Ctrl+U
- Center:      Ctrl+E
- Justify:     Ctrl+Shift+J

━━━ LINE SPACING (GLOBAL) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Click in the document body, press Ctrl+A (select all).
2. Format → “Line & paragraph spacing” → choose “1.5”.

━━━ HEADING / BODY STYLES (DO THIS INSTEAD OF ONE-BY-ONE) ━━━━━━━━━━━━━━━━
To update all paragraphs of a style (e.g. all Heading 1):

1. Click one paragraph that already uses that style (e.g. Heading 1).
2. Apply required formatting (font, size, bold, color).
3. In the toolbar, open the styles dropdown (leftmost, shows the style name).
4. In the dropdown, hover the same style name (e.g. “Heading 1”).
5. Click the ► arrow on its right → click “Update 'Heading 1' to match”.
6. ✅ All paragraphs with that style are now updated at once.

Repeat for Heading 2, Heading 3, and Normal text as needed.

━━━ TABLE OF CONTENTS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Use Ctrl+F to find the first chapter heading (e.g. “Chapter 1”).
2. Escape to close find, set caret at start of that heading line.
3. Press Ctrl+Enter to insert a blank page above it.
4. Click on the new blank page.
5. Insert → “Table of contents” → choose the variant with page numbers.

━━━ PAGE NUMBERS IN FOOTER ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Insert → “Page numbers”.
2. In the options, choose bottom of page, centered (footer center option).

━━━ EXECUTION RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Do NOT format headings or paragraphs one by one if a style update can do it.
- Use as few steps as possible: global baseline → style updates → specific tweaks.
- If a shortcut fails, try the equivalent menu path once; if it still fails,
  note that instruction as ❌ in the final report and move on.
- At the end, confirm “All changes saved” appears in the top status bar, then
  report each original instruction with ✅ or ❌ and a brief reason.
"""


# ══════════════════════════════════════════════════════════════════════════════
# TASK BUILDER
# ══════════════════════════════════════════════════════════════════════════════
def build_task(doc_url: str, instructions: str) -> str:
    return f"""
Open this Google Docs document in the browser:
{doc_url}

Wait for the document editor to FULLY load. The toolbar showing font name,
font size, and the Bold/Italic buttons must all be visible before you begin.

Apply ALL of the following formatting instructions:

{instructions}

━━━ HOW TO WORK EFFICIENTLY ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Priority order:
  1. FIRST: Select All (Ctrl+A) and set the global font, size, and line spacing.
     This sets the baseline for the whole document in just a few actions.

  2. SECOND: Update each heading style using "Update style to match" — this
     reformats ALL headings of that type at once instead of one by one.

  3. THIRD: Handle specific elements — title, conclusion, page breaks, TOC,
     page numbers, bullet lists — each targeted with Ctrl+F to locate them.

━━━ FINAL STEP ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
After all instructions are applied:
  1. Confirm "All changes saved" appears in the status bar.
  2. List every instruction with ✅ (applied successfully) or ❌ (failed, reason).
"""


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
async def main():
    console.print(Panel(
        "[bold cyan]Word Document Formatter[/bold cyan]\n"
        "[dim]Gemini 2.0 Flash · ~150 browser calls · Google Docs[/dim]",
        border_style="cyan",
        title="🤖 AI Document Formatter"
    ))

    # ── API Key ───────────────────────────────────────────────────────────────
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if api_key:
        console.print("\n[dim]Using GOOGLE_API_KEY from environment.[/dim]")
    else:
        api_key = Prompt.ask(
            "\n[bold]Google Gemini API key[/bold] [dim](free at aistudio.google.com)[/dim]",
            password=True
        )

    # ── Document URL ──────────────────────────────────────────────────────────
    doc_url = Prompt.ask("\n[bold]Document URL[/bold] [dim](Google Docs link)[/dim]")

    # ── Instructions ──────────────────────────────────────────────────────────
    console.print("\n[bold]Formatting instructions[/bold]")
    console.print("[dim]Type everything you want done. Press Enter twice when finished.[/dim]\n")

    lines = []
    while True:
        line = input("  ")
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    instructions = "\n".join(lines).strip()

    if not instructions:
        console.print("[red]No instructions entered — exiting.[/red]")
        return

    # ── LLM ───────────────────────────────────────────────────────────────────
    # Use browser-use's built-in Gemini client (ChatGoogle) instead of
    # langchain_google_genai. It reads GOOGLE_API_KEY from the environment.
    os.environ["GOOGLE_API_KEY"] = api_key
    llm = ChatGoogle(
        model="gemini-2.0-flash",
    )

    # ── Browser ───────────────────────────────────────────────────────────────
    # TIP: After your first run where you log into Google manually,
    # uncomment the user_data_dir line below to reuse your login session.
    browser = Browser()
    # To reuse Google login across runs, replace the line above with:
    # from browser_use import BrowserConfig
    # browser = Browser(config=BrowserConfig(user_data_dir="./browser_profile"))

    # ── Agent ─────────────────────────────────────────────────────────────────
    # 20 steps × 2 actions per step ≈ 40 total browser/LLM calls
    # Also exposes docx tools via 'controller' so the agent can optionally
    # generate or update .docx reports in addition to formatting Google Docs.
    agent = Agent(
        task=build_task(doc_url, instructions),
        llm=llm,
        browser=browser,
        system_prompt_extension=SYSTEM_PROMPT,
        use_vision=True,           # reads screenshots to verify each change
        max_actions_per_step=2,    # keep actions per step low for cost control
        controller=controller,     # exposes create_master_doc, append_section_to_doc, etc.
    )

    console.print("\n[bold green]Agent is running — watch the browser window.[/bold green]")
    console.print("[dim]This takes 5–15 minutes for a complex document. Don't close the browser.[/dim]\n")

    try:
        result = await agent.run(max_steps=20)   # 20 × 2 ≈ 40 total calls
        console.print(Panel(
            str(result),
            title="[bold green]✅ Finished[/bold green]",
            border_style="green"
        ))
    except Exception as e:
        console.print(Panel(
            f"[red]{e}[/red]",
            title="[bold red]❌ Error[/bold red]",
            border_style="red"
        ))
    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())