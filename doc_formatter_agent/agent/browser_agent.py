"""
Gemini-powered browser agent using Playwright.

High-level behaviour:
- Launch a Chromium browser with Playwright.
- Repeatedly:
  - Capture a screenshot and a compact DOM summary (observation).
  - Send GOAL + observation + screenshot to Gemini Flash Vision as planner.
  - Receive a structured action (CLICK / SET_FILE / TYPE / NAVIGATE / DONE).
  - Execute the action with Playwright.
- Stop when the planner returns DONE or when a success condition is met.

Baseline use case:
- Control the local FastAPI Swagger UI at http://127.0.0.1:8000/docs
  to upload a .docx to the /format endpoint and download the formatted result.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import Page, sync_playwright

from gemini_client import PlannerAction, call_vision_planner


AGENT_DIR = Path(__file__).resolve().parent
DEFAULT_BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
DEFAULT_SWAGGER_URL = f"{DEFAULT_BACKEND_URL}/docs"


@dataclass
class StepRecord:
    step_index: int
    action: PlannerAction
    success: bool
    error: Optional[str] = None


def _summarise_elements(page: Page, max_items: int = 40) -> List[Dict[str, Any]]:
    """
    Build a lightweight summary of clickable elements and file inputs on the page.
    This is intentionally approximate; the planner uses it together with the screenshot.
    """
    elements: List[Dict[str, Any]] = []

    # Buttons and links
    try:
        handles = page.query_selector_all("button, a, input[type=submit]")
        for h in handles[:max_items]:
            try:
                text = (h.inner_text() or "").strip()
                role = h.get_attribute("role") or ""
                tag = h.evaluate("el => el.tagName") or ""
                elements.append(
                    {
                        "kind": "clickable",
                        "tag": str(tag),
                        "role": role,
                        "text": text[:120],
                    }
                )
            except Exception:
                continue
    except Exception:
        pass

    # File inputs
    try:
        file_inputs = page.query_selector_all("input[type=file]")
        for h in file_inputs[: max(5, max_items - len(elements))]:
            try:
                name = h.get_attribute("name") or ""
                accept = h.get_attribute("accept") or ""
                elements.append(
                    {
                        "kind": "file_input",
                        "name": name,
                        "accept": accept,
                    }
                )
            except Exception:
                continue
    except Exception:
        pass

    return elements


def build_observation(page: Page, goal: str, steps: List[StepRecord]) -> Dict[str, Any]:
    """Create a compact observation dict for Gemini from the current page and history."""
    last_steps: List[Dict[str, Any]] = []
    for s in steps[-5:]:
        last_steps.append(
            {
                "step_index": s.step_index,
                "action": {
                    "action_type": s.action.action_type,
                    "target": s.action.target,
                    "arguments": s.action.arguments,
                },
                "success": s.success,
                "error": s.error,
            }
        )

    try:
        url = page.url
    except Exception:
        url = ""
    try:
        title = page.title()
    except Exception:
        title = ""

    elements = _summarise_elements(page)

    # Limit page text to a small prefix of visible body text to avoid huge prompts.
    try:
        main_text = page.inner_text("body")[:2000]
    except Exception:
        main_text = ""

    return {
        "goal": goal,
        "url": url,
        "title": title,
        "elements": elements,
        "recent_steps": last_steps,
        "visible_text_prefix": main_text,
    }


def _execute_action(
    page: Page,
    action: PlannerAction,
    doc_path: Path,
) -> StepRecord:
    """
    Execute a single PlannerAction on the given Playwright page.
    This intentionally uses robust, slightly fuzzy heuristics for selectors.
    """
    error: Optional[str] = None
    success = True

    def _click_by_description(description: str) -> None:
        # Try role/text-based locators first, then fallback to generic text search.
        text = description
        if ":" in description:
            # e.g. "button:Execute"
            prefix, rest = description.split(":", 1)
            text = rest.strip()
            prefix = prefix.strip().lower()
            if prefix in {"button", "btn"}:
                page.get_by_role("button", name=text).first.click()
                return
            if prefix in {"link", "a"}:
                page.get_by_role("link", name=text).first.click()
                return
        # Fallbacks
        try:
            page.get_by_text(text, exact=True).first.click()
        except Exception:
            page.get_by_text(text).first.click()

    try:
        if action.action_type == "CLICK":
            if not action.target:
                raise ValueError("CLICK action missing target")
            target = action.target
            if target.startswith("css:"):
                sel = target.split(":", 1)[1]
                page.locator(sel).first.click()
            else:
                _click_by_description(target)

        elif action.action_type == "SET_FILE":
            # We always map file_role "docx_to_upload" to doc_path.
            if not action.target:
                target = "input[type=file]"
            else:
                target = action.target

            if target.startswith("css:"):
                sel = target.split(":", 1)[1]
                input_loc = page.locator(sel).first
            else:
                # Simple heuristic: just pick first file input.
                input_loc = page.locator("input[type=file]").first

            input_loc.set_input_files(str(doc_path))

        elif action.action_type == "TYPE":
            if not action.target:
                raise ValueError("TYPE action missing target")
            text = ""
            if action.arguments and isinstance(action.arguments, dict):
                text = str(action.arguments.get("text", ""))
            if not text:
                raise ValueError("TYPE action missing 'text' in arguments")

            target = action.target
            if target.startswith("css:"):
                sel = target.split(":", 1)[1]
                page.fill(sel, text)
            else:
                # Try role=text; otherwise use a generic input.
                try:
                    page.get_by_label(target).first.fill(text)
                except Exception:
                    page.locator("input, textarea").first.fill(text)

        elif action.action_type == "NAVIGATE":
            if not action.target:
                raise ValueError("NAVIGATE action missing URL target")
            page.goto(action.target, wait_until="domcontentloaded")

        elif action.action_type == "DONE":
            # No browser action; caller will stop the loop.
            pass

        else:
            raise ValueError(f"Unknown action_type: {action.action_type}")

    except Exception as exc:
        success = False
        error = str(exc)

    return StepRecord(step_index=0, action=action, success=success, error=error)


def run_agent(
    goal: str,
    start_url: str,
    doc_path: Path,
    max_steps: int = 20,
    headless: bool = False,
) -> List[StepRecord]:
    """
    Main browser-agent loop. Returns the sequence of executed steps.

    Assumes the backend is already running at the URL referenced by start_url.
    """
    steps: List[StepRecord] = []

    if not doc_path.is_file():
        raise FileNotFoundError(f"Document to upload not found at: {doc_path}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=200)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        print(f"[agent] Navigating to {start_url} ...")
        page.goto(start_url, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        for i in range(max_steps):
            screenshot_path = str(AGENT_DIR / f"_agent_step_{i:02d}.png")
            page.screenshot(path=screenshot_path, full_page=True)

            observation = build_observation(page, goal=goal, steps=steps)
            print(f"[agent] Step {i}: calling Gemini planner...")
            action = call_vision_planner(
                goal=goal,
                observation=observation,
                screenshot_path=screenshot_path,
            )

            print(f"[agent]  → action: {action.action_type} target={action.target!r}")

            if action.action_type == "DONE":
                steps.append(
                    StepRecord(
                        step_index=i,
                        action=action,
                        success=True,
                        error=None,
                    )
                )
                print("[agent] Planner reported DONE. Stopping.")
                break

            step_result = _execute_action(page, action, doc_path=doc_path)
            step_result.step_index = i
            steps.append(step_result)

            if not step_result.success:
                print(f"[agent]  ! action failed: {step_result.error}")

            page.wait_for_timeout(1000)

        browser.close()

    return steps


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Gemini Flash Vision + Playwright browser agent for document upload flows."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_SWAGGER_URL,
        help=f"Start URL (default: {DEFAULT_SWAGGER_URL})",
    )
    parser.add_argument(
        "--file",
        default=str(AGENT_DIR / "sample.docx"),
        help="Path to the .docx file to upload (default: agent/sample.docx)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=20,
        help="Maximum planner steps before stopping (default: 20)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headless instead of visible.",
    )
    parser.add_argument(
        "--goal",
        default="Use this page to upload the provided DOCX file and submit the form so that it is formatted.",
        help="High-level goal description for the planner.",
    )
    parser.add_argument(
        "--dump-steps",
        action="store_true",
        help="Print final steps as JSON to stdout.",
    )

    args = parser.parse_args(argv)

    doc_path = Path(args.file).expanduser().resolve()

    steps = run_agent(
        goal=args.goal,
        start_url=args.url,
        doc_path=doc_path,
        max_steps=args.max_steps,
        headless=args.headless,
    )

    print(f"[agent] Finished after {len(steps)} step(s).")
    if args.dump_steps:
        serialisable = [asdict(s) for s in steps]
        print(json.dumps(serialisable, indent=2))


if __name__ == "__main__":
    main()

