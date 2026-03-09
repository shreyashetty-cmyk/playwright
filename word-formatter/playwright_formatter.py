from playwright.sync_api import sync_playwright

DOC_URL = "https://docs.google.com/document/d/1z5r-UH6F_BNfyicrBI5YfimyqgPYe7PFqYex7QdSXm0/edit?usp=sharing"


def wait_for_docs_ready(page):
    """
    Very simple readiness check:
      - give Docs some time to load
      - if it's a login page, let the user log in manually
      - then rely on the user to confirm the document is visible
    """
    # Give redirects a moment
    page.wait_for_timeout(5000)

    # If we're on a Google login page, we cannot automate credentials.
    # Ask you to log in manually in the opened browser window.
    if "accounts.google.com" in page.url:
        print("\nIt looks like the page is a Google login / account chooser.")
        print("Please complete the login in the browser window.")
        input("When the document is visible in Google Docs, press Enter here to continue...")
    else:
        print("\nWaiting 10 seconds for the document to load...")
        page.wait_for_timeout(10000)
        print("If the document is not fully visible yet, wait for it,")
        input("then press Enter here to start formatting...")


def click_document_body(page):
    # Click somewhere in the white page so keyboard shortcuts apply to the doc
    # Docs uses many nested divs; this is a pragmatic approach.
    viewport = page.viewport_size or {"width": 1200, "height": 800}
    page.mouse.click(viewport["width"] // 2, viewport["height"] // 2)


def select_all(page):
    click_document_body(page)
    page.keyboard.press("Control+A")


def set_font(page, font_name: str):
    # NOTE: These selectors may need tweaking if Google changes the UI.
    # This tries to click the font dropdown in the main toolbar.
    font_button = page.locator('div[aria-label^="Font"][role="button"]')
    if font_button.count() == 0:
        # Fallback: any element whose aria-label starts with "Font"
        font_button = page.locator('[aria-label^="Font"]')
    font_button.first.click()
    page.keyboard.type(font_name)
    page.keyboard.press("Enter")


def set_font_size(page, size: str):
    size_box = page.locator('div[aria-label^="Font size"][role="button"]')
    if size_box.count() == 0:
        size_box = page.locator('[aria-label^="Font size"]')
    size_box.first.click()
    page.keyboard.type(size)
    page.keyboard.press("Enter")


def set_justified(page):
    click_document_body(page)
    page.keyboard.press("Control+Shift+J")


def set_line_spacing_1_5(page):
    # Format > Line & paragraph spacing > 1.5
    # Use non-exact text selectors to be a bit more robust
    page.click("text=Format")
    page.click("text=Line & paragraph spacing")
    page.click("text=1.5")


def find_and_select_paragraph(page, text: str):
    """
    Rough helper:
    - Ctrl+F to find text
    - Close find bar
    - Triple-click near the center of the viewport to select the paragraph.
    This is heuristic and may need adjustment for your doc.
    """
    page.keyboard.press("Control+F")
    page.keyboard.type(text)
    page.keyboard.press("Enter")
    page.keyboard.press("Escape")  # close find box; caret should be on the found text

    viewport = page.viewport_size or {"width": 1200, "height": 800}
    page.mouse.click(viewport["width"] // 2, viewport["height"] // 2, click_count=3)


def format_title(page):
    # Go to top, select first paragraph (title), apply title formatting
    click_document_body(page)
    page.keyboard.press("Control+Home")
    page.wait_for_timeout(500)
    viewport = page.viewport_size or {"width": 1200, "height": 800}
    page.mouse.click(viewport["width"] // 2, 150, click_count=3)  # near top

    set_font(page, "Arial")
    set_font_size(page, "24")
    page.keyboard.press("Control+B")
    page.keyboard.press("Control+E")  # center


def format_body(page):
    # Global body formatting: Times New Roman, 12pt, justified, 1.5 spacing
    select_all(page)
    set_font(page, "Times New Roman")
    set_font_size(page, "12")
    set_justified(page)
    set_line_spacing_1_5(page)


def insert_toc(page):
    # Insert TOC on a blank page above Chapter 1
    find_and_select_paragraph(page, "Chapter 1")
    # Move caret to start of the line
    page.keyboard.press("Home")
    # Insert page break before
    page.keyboard.press("Control+Enter")
    click_document_body(page)
    page.click('text="Insert"')
    page.click('text="Table of contents"')
    # Choose variant with page numbers if available
    toc_with_numbers = page.locator('text="Table of contents with page numbers"')
    if toc_with_numbers.count():
        toc_with_numbers.first.click()


def insert_page_numbers(page):
    page.click('text="Insert"')
    page.click('text="Page numbers"')
    # Choose bottom center option if visible
    bottom_center = page.locator('text="Bottom of page"')
    if bottom_center.count():
        bottom_center.first.click()


def format_conclusion(page):
    find_and_select_paragraph(page, "Conclusion")
    # Apply italic to whole section starting at "Conclusion" (heuristic)
    page.keyboard.press("Control+I")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(DOC_URL, wait_until="domcontentloaded")

        wait_for_docs_ready(page)

        # Base body formatting
        format_body(page)

        # Title formatting
        format_title(page)

        # Insert TOC and page numbers (may need selector tweaks)
        insert_toc(page)
        insert_page_numbers(page)

        # Conclusion styling (heuristic)
        format_conclusion(page)

        print("Playwright formatting script finished. Check the doc, then press Enter to close.")
        input()
        browser.close()


if __name__ == "__main__":
    main()

