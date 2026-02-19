from __future__ import annotations
from pathlib import Path
from markdown import markdown
from shutil import copyfile

# Try to import WeasyPrint, but don't crash if it misbehaves (common on Windows).
try:
    from weasyprint import HTML  # type: ignore[import-untyped]
    WEASYPRINT_AVAILABLE = True
except Exception as e:  # WeasyPrint can raise non-ImportError exceptions
    HTML = None  # type: ignore[assignment]
    WEASYPRINT_AVAILABLE = False
    WEASYPRINT_IMPORT_ERROR = str(e)


# ---------- Paths (defaults for the leave leakage report) ----------

BASE_DIR = Path(__file__).resolve().parents[2]
CSS_SOURCE = BASE_DIR / "docs" / "crc_report.css"
OUTPUTS_DIR = BASE_DIR / "outputs"

EXEC_PACK_MD_PATH = OUTPUTS_DIR / "crc_executive_pack.md"
EXEC_PACK_HTML_PATH = OUTPUTS_DIR / "crc_executive_pack.html"
EXEC_PACK_PDF_PATH = OUTPUTS_DIR / "crc_executive_pack.pdf"


# ---------- HTML template ----------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <link rel="stylesheet" href="crc_report.css">
</head>
<body>
  <div class="report-container">
    {content}
  </div>
</body>
</html>
"""


# ---------- Builders ----------

def build_html_from_markdown(
    md_path: Path,
    html_path: Path,
    page_title: str,
) -> Path:
    """
    Convert the given Markdown file into a styled HTML file.
    """
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown report not found: {md_path}")

    md_text = md_path.read_text(encoding="utf-8")
    # Use 'extra' + 'tables' so Markdown tables become proper <table> elements.
    content_html = markdown(md_text, extensions=["extra", "tables"])

    full_html = HTML_TEMPLATE.format(title=page_title, content=content_html)

    # Ensure output folder exists
    html_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy shared CSS alongside the HTML so <link href="crc_report.css"> works
    if CSS_SOURCE.exists():
        css_target = html_path.parent / CSS_SOURCE.name
        try:
            copyfile(CSS_SOURCE, css_target)
        except OSError:
            # Non-fatal: HTML will still work, just without custom styling
            pass

    # Write the final HTML
    html_path.write_text(full_html, encoding="utf-8")

    return html_path

def html_to_pdf(
    html_path: Path,
    pdf_path: Path,
) -> Path | None:
    """
    Render the HTML report to PDF using WeasyPrint, if available.
    Returns the PDF path on success, or None if WeasyPrint is not available.
    """
    if not html_path.exists():
        raise FileNotFoundError(f"HTML report not found: {html_path}")

    if not WEASYPRINT_AVAILABLE:
        print("WeasyPrint not available; skipping PDF generation.")
        try:
            print(f"Reason: {WEASYPRINT_IMPORT_ERROR}")
        except NameError:
            pass
        return None

    # Let WeasyPrint load the HTML file (and its linked CSS) from disk
    HTML(filename=str(html_path)).write_pdf(str(pdf_path))
    return pdf_path


def build_html_and_pdf(
    md_path: Path,
    html_path: Path,
    pdf_path: Path | None = None,
    page_title: str = "Payroll Compliance Report",
) -> tuple[Path, Path | None]:
    """
    High-level helper: build HTML from Markdown, then render PDF if possible.

    Returns (html_path, pdf_path_or_None).
    """
    html_built = build_html_from_markdown(
        md_path=md_path,
        html_path=html_path,
        page_title=page_title,
    )

    pdf_built: Path | None = None
    if pdf_path is not None:
        pdf_built = html_to_pdf(html_path=html_built, pdf_path=pdf_path)

    return html_built, pdf_built


# Convenience wrapper for the original leave-leakage report, if ever needed.
def build_default_html_and_pdf() -> tuple[Path, Path | None]:
    return build_html_and_pdf(
        md_path=EXEC_PACK_MD_PATH ,
        html_path=EXEC_PACK_HTML_PATH,
        pdf_path=EXEC_PACK_PDF_PATH,
        page_title="Leave & Entitlement Leakage Review",
    )


if __name__ == "__main__":
    build_default_html_and_pdf()
