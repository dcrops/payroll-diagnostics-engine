from __future__ import annotations

from pathlib import Path
from shutil import copyfile
from markdown import markdown

from reporting.core.paths import get_repo_root, get_default_outputs_dir

# Try to import WeasyPrint, but don't crash if it misbehaves (common on Windows).
try:
    from weasyprint import HTML  # type: ignore[import-untyped]
    WEASYPRINT_AVAILABLE = True
except Exception as e:  # WeasyPrint can raise non-ImportError exceptions
    HTML = None  # type: ignore[assignment]
    WEASYPRINT_AVAILABLE = False
    WEASYPRINT_IMPORT_ERROR = str(e)


# ---------- Paths (defaults for the leave leakage report) ----------

REPO_ROOT = get_repo_root()
CSS_SOURCE = REPO_ROOT / "docs" / "crc_report.css"
OUTPUTS_DIR = get_default_outputs_dir()

EXEC_PACK_MD_PATH = OUTPUTS_DIR / "crc_executive_pack.md"
EXEC_PACK_HTML_PATH = OUTPUTS_DIR / "crc_executive_pack.html"
EXEC_PACK_PDF_PATH = OUTPUTS_DIR / "crc_executive_pack.pdf"


# ---------- Fallback CSS (used if crc_report.css cannot be loaded) ----------

DEFAULT_EMBEDDED_CSS = """
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  font-size: 11pt;
  line-height: 1.5;
  color: #111827;
  margin: 0;
  padding: 0;
}

.report-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 32px;
}

h1, h2, h3, h4 {
  color: #7b001c;
  font-weight: 600;
  margin-top: 1.2em;
  margin-bottom: 0.4em;
}

h1 {
  font-size: 22pt;
}

h2 {
  font-size: 16pt;
}

h3 {
  font-size: 13pt;
}

hr {
  border: none;
  border-top: 2px solid #7b001c;
  margin: 16px 0 12px 0;
}

table {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0 16px 0;
}

th, td {
  border: 1px solid #d1d5db;
  padding: 6px 8px;
  font-size: 10pt;
}

th {
  background: #111827;
  color: #ffffff;
  font-weight: 600;
}

.badge-high {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 9999px;
  background: #fee2e2;
  color: #b91c1c;
  font-size: 9pt;
  font-weight: 600;
}

.badge-medium {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 9999px;
  background: #fef3c7;
  color: #92400e;
  font-size: 9pt;
  font-weight: 600;
}

.badge-low {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 9999px;
  background: #dcfce7;
  color: #166534;
  font-size: 9pt;
  font-weight: 600;
}

blockquote {
  border-left: 3px solid #e5e7eb;
  padding-left: 10px;
  margin-left: 0;
  color: #4b5563;
  font-size: 10pt;
}

ul, ol {
  padding-left: 22px;
}
"""


# ---------- HTML template ----------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
{css}
  </style>
</head>
<body>
  <div class="report-container">
    {content}
  </div>
</body>
</html>
"""


# ---------- Builders ----------

def _load_css_text() -> str:
    """
    Try to load crc_report.css from docs/. If it fails or is empty, fall
    back to DEFAULT_EMBEDDED_CSS so reports are never unstyled.
    """
    css_text = ""

    if CSS_SOURCE.exists():
        try:
            css_text = CSS_SOURCE.read_text(encoding="utf-8")
            if css_text.strip():
                print(f"Using CSS from {CSS_SOURCE}")
                return css_text
            else:
                print(f"Warning: {CSS_SOURCE} was empty; using embedded fallback CSS.")
        except OSError as e:
            print(f"Warning: could not read {CSS_SOURCE} ({e}); using embedded fallback CSS.")
    else:
        print(f"Warning: {CSS_SOURCE} not found; using embedded fallback CSS.")

    return DEFAULT_EMBEDDED_CSS


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
    content_html = markdown(md_text, extensions=["extra", "tables"])

    css_text = _load_css_text()

    full_html = HTML_TEMPLATE.format(
        title=page_title,
        content=content_html,
        css=css_text,
    )

    # Ensure output folder exists
    html_path.parent.mkdir(parents=True, exist_ok=True)

    # Optional: still copy crc_report.css alongside the HTML (not required for styling)
    if CSS_SOURCE.exists():
        css_target = html_path.parent / CSS_SOURCE.name
        try:
            if css_target != CSS_SOURCE:
                copyfile(CSS_SOURCE, css_target)
        except OSError:
            pass

    html_path.write_text(full_html, encoding="utf-8")
    return html_path


def html_to_pdf(
    html_path: Path,
    pdf_path: Path,
) -> Path | None:
    """
    Render the HTML report to PDF using WeasyPrint, if available.
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


def build_default_html_and_pdf() -> tuple[Path, Path | None]:
    return build_html_and_pdf(
        md_path=EXEC_PACK_MD_PATH,
        html_path=EXEC_PACK_HTML_PATH,
        pdf_path=EXEC_PACK_PDF_PATH,
        page_title="Leave & Entitlement Leakage Review",
    )


if __name__ == "__main__":
    build_default_html_and_pdf()