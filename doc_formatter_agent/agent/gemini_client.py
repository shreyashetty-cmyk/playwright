"""
Gemini Flash Vision client wrapper for the browser agent.

Responsibilities:
- Read API key and model name from environment.
- Accept a high-level goal, structured observation dict, and a screenshot path.
- Call a Gemini multimodal model (text + image) with a strict system prompt.
- Return the model's response parsed as JSON describing the next browser action.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover - handled at runtime
    genai = None


GEMINI_API_KEY_ENV_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
DEFAULT_MODEL_NAME = os.environ.get("GOOGLE_MODEL", "gemini-2.5-flash")


class GeminiClientError(RuntimeError):
    """Raised when the Gemini client cannot fulfil a request."""


def _get_api_key() -> str:
    for name in GEMINI_API_KEY_ENV_VARS:
        value = os.environ.get(name)
        if value:
            return value
    raise GeminiClientError(
        "No Gemini API key found. Please set GEMINI_API_KEY or GOOGLE_API_KEY in your environment."
    )


def _ensure_client() -> None:
    if genai is None:  # pragma: no cover - environment dependent
        raise GeminiClientError(
            "google-generativeai is not installed. "
            "Install it with `pip install google-generativeai` inside your virtualenv."
        )
    api_key = _get_api_key()
    genai.configure(api_key=api_key)


@dataclass
class PlannerAction:
    """Structured action returned by Gemini for the browser agent."""

    action_type: str
    target: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    raw_response: Optional[str] = None


PLANNER_SYSTEM_PROMPT = """
You are a cautious browser automation planner controlling a Playwright agent.

You are given:
- A high-level GOAL (what the user ultimately wants, e.g. upload and submit a .docx or collect articles on a topic).
- A structured OBSERVATION describing the current page (URL, title, visible elements, search results, etc.).
- A SCREENSHOT of the current page.

Your job is to choose exactly ONE next action for the Playwright agent.

You must respond with STRICT JSON, with this shape (no extra keys, no comments, no prose):
{
  "action_type": "CLICK" | "SET_FILE" | "TYPE" | "NAVIGATE" | "SCROLL" | "EXTRACT_MAIN_TEXT" | "DONE",
  "target": "string describing the element / selector / URL (or a short description for SCROLL / EXTRACT_MAIN_TEXT)",
  "arguments": { ... optional extra parameters, may be null }
}

Semantics:
- CLICK: click a button, link, or control. `target` should be a concise description or selector hint
         (e.g. "button:Try it out", "button:Execute", "input[type=file]", "link:Upload", "link:Article title").
- SET_FILE: choose a local file in a file input. Use `arguments` = { "file_role": "docx_to_upload" } and
            set `target` to describe which input to use (e.g. "input[type=file]" or label text).
- TYPE: type text into an input. `arguments` must contain { "text": "..." }.
- NAVIGATE: go to a new URL. `target` must be the full URL string (usually taken from the OBSERVATION, not invented).
- SCROLL: scroll the page to reveal more content. `arguments` may contain { "direction": "down" | "up", "pixels": number }.
- EXTRACT_MAIN_TEXT: you believe the current page is an article/content page; ask the agent to extract the main body text.
                     The implementation will choose appropriate DOM regions; you do NOT need to provide selectors.
- DONE: the task is successfully completed; `target` can be a short success message.

Constraints:
- Prefer actions that move you towards the GOAL.
- Avoid destructive actions (log out, delete, unsubscribe, random navigation).
- For Swagger UI upload flows:
  - Expand the relevant endpoint if needed.
  - Click 'Try it out' before attempting to set the file.
  - Use SET_FILE on the correct file input.
  - Then CLICK the 'Execute' button.
- For research flows over search pages:
  - Prefer NAVIGATE actions that use URLs explicitly listed in the OBSERVATION (e.g. search_results) instead of making up URLs.

Output rules:
- OUTPUT MUST BE PURE JSON. Do NOT wrap in markdown. Do NOT add explanations.
- If you believe the GOAL is fully achieved, use action_type = "DONE".
"""


def call_vision_planner(
    goal: str,
    observation: Dict[str, Any],
    screenshot_path: str,
    model_name: str | None = None,
) -> PlannerAction:
    """
    Call Gemini Flash Vision with the current observation and screenshot.

    Returns a PlannerAction describing the next Playwright step.
    """
    _ensure_client()

    model = genai.GenerativeModel(model_name or DEFAULT_MODEL_NAME)

    # Read screenshot bytes
    try:
        with open(screenshot_path, "rb") as f:
            image_bytes = f.read()
    except OSError as exc:
        raise GeminiClientError(f"Failed to read screenshot at {screenshot_path}: {exc}") from exc

    prompt_parts = [
        PLANNER_SYSTEM_PROMPT.strip(),
        "",
        "GOAL:",
        goal.strip(),
        "",
        "OBSERVATION (JSON):",
        json.dumps(observation, ensure_ascii=False, indent=2),
        "",
        "Now respond with the next action as strict JSON only.",
    ]
    text_prompt = "\n".join(prompt_parts)

    try:
        response = model.generate_content(
            [
                {"text": text_prompt},
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_bytes,
                    }
                },
            ],
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 512,
            },
        )
    except Exception as exc:  # pragma: no cover - network / API specific
        raise GeminiClientError(f"Gemini planner call failed: {exc}") from exc

    raw = (getattr(response, "text", None) or "").strip()
    if not raw:
        raise GeminiClientError("Gemini returned an empty response for planner call.")

    # Some models may wrap JSON in code fences; strip common wrappers.
    cleaned = raw
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lstrip().startswith("json"):
            cleaned = cleaned.lstrip()[4:]

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GeminiClientError(f"Gemini planner returned non-JSON output: {raw}") from exc

    action_type = str(data.get("action_type", "")).upper()
    target = data.get("target")
    arguments = data.get("arguments")

    if action_type not in {"CLICK", "SET_FILE", "TYPE", "NAVIGATE", "SCROLL", "EXTRACT_MAIN_TEXT", "DONE"}:
        raise GeminiClientError(f"Invalid or missing action_type in planner output: {data!r}")

    return PlannerAction(
        action_type=action_type,
        target=target if isinstance(target, str) else None,
        arguments=arguments if isinstance(arguments, dict) else None,
        raw_response=raw,
    )

