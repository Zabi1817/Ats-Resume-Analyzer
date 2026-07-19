import logging
import traceback
from playwright.sync_api import sync_playwright

logger = logging.getLogger('ats_resume_scorer')


def generate_combined_pdf(html_docs: dict[str, str]) -> bytes:
    """
    Renders multiple HTML documents into a single PDF using headless Chromium.

    Uses Playwright's **synchronous** API because on Windows the default
    ProactorEventLoop used by uvicorn raises NotImplementedError when
    the async API tries to spawn a browser subprocess.  The caller
    (routes.py) wraps this in ``run_in_threadpool`` so it never blocks
    the FastAPI event loop.
    """
    logger.info("Starting PDF generation via Playwright (sync API)")

    # Combine HTML strings with explicit page breaks
    combined_html = ""
    for name, html_str in html_docs.items():
        combined_html += html_str + '\n<div style="page-break-after: always;"></div>\n'

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Load the raw HTML into the browser
            page.set_content(combined_html, wait_until="networkidle")

            # Print to PDF (A4, preserving background colors)
            pdf_bytes = page.pdf(format="A4", print_background=True)

            browser.close()
            logger.info(f"Successfully generated {len(pdf_bytes)} bytes of PDF")
            return pdf_bytes

    except Exception as e:
        logger.error(f"Playwright failed to generate PDF:\n{traceback.format_exc()}")
        raise
