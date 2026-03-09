"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         BROWSER USE + DOCX TOOLS — WORD REPORT GENERATOR (GEMINI)            ║
║  Agent browses the web, extracts info, and generates formatted .docx reports║
╚══════════════════════════════════════════════════════════════════════════════╝

This agent combines browser-use (for web browsing) with custom docx tools
to create professional Word reports from web research.

SETUP:
  pip install -r requirements.txt
  playwright install chromium

USAGE:
  python word_report_agent.py
"""

import asyncio
import os
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from dotenv import load_dotenv

load_dotenv()

from browser_use import Agent, Browser, ChatGoogle
from doc_tools import controller  # Your custom docx tools

console = Console()


async def main():
    console.print(Panel(
        "[bold cyan]Word Report Generator Agent[/bold cyan]\n"
        "[dim]Gemini + Browser-Use + python-docx · Creates formatted .docx reports[/dim]",
        border_style="cyan",
        title="🤖 Word Report Generator"
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

    # ── Task ──────────────────────────────────────────────────────────────────
    console.print("\n[bold]What should the agent do?[/bold]")
    console.print("[dim]Examples:[/dim]")
    console.print("  • 'Research Ringg AI pricing and team, create Ringg_Report.docx'")
    console.print("  • 'Browse example.com, extract key features, generate Feature_List.docx'")
    console.print("  • 'Find the latest news about AI, create News_Summary.docx with tables'")
    
    task = Prompt.ask("\n[bold]Agent task[/bold]")

    # ── LLM ───────────────────────────────────────────────────────────────────
    os.environ["GOOGLE_API_KEY"] = api_key
    llm = ChatGoogle(model="gemini-2.0-flash")

    # ── Browser ───────────────────────────────────────────────────────────────
    browser = Browser()

    # ── Agent ─────────────────────────────────────────────────────────────────
    # Pass controller=controller to expose your docx tools
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        controller=controller,  # This exposes create_master_doc, append_section_to_doc, etc.
        use_vision=False,        # Set True if you want screenshot support
        max_actions_per_step=2,
    )

    console.print("\n[bold green]Agent running — watch the browser window.[/bold green]")
    console.print("[dim]The agent will browse, extract info, and generate a Word report.[/dim]\n")

    try:
        result = await agent.run(max_steps=20)
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


if __name__ == "__main__":
    asyncio.run(main())
