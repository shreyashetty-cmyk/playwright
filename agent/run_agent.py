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
    """Upload one file via Swagger, click Execute, save response. Returns path to saved file or None."""
    file_path = os.path.abspath(file_path)
    if not os.path.isfile(file_path):
        return None
    base = os.path.basename(file_path)

    # Reset file input (clear previous) and set new file
    file_input = page.locator('input[type="file"]').first
    file_input.set_input_files(file_path)
    page.wait_for_timeout(400)

    # Wait for POST /format (with or without use_llm query; Swagger may not set it from UI)
    with page.expect_response(
        lambda r: "/format" in r.url and r.request.method == "POST" and r.status == 200,
        timeout=60000 if use_llm else 30000,
    ) as response_info:
        page.get_by_text("Execute", exact=True).first.click()

    response = response_info.value
    body = response.body()
    cd = response.headers.get("content-disposition") or ""
    if "filename=" in cd:
        filename = cd.split("filename=")[-1].strip('"\'')
    else:
        filename = f"formatted_{base}"
    save_path = os.path.join(output_dir, filename)
    with open(save_path, "wb") as f:
        f.write(body)
    return save_path


def run(files: list[str] | None = None, folder: str | None = None, use_llm: bool = False):
    """
    Run the Playwright flow. If files or folder are given, format each in turn (batch).
    Otherwise use FILE_TO_UPLOAD.
    """
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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=400)
        page = browser.new_page()

        print("Opening Swagger UI...")
        page.goto("http://127.0.0.1:8000/docs", wait_until="networkidle")
        page.wait_for_timeout(1000)

        print("Expanding POST /format...")
        page.locator(".opblock-summary").first.click()
        page.wait_for_timeout(1200)

        try_it = page.get_by_text("Try it out", exact=True).first
        if try_it.is_visible():
            print("Clicking Try it out...")
            try_it.click()
            page.wait_for_timeout(800)

        file_input = page.locator('input[type="file"]').first
        file_input.wait_for(state="visible", timeout=10000)

        for i, path in enumerate(to_format):
            print(f"[{i + 1}/{len(to_format)}] Formatting {os.path.basename(path)}...")
            saved = _format_one_file(page, path, OUTPUT_DIR, use_llm=use_llm)
            if saved:
                print(f"  Saved: {saved}")
            else:
                print(f"  Skip (not found or error): {path}")
            if i < len(to_format) - 1:
                page.wait_for_timeout(1500)

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
